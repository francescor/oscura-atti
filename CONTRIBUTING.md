# Contributing

Thank you for helping. Issues and pull requests are welcome in English or Italian; code, comments,
commit messages and documentation are in English, and the README exists in both languages.

## The one rule: no real documents

Real public-sector documents contain personal data. **Never commit, attach or paste one**, nor any
real name, tax code, IBAN or address taken from one — not in an issue, a pull request, a test or a
commit message. The repository enforces this with a pre-commit hook and a CI check
(`tools/check_forbidden_files.py`, which also inspects file contents), and the issue forms ask you to
confirm it.

Every problem found on a real document becomes an **invented** reproduction: a test in `tests/`
built with `oscura_atti.synthetic`, and, if it is a new pattern, a new case in `synthetic.py`.

## Set up

```bash
git clone https://github.com/francescor/oscura-atti && cd oscura-atti
git config core.hooksPath .githooks        # no documents, both README languages together
python3 -m venv .venv && .venv/bin/pip install -e ".[test]" pytest-xdist
sudo apt install tesseract-ocr tesseract-ocr-ita   # OCR tests
.venv/bin/python -m pytest -q -n auto
```

Before proposing a change to the recognizers, run the benchmark on invented documents and compare
the numbers with the README:

```bash
.venv/bin/python -m oscura_atti.bench --n 300 --verbose
.venv/bin/python -m oscura_atti.bench --n 40 --scanned-every 1   # scanned pages, slower
```

A change that leaks a private value or hides a public one in the benchmark is not mergeable.

## Pull requests

- One topic per pull request, with a test that fails before the change.
- If you change `README.md`, change `README.it.md` in the same commit (and vice versa).
- Add a line under `## [Unreleased]` in `CHANGELOG.md`.
- The checks must pass: repository checks, tests on Python 3.11–3.14.

## Releases (maintainers)

1. Set the new version in `pyproject.toml`, `src/oscura_atti/__init__.py` and `server.json` (CI checks
   that they agree).
2. Move the `Unreleased` entries of `CHANGELOG.md` under the new version, with the date.
3. Commit, then `git tag -a vX.Y.Z -m "oscura-atti X.Y.Z" && git push origin vX.Y.Z`.

The `publish` workflow then builds and signs the container image, publishes the package on PyPI,
updates the MCP Registry entry and creates the GitHub release with the changelog section.
