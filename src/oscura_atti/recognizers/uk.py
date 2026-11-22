"""United Kingdom: National Insurance number, NHS number, phone numbers, postcodes in addresses,
birth dates and courtesy titles before names."""

from __future__ import annotations

import re
from typing import Iterable

from .. import labels as L
from .base import NAME_WITH_PARTICLES, Finding
from .words import TITLES

# NINO: two prefix letters (D, F, I, Q, U, V never; O not second; some pairs never issued), six digits, A-D.
NINO_RE = re.compile(r"(?<![A-Z0-9])(?!BG|GB|KN|NK|NT|TN|ZZ)[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z][ ]?\d{2}[ ]?\d{2}[ ]?\d{2}[ ]?[A-D](?![A-Z0-9])")
NHS_RE = re.compile(r"(?<![\d])\d{3}[ -]?\d{3}[ -]?\d{4}(?!\d)")
_NHS_CONTEXT = re.compile(r"(?i:nhs|health\s+(?:service|care)\s+(?:no|number)|patient)[^\n]{0,30}$")
UK_PHONE_RE = re.compile(r"(?<![\d+])(?:\+44\s?\(?0?\)?\s?|0)(?:7\d{3}|1\d{2,4}|2\d)[ ]?\d{3,4}[ ]?\d{3,4}(?!\d)")
POSTCODE = r"(?:[A-PR-UWYZ][A-HK-Y]?\d[A-Z\d]?\s?\d[ABD-HJLNP-UW-Z]{2})"
_STREET = (r"(?i:street|st\.|road|rd\.|avenue|ave\.|lane|ln\.|drive|dr\.|close|court|ct\.|place|pl\.|square|sq\."
           r"|way|crescent|terrace|gardens|grove|hill|mews|row|walk|park|green|view|rise)")
UK_ADDRESS_RE = re.compile(
    rf"(?<![\w])(?P<v>(?:(?:Flat|Apartment|Unit)\s+\w+,?\s+)?\d{{1,4}}[A-Za-z]?\s+(?:[A-Z][a-z']+\s+){{1,3}}{_STREET}"
    rf"(?:,\s*[A-Z][A-Za-z' ]{{1,30}}){{0,3}}(?:,?\s*{POSTCODE})?)")
BIRTH_RE = re.compile(
    r"(?i:\bborn\s+(?:on\s+)?|date\s+of\s+birth\s*[:.]?\s*|d\.?o\.?b\.?\s*[:.]?\s*)"
    r"(?P<v>\d{1,2}(?:st|nd|rd|th)?\s+(?i:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}"
    r"|\d{1,2}/\d{1,2}/\d{2,4})")

_TITLES = "|".join(TITLES["en"])
TITLE_RE = re.compile(rf"(?<![\w.])(?i:{_TITLES})[ \t]+(?P<v>{NAME_WITH_PARTICLES})")


def nhs_ok(number: str) -> bool:
    d = [int(c) for c in re.sub(r"\D", "", number)]
    if len(d) != 10:
        return False
    check = 11 - sum(v * (10 - i) for i, v in enumerate(d[:9])) % 11
    check = 0 if check == 11 else check
    return check != 10 and check == d[9]


def find_ninos(text: str) -> Iterable[Finding]:
    for m in NINO_RE.finditer(text):
        yield Finding(L.TAX_CODE, m.start(), m.end(), m.group(), "uk:nino")


def find_nhs(text: str) -> Iterable[Finding]:
    for m in NHS_RE.finditer(text):
        if nhs_ok(m.group()) and _NHS_CONTEXT.search(text[max(0, m.start() - 50):m.start()]):
            yield Finding(L.HEALTH_ID, m.start(), m.end(), m.group(), "uk:nhs")


def find_uk_phones(text: str) -> Iterable[Finding]:
    for m in UK_PHONE_RE.finditer(text):
        yield Finding(L.PHONE, m.start(), m.end(), m.group(), "uk:phone")


def find_uk_addresses(text: str) -> Iterable[Finding]:
    for m in UK_ADDRESS_RE.finditer(text):
        yield Finding(L.ADDRESS, m.start("v"), m.end("v"), m.group("v"), "uk:address", 0.8)


def find_uk_birth(text: str) -> Iterable[Finding]:
    for m in BIRTH_RE.finditer(text):
        yield Finding(L.BIRTH, m.start("v"), m.end("v"), m.group("v"), "uk:birth")


def find_uk_titles(text: str) -> Iterable[Finding]:
    for m in TITLE_RE.finditer(text):
        yield Finding(L.PERSON, m.start("v"), m.end("v"), m.group("v"), "uk:title", 0.9)


find_uk_titles.uses_lines = True

RECOGNIZERS = [find_ninos, find_nhs, find_uk_phones, find_uk_addresses, find_uk_birth, find_uk_titles]
