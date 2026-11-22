"""Spain, France and Germany: national identification numbers with check digits and the
courtesy titles that precede names. Smaller packs than Italy's: contributions welcome."""

from __future__ import annotations

import re
from typing import Iterable

from .. import labels as L
from .base import NAME_WITH_PARTICLES, Finding
from .words import TITLES

# ------------------------------------------------------------------------------------- Spain

_DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
DNI_RE = re.compile(r"(?<![A-Z0-9])(\d{8})[ -]?([A-Z])(?![A-Z0-9])")
NIE_RE = re.compile(r"(?<![A-Z0-9])([XYZ])[ -]?(\d{7})[ -]?([A-Z])(?![A-Z0-9])")


def dni_ok(number: str, letter: str) -> bool:
    return _DNI_LETTERS[int(number) % 23] == letter


def find_dni_nie(text: str) -> Iterable[Finding]:
    for m in DNI_RE.finditer(text):
        if dni_ok(m.group(1), m.group(2)):
            yield Finding(L.TAX_CODE, m.start(), m.end(), m.group(), "es:dni")
    for m in NIE_RE.finditer(text):
        if dni_ok(str("XYZ".index(m.group(1))) + m.group(2), m.group(3)):
            yield Finding(L.TAX_CODE, m.start(), m.end(), m.group(), "es:nie")


# ------------------------------------------------------------------------------------ France

# NIR (numéro de sécurité sociale): sex, year, month, department (2A/2B for Corsica), commune, order, key.
NIR_RE = re.compile(r"(?<![\dA-Z])([12])[ ]?(\d{2})[ ]?(0[1-9]|1[0-2]|[2-9]\d)[ ]?(\d{2}|2[AB])[ ]?(\d{3})[ ]?(\d{3})[ ]?(\d{2})(?![\d])")


def nir_ok(m: re.Match) -> bool:
    dept = m.group(4).replace("2A", "19").replace("2B", "18")
    body = int(m.group(1) + m.group(2) + m.group(3) + dept + m.group(5) + m.group(6))
    return 97 - body % 97 == int(m.group(7))


def find_nir(text: str) -> Iterable[Finding]:
    for m in NIR_RE.finditer(text):
        if nir_ok(m):
            yield Finding(L.TAX_CODE, m.start(), m.end(), m.group(), "fr:nir")


# ----------------------------------------------------------------------------------- Germany

STEUER_ID_RE = re.compile(r"(?<!\d)([1-9]\d)[ ]?(\d{3})[ ]?(\d{3})[ ]?(\d{3})(?!\d)")
_STEUER_CONTEXT = re.compile(r"(?i:steuer[\-\s]?(?:id|identifikationsnummer)|idnr|identifikationsnummer)[^\n]{0,25}$")


def steuer_id_ok(number: str) -> bool:
    """ISO 7064 MOD 11,10 check digit, plus the "one digit repeated 2-3 times" rule."""
    if len(number) != 11 or number[0] == "0":
        return False
    counts = [number[:10].count(c) for c in set(number[:10])]
    if not (max(counts) in (2, 3) and counts.count(1) >= 7):
        return False
    product = 10
    for c in number[:10]:
        total = (int(c) + product) % 10 or 10
        product = (total * 2) % 11
    check = 11 - product
    return (0 if check == 10 else check) == int(number[10])


def find_steuer_id(text: str) -> Iterable[Finding]:
    for m in STEUER_ID_RE.finditer(text):
        number = "".join(m.groups())
        if steuer_id_ok(number) and _STEUER_CONTEXT.search(text[max(0, m.start() - 50):m.start()]):
            yield Finding(L.TAX_CODE, m.start(), m.end(), m.group(), "de:steuer_id")


# ------------------------------------------------------------------------------ title cues

def _title_finder(lang: str):
    regex = re.compile(rf"(?<![\w.])(?i:{'|'.join(TITLES[lang])})[ \t]+(?P<v>{NAME_WITH_PARTICLES})")

    def find(text: str) -> Iterable[Finding]:
        for m in regex.finditer(text):
            yield Finding(L.PERSON, m.start("v"), m.end("v"), m.group("v"), f"{lang}:title", 0.9)

    find.__name__ = f"find_{lang}_titles"
    find.uses_lines = True
    return find


ES = [find_dni_nie, _title_finder("es")]
FR = [find_nir, _title_finder("fr")]
DE = [find_steuer_id, _title_finder("de")]
