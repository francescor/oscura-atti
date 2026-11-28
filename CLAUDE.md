# CLAUDE.md — oscura-atti

Standalone service (CLI + library + MCP server) that redacts personal data in public-sector PDFs,
replacing values with consistent labels ("Persona 1", "Person 1"...). Independent from any archive
that uses it.

## Hard rules

1. **Never commit a document** (PDF, p7m, office files, images): they may contain personal data.
   Test documents are generated at runtime by `src/oscura_atti/synthetic.py` with INVENTED data.
   Guards: `.gitignore`, `.githooks/pre-commit` (run `git config core.hooksPath .githooks` after
   cloning), CI step `tools/check_forbidden_files.py`. Experiments on real documents happen outside
   the repo; only aggregate numbers may be written here, never names or values. Only exception:
   `docs/media/` (PNG/GIF/MP4 made by `tools/make_media.py` from the invented act — never from real ones).
2. Repository language: **English** (code, comments, docs, commit messages). Label texts exist per
   language in `labels.py`. The README is also in **Italian** (`README.it.md`): every commit that
   changes one language must change the other too (pre-commit hook + CI, `tools/check_translations.py`).
   Same for any future `NAME.md` / `NAME.it.md` pair.
3. The service stores nothing: no PDFs, no value→label mapping. Reports returned to callers contain
   values only when explicitly asked (`include_values`).
4. Licence AGPL-3.0-or-later (PyMuPDF is AGPL).

## Layout

- `recognizers/` — packs: `common`, `it`, `uk`, `eu` (es/fr/de); `words.py` = titles, roles,
  non-name words, sensitive terms per language. Recognizers flagged `uses_lines = True` (name cues)
  see the text with line breaks; all others see it with line breaks turned into spaces.
- `pdf.py` — character-level text model with boxes, OCR detection, redaction and scrubbing.
- `engine.py` — clean-up of person mentions, grouping, propagation, roles, labels, verification.
- `service.py` — PDF or .p7m in; `cli.py`, `batch.py`, `mcp_server.py` (mcp SDK 2.x, `MCPServer`).
- `bench.py` — benchmark on synthetic documents (leak and over-redaction rates).

## Releases

Version in three places (`pyproject.toml`, `src/oscura_atti/__init__.py`, `server.json`: CI checks them),
`CHANGELOG.md` section with the date, then tag `vX.Y.Z`. `.github/workflows/publish.yml` does the rest:
signed multi-arch image on GHCR, PyPI (Trusted Publishing, environment `pypi`), MCP Registry
(`io.github.francescor/oscura-atti`, GitHub OIDC; needs the image label and the `mcp-name:` comment in
both READMEs), GitHub release with the changelog section. Branch `main` and tags `v*` are protected by
repository rulesets; the required check is "all tests passed". Actions are pinned to commit SHAs
(Dependabot updates them).

## Commands

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[mcp,test]" pytest-xdist
.venv/bin/python -m pytest -q -n 8
.venv/bin/python -m oscura_atti.bench --n 300 --verbose
.venv/bin/python -m oscura_atti.bench --n 40 --scanned-every 1   # OCR, slower
```

Every bug found on a real document becomes (a) an invented reproduction in `tests/` and, if it is
a new pattern, (b) a new case in `synthetic.py` — never the real text.
