"""Benchmark on invented documents: leaks (private values still extractable) and
over-redaction (public values that disappeared). Usage: python -m oscura_atti.bench --n 200"""

from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
from collections import Counter

import pymupdf

from . import engine, synthetic
from .config import Config


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.replace("’", "'")).strip().lower()


def output_text(pdf: bytes, ocr: bool) -> str:
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        parts = []
        for page in doc:
            if ocr:
                parts.append(page.get_text(textpage=page.get_textpage_ocr(language="ita", dpi=300, full=True)))
            else:
                parts.append(page.get_text())
    return _norm(" ".join(parts))


def present(value: str, haystack: str) -> bool:
    v = _norm(value)
    return bool(re.search(rf"(?<!\w){re.escape(v)}(?!\w)", haystack))


def run(n: int, scanned_every: int = 0, verbose: bool = False) -> dict:
    conf = Config()
    stats = Counter()
    failures = []
    t0 = time.time()
    for seed in range(n):
        doc = synthetic.generate(seed)
        scanned = bool(scanned_every) and seed % scanned_every == 0
        pdf = synthetic.as_scan(doc.pdf) if scanned else doc.pdf
        out, report = engine.redact(pdf, conf, verify_ocr=False)
        text = output_text(out, scanned)
        public_words = {w for v in doc.public_values for w in _norm(v).split()}
        source_words = _norm(doc.text)
        for v in set(doc.private_values):
            stats["private"] += 1
            leaked = present(v, text)
            if not leaked and " " in v and not any(c.isdigit() for c in v):
                # Partial leaks: any word of a private name still readable (e.g. the given name).
                # Words also used elsewhere in the act (towns, public names, common words) are skipped.
                for w in _norm(v).split():
                    if len(w) >= 4 and w not in public_words and source_words.count(w) == _norm(" ".join(
                            x for x in doc.private_values)).count(w) and present(w, text):
                        leaked = True
                        v = f"{v} (word: {w})"
                        break
            if leaked:
                stats["leaked"] += 1
                failures.append({"seed": seed, "kind": doc.kind, "scanned": scanned, "leak": v})
        for v in set(doc.public_values):
            stats["public"] += 1
            if not present(v, text):
                stats["over_redacted"] += 1
                failures.append({"seed": seed, "kind": doc.kind, "scanned": scanned, "lost_public": v})
        stats["docs"] += 1
        stats["outcome_" + report["outcome"]] += 1
    result = {
        "docs": stats["docs"],
        "private_values": stats["private"],
        "leaked": stats["leaked"],
        "leak_rate": round(stats["leaked"] / max(1, stats["private"]), 4),
        "public_values": stats["public"],
        "over_redacted": stats["over_redacted"],
        "over_redaction_rate": round(stats["over_redacted"] / max(1, stats["public"]), 4),
        "outcomes": {k[8:]: v for k, v in stats.items() if k.startswith("outcome_")},
        "seconds": round(time.time() - t0, 1),
    }
    if verbose:
        result["failures"] = failures
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--scanned-every", type=int, default=0, help="every k-th document as a scan (OCR)")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    print(json.dumps(run(a.n, a.scanned_every, a.verbose), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
