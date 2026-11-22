"""Recognizer packs. Each pack is a list of functions `text -> Iterable[Finding]`."""

from __future__ import annotations

from .. import labels as L
from . import common, eu, it, uk
from .base import Finding, Recognizer, resolve_overlaps

PACKS: dict[str, list[Recognizer]] = {
    "common": common.RECOGNIZERS,
    "it": it.RECOGNIZERS,
    "uk": uk.RECOGNIZERS,
    "es": eu.ES,
    "fr": eu.FR,
    "de": eu.DE,
}

# On overlap the lower number wins (then the longer span).
PRIORITY = {L.TAX_CODE: 0, L.HEALTH_ID: 1, L.IBAN: 2, L.PAYMENT_CARD: 3, L.EMAIL: 4, L.ID_DOCUMENT: 5,
            L.BIRTH: 6, L.ADDRESS: 7, L.PHONE: 8, L.PLATE: 9, L.VAT_NUMBER: 10, L.PERSON: 11}


def recognizers_for(packs: list[str]) -> list[Recognizer]:
    out: list[Recognizer] = []
    for p in packs:
        if p not in PACKS:
            raise ValueError(f"unknown recognizer pack: {p} (available: {', '.join(PACKS)})")
        out.extend(PACKS[p])
    return out


__all__ = ["Finding", "Recognizer", "PACKS", "PRIORITY", "recognizers_for", "resolve_overlaps"]
