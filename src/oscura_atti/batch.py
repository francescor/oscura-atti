"""Redact every PDF / .p7m of a folder tree into another folder, in parallel.

Output: for each input `a/b/act.pdf` -> `a/b/act.redacted.pdf` + `a/b/act.report.json`, and an
`index.json` with one row per input (status, outcome, counts). Inputs are never modified.
Already processed files (same name and size, report present) are skipped, so a run can resume.
"""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path

from . import service
from .config import Config

from .convert import SUPPORTED as SUFFIXES


def _targets(src: Path, rel: Path, out_dir: Path) -> tuple[Path, Path]:
    stem = rel.name
    for suffix in (".p7m", ".P7M"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    stem = Path(stem).stem
    base = out_dir / rel.parent / stem
    return base.with_name(base.name + ".redacted.pdf"), base.with_name(base.name + ".report.json")


def _one(args: tuple[str, str, str, dict]) -> dict:
    src, rel, out_dir, conf_dict = args
    src_p, out_p = Path(src), Path(out_dir)
    pdf_out, rep_out = _targets(src_p, Path(rel), out_p)
    row = {"input": rel, "output": str(pdf_out.relative_to(out_p)), "report": str(rep_out.relative_to(out_p))}
    data = src_p.read_bytes()
    row["sha256"] = hashlib.sha256(data).hexdigest()
    if rep_out.exists() and pdf_out.exists():
        try:
            old = json.loads(rep_out.read_text(encoding="utf-8"))
            if old.get("input_sha256") == row["sha256"]:
                row.update(status="done", outcome=old.get("outcome"), skipped=True,
                           redacted_entities=old.get("redacted_entities"))
                return row
        except (ValueError, OSError):
            pass
    try:
        output, report = service.redact_file(data, src_p.name, Config.from_dict(conf_dict))
    except Exception as e:  # unreadable, encrypted, not a PDF...
        row.update(status="error", error=f"{type(e).__name__}: {e}")
        return row
    report["input_sha256"] = row["sha256"]
    if report.get("unchanged"):
        # nothing to redact: an identical copy of the original, in its own format
        pdf_out = pdf_out.with_name(pdf_out.name.replace(".redacted.pdf", ".unchanged") + "".join(Path(rel).suffixes[-1:]))
        row["output"] = str(pdf_out.relative_to(out_p))
    pdf_out.parent.mkdir(parents=True, exist_ok=True)
    pdf_out.write_bytes(output)
    rep_out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    row.update(status="done", outcome=report["outcome"], redacted_entities=report["redacted_entities"],
               unchanged=bool(report.get("unchanged")),
               leaks=len(report.get("leaks", [])), ocr_pages=len(report["ocr_pages"]),
               sensitive=bool(report["sensitive_terms"]))
    return row


def _conf_dict(conf: Config) -> dict:
    d = asdict(conf)
    return d


def _learn_one(args: tuple[str, dict]) -> list[tuple[str, str, str]]:
    path, conf_dict = args
    try:
        data = Path(path).read_bytes()
        conf = Config.from_dict({**conf_dict, "ocr": False})
        report = service.analyse(data, conf, include_values=True)
    except Exception:
        return []
    out = []
    for e in report["entities"]:
        if e["type"] == "PERSON" and e["values"]:
            out.append((max(e["values"], key=len), e["action"], e["reason"]))
    return out


# Presence marks and abbreviations that stick to names in minutes ("AG MODELLINI Valentina", "TIPICELLI LUCA Resp").
_NOISE = {"ag", "p", "a", "as", "g", "pres", "ass", "resp", "resp.", "vice", "dott", "dott.", "dott.ssa", "ing.", "arch.",
          "geom.", "avv.", "rag.", "sig.", "sig.ra"}


def clean_name(name: str) -> str:
    words = " ".join(name.split()).split(" ")
    while words and words[0].lower() in _NOISE:
        words.pop(0)
    while words and words[-1].lower() in _NOISE:
        words.pop()
    return " ".join(words)


def merge_learned(entries: list[dict], lex, name_key: str = "name", count_keys: tuple[str, ...] = ()) -> list[dict]:
    """Merge entries of the same person ("ESEMPLARI Lucia Maria" / "Lucia Maria"): the longer name
    wins, counts are added up, roles merged."""
    for e in entries:
        e[name_key] = clean_name(e[name_key])
    entries = sorted(entries, key=lambda e: (-len(lex.token_key(e[name_key])), -sum(e.get(k, 0) for k in count_keys)))
    merged: list[dict] = []
    for e in entries:
        key = lex.token_key(e[name_key])
        if len(key) < 2 and not any(key and key <= lex.token_key(m[name_key]) for m in merged):
            continue
        target = next((m for m in merged if key <= lex.token_key(m[name_key])), None)
        if target is None:
            merged.append(dict(e))
            continue
        for k in count_keys:
            target[k] = target.get(k, 0) + e.get(k, 0)
        for list_key in ("roles", "ruoli"):
            if list_key in e:
                target[list_key] = list(dict.fromkeys(target.get(list_key, []) + e[list_key]))[:3]
    return sorted(merged, key=lambda e: -e.get(count_keys[0], 0) if count_keys else 0)


def learn_public_persons(files: list[Path], conf: Config, jobs: int = 1, min_docs: int = 2) -> list[dict]:
    """First pass over an archive: names kept because of a public role in at least `min_docs`
    documents, and kept more often than redacted, are officials. Review the list by hand."""
    from collections import Counter, defaultdict
    from .engine import _Lexicon
    lex = _Lexicon(conf)
    kept, redacted = defaultdict(set), defaultdict(set)
    forms, roles = defaultdict(Counter), defaultdict(Counter)
    pdfs = [str(f) for f in files if f.name.lower().endswith((".pdf", ".p7m"))]
    tasks = [(f, asdict(conf)) for f in pdfs]
    results = ProcessPoolExecutor(jobs).map(_learn_one, tasks, chunksize=2) if jobs > 1 else map(_learn_one, tasks)
    for path, rows in zip(pdfs, results):
        for value, action, reason in rows:
            key = lex.token_key(value)
            if len(key) < 2:
                continue
            if action == "keep" and reason.startswith("public role"):
                kept[key].add(path)
                forms[key][value] += 1
                roles[key][reason] += 1
            elif action == "redact":
                redacted[key].add(path)
    learned = [{"name": forms[k].most_common(1)[0][0], "documents_with_role": len(docs),
                "documents_redacted": len(redacted.get(k, ())), "roles": [r for r, _ in roles[k].most_common(3)]}
               for k, docs in kept.items() if len(docs) >= min_docs and len(docs) >= len(redacted.get(k, ()))]
    return merge_learned(learned, lex, "name", ("documents_with_role", "documents_redacted"))


def run_batch(in_dir: Path, out_dir: Path, conf: Config, jobs: int = 1, learn_public: bool = False) -> int:
    files = sorted(p for p in in_dir.rglob("*") if p.is_file() and p.name.lower().endswith(SUFFIXES))
    out_dir.mkdir(parents=True, exist_ok=True)
    if learn_public:
        learned = learn_public_persons(files, conf, jobs)
        (out_dir / "public_persons_learned.json").write_text(json.dumps(learned, ensure_ascii=False, indent=1),
                                                              encoding="utf-8")
        conf.public_persons = sorted(set(conf.public_persons) | {x["name"] for x in learned})
        print(f"learned {len(learned)} public persons (see {out_dir / 'public_persons_learned.json'})")
    tasks = [(str(p), str(p.relative_to(in_dir)), str(out_dir), _conf_dict(conf)) for p in files]
    if jobs > 1:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            rows = list(pool.map(_one, tasks, chunksize=1))
    else:
        rows = [_one(t) for t in tasks]
    (out_dir / "index.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    errors = sum(r["status"] == "error" for r in rows)
    review = sum(r.get("outcome") == "review" for r in rows)
    print(f"{len(rows)} files: {len(rows) - errors} redacted ({review} to review), {errors} errors")
    return 1 if errors else 0
