#!/usr/bin/env python3
"""Every document translated in two languages must change in both, in the same commit.

Pairs: any `NAME.md` that has a sibling `NAME.it.md` (README.md / README.it.md, ...).
  --staged              check the commit being made (pre-commit hook)
  --range BASE HEAD     check every commit in BASE..HEAD (CI)
"""

import subprocess
import sys
from pathlib import Path


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def pairs() -> list[tuple[str, str]]:
    files = git("ls-files").splitlines()
    out = []
    for f in files:
        if f.endswith(".it.md"):
            base = f[: -len(".it.md")] + ".md"
            if base in files or Path(base).exists():
                out.append((base, f))
    return out or [("README.md", "README.it.md")]


def problems(changed: set[str]) -> list[str]:
    msgs = []
    for a, b in pairs():
        if (a in changed) != (b in changed):
            done, missing = (a, b) if a in changed else (b, a)
            msgs.append(f"{done} changed but {missing} did not: update both languages in the same commit")
    return msgs


def main() -> int:
    if "--range" in sys.argv:
        i = sys.argv.index("--range")
        base, head = sys.argv[i + 1], sys.argv[i + 2]
        commits = git("rev-list", f"{base}..{head}").split() if base.strip("0") else [head]
        errors = []
        for c in commits:
            changed = set(git("diff-tree", "--no-commit-id", "--name-only", "-r", "--root", c).split())
            errors += [f"{c[:8]}: {m}" for m in problems(changed)]
    else:
        changed = set(git("diff", "--cached", "--name-only").split())
        errors = problems(changed)
    if errors:
        print("Translated documents must change together:", file=sys.stderr)
        for e in errors:
            print("  " + e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
