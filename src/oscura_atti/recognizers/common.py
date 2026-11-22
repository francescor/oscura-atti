"""Language-independent recognizers: e-mail, IBAN, payment cards, international phone numbers."""

from __future__ import annotations

import re
from typing import Iterable

from .. import labels as L
from .base import Finding, luhn_ok

# ---------------------------------------------------------------------------------------- e-mail

EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}(?![\w-])")


def find_emails(text: str) -> Iterable[Finding]:
    for m in EMAIL_RE.finditer(text):
        yield Finding(L.EMAIL, m.start(), m.end(), m.group(), "email")


# ------------------------------------------------------------------------------------------ IBAN

# Lengths from the SWIFT IBAN registry (EU/EEA, UK, CH and neighbours).
IBAN_LENGTHS = {
    "AD": 24, "AT": 20, "BE": 16, "BG": 22, "CH": 21, "CY": 28, "CZ": 24, "DE": 22, "DK": 18, "EE": 20,
    "ES": 24, "FI": 18, "FO": 18, "FR": 27, "GB": 22, "GI": 23, "GL": 18, "GR": 27, "HR": 21, "HU": 28,
    "IE": 22, "IS": 26, "IT": 27, "LI": 21, "LT": 20, "LU": 20, "LV": 21, "MC": 27, "MT": 31, "NL": 18,
    "NO": 15, "PL": 28, "PT": 25, "RO": 24, "SE": 24, "SI": 19, "SK": 24, "SM": 27, "VA": 22,
}
# Country code + check digits, then groups possibly separated by single spaces or hyphens.
IBAN_CONTEXT = re.compile(r"(?i:iban|conto\s+corrente|c/c|bank\s+account|cuenta|compte|konto)[^\n]{0,15}$")
IBAN_RE = re.compile(r"(?<![A-Z0-9])([A-Z]{2})[ ]?(\d{2})((?:[ -]?[A-Z0-9]){11,30})")


def iban_ok(iban: str) -> bool:
    iban = re.sub(r"[ -]", "", iban).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", iban):
        return False
    expected = IBAN_LENGTHS.get(iban[:2])
    if expected is None or len(iban) != expected:
        return False
    return int("".join(str(int(c, 36)) for c in iban[4:] + iban[:4])) % 97 == 1


def find_ibans(text: str) -> Iterable[Finding]:
    for m in IBAN_RE.finditer(text):
        country = m.group(1)
        if country not in IBAN_LENGTHS:
            continue
        # The regex can swallow letters of the following word: cut at the expected length.
        positions = [m.start() + i for i, c in enumerate(m.group()) if c not in " -"]
        n = IBAN_LENGTHS[country]
        if len(positions) < n:
            if IBAN_CONTEXT.search(text[max(0, m.start() - 30):m.start()]):
                yield Finding(L.IBAN, m.start(), m.end(), m.group(), "iban:context", 0.8)
            continue
        end = positions[n - 1] + 1
        if end < len(text) and text[end].isalnum():
            # A longer alphanumeric run: not a valid IBAN, unless announced by "IBAN" (OCR noise).
            if IBAN_CONTEXT.search(text[max(0, m.start() - 30):m.start()]):
                yield Finding(L.IBAN, m.start(), m.end(), m.group(), "iban:context", 0.8)
            continue
        candidate = text[m.start():end]
        if iban_ok(candidate):
            yield Finding(L.IBAN, m.start(), end, candidate, "iban:mod97")
        elif IBAN_CONTEXT.search(text[max(0, m.start() - 30):m.start()]):
            # OCR text: a digit misread or added breaks the checksum. After the word "IBAN"
            # the whole alphanumeric run is redacted anyway.
            run = re.match(r"[A-Z]{2}\d{2}(?:[ -]?[A-Z0-9]){11,32}", text[m.start():])
            stop = m.start() + len(run.group().rstrip()) if run else end
            yield Finding(L.IBAN, m.start(), stop, text[m.start():stop], "iban:context", 0.8)


# --------------------------------------------------------------------------------- payment cards

CARD_RE = re.compile(r"(?<![\d.,])(?:\d[ -]?){12,18}\d(?![\d.,]\d|\d)")
CARD_CONTEXT = re.compile(r"(?i:carta|card|visa|mastercard|maestro|amex|tarjeta|carte|karte|kreditkarte)")


def find_cards(text: str) -> Iterable[Finding]:
    for m in CARD_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19 and luhn_ok(digits) and digits[0] in "23456" \
                and CARD_CONTEXT.search(text[max(0, m.start() - 40):m.start()]):
            yield Finding(L.PAYMENT_CARD, m.start(), m.end(), m.group(), "card:luhn")


# ----------------------------------------------------------------------- international phone numbers

INTL_PHONE_RE = re.compile(r"(?<![\w+])(?:\+|00)(?:[1-9]\d{0,2})(?:[ .\-/]?\(?\d+\)?){2,6}(?!\d)")


def find_intl_phones(text: str) -> Iterable[Finding]:
    for m in INTL_PHONE_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        # "00" + digits with no separator is usually a numeric tax code (e.g. 00123450678), not a phone.
        if m.group().startswith("00") and not re.search(r"[ .\-/()]", m.group()):
            continue
        if 9 <= len(digits) <= 15:
            yield Finding(L.PHONE, m.start(), m.end(), m.group().rstrip(" .-/"), "phone:international")


RECOGNIZERS = [find_emails, find_ibans, find_cards, find_intl_phones]
