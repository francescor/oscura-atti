"""Shared building blocks for recognizers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable


@dataclass(frozen=True)
class Finding:
    type: str
    start: int
    end: int
    text: str
    rule: str
    score: float = 1.0


Recognizer = Callable[[str], Iterable[Finding]]

# Upper/lower-case letters of Latin-script European languages (Latin-1 + Latin Extended-A).
UP = "A-ZÀ-ÖØ-ÞĀĂĄĆĈĊČĎĐĒĔĖĘĚĜĞĠĢĤĦĨĪĬĮİĴĶĹĻĽĿŁŃŅŇŊŌŎŐŒŔŖŘŚŜŞŠŢŤŦŨŪŬŮŰŲŴŶŸŹŻŽ"
LO = "a-zß-öø-ÿāăąćĉċčďđēĕėęěĝğġģĥħĩīĭįıĵķĺļľŀłńņňŋōŏőœŕŗřśŝşšţťŧũūŭůűųŵŷźżž"
APOS = "'’"

# A name token: "Rossi", "D'Amico", "O'Brien", "ROSSI", "DIDONE'" (final apostrophe = accent), "Müller-Lüdenscheidt".
T_CAP = rf"[{UP}][{LO}]+(?:[{APOS}][{UP}{LO}][{LO}]+)?(?:-[{UP}][{LO}]+)?"
T_APO = rf"[{UP}][{APOS}][{UP}][{LO}]+"
T_UPPER = rf"[{UP}]{{2,}}(?:[{APOS}][{UP}]{{2,}}|[{APOS}](?![{UP}{LO}]))?(?:-[{UP}]{{2,}})?"
T_APO_UP = rf"[{UP}][{APOS}][{UP}]{{2,}}"
TOKEN = rf"(?:{T_APO_UP}|{T_APO}|{T_CAP}|{T_UPPER})"
T_UPPER_ANY = rf"(?:{T_APO_UP}|{T_UPPER})"
# 1-4 tokens on the same line (names never span a line break in our text model).
NAME = rf"{TOKEN}(?:[ \t]+{TOKEN}){{0,3}}"
# Capitalised particles that start a surname: "Dal Bello", "De Marchi", "Della Valle", "Van Dijk".
CAP_PARTICLES = {"da", "dal", "dalla", "dalle", "dai", "de", "del", "della", "dei", "degli", "di", "do", "dos",
                 "du", "la", "le", "lo", "li", "van", "von", "der", "den", "ter", "zu", "mac", "mc", "st"}
# Lower-case particles inside surnames: "van der Berg", "de la Cruz", "di Maria".
PARTICLE = r"(?:van|von|der|den|de|del|della|di|da|dos|du|la|le|zu)"
NAME_WITH_PARTICLES = rf"{TOKEN}(?:[ \t]+(?:{PARTICLE}[ \t]+){{0,2}}{TOKEN}){{0,3}}"

TOKEN_RE = re.compile(TOKEN)


def name_tokens(s: str) -> list[str]:
    return TOKEN_RE.findall(s)


def luhn_ok(digits: str) -> bool:
    total = 0
    for i, c in enumerate(reversed(digits)):
        d = int(c)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def resolve_overlaps(findings: Iterable[Finding], priority: dict[str, int]) -> list[Finding]:
    """Keep non-overlapping findings: higher priority type first, then the more reliable rule
    (operator additions and strong cues before weak ones), then the longer span."""
    ordered = sorted(findings, key=lambda f: (priority.get(f.type, 99), -f.score, -(f.end - f.start), f.start))
    kept: list[Finding] = []
    for f in ordered:
        if all(f.end <= k.start or f.start >= k.end for k in kept):
            kept.append(f)
    return sorted(kept, key=lambda f: f.start)
