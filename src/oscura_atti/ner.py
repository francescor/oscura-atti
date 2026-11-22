"""Optional neural NER for people's names without any contextual cue (extra "ner").

Uses a GLiNER model (default `urchade/gliner_multi_pii-v1`, multilingual, Apache-2.0) on CPU.
Findings go through the same clean-up, public-role and organisation checks as the rules, and
need a full name (two tokens) to count; their surnames are then propagated as usual.
Install with `pip install "oscura-atti[ner]"`; the model (~1 GB) is downloaded on first use.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Iterable

from . import labels as L
from .recognizers.base import Finding

_CHUNK_WORDS = 180
_OVERLAP_WORDS = 30


@lru_cache(maxsize=2)
def _model(name: str):
    from gliner import GLiNER   # imported lazily: heavy, optional dependency
    return GLiNER.from_pretrained(name)


def find_people(text: str, model: str = "urchade/gliner_multi_pii-v1", threshold: float = 0.5) -> Iterable[Finding]:
    m = _model(model)
    words = [(w.start(), w.end()) for w in re.finditer(r"\S+", text)]
    seen: set[tuple[int, int]] = set()
    step = _CHUNK_WORDS - _OVERLAP_WORDS
    for k in range(0, max(1, len(words)), step):
        window = words[k:k + _CHUNK_WORDS]
        if not window:
            break
        lo, hi = window[0][0], window[-1][1]
        chunk = text[lo:hi]
        for e in m.predict_entities(chunk, ["person"], threshold=threshold):
            start, end = lo + e["start"], lo + e["end"]
            if (start, end) in seen or "\n" in text[start:end]:
                continue
            seen.add((start, end))
            yield Finding(L.PERSON, start, end, text[start:end], "ner", float(e["score"]))
