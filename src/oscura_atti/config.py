"""Per-organisation configuration: what stays readable, which recognizers run, how labels look."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from pathlib import Path

from . import labels as L

# Action for each entity type:
#   "redact" -> replaced in the PDF by its label (with contextual exceptions for some types)
#   "always" -> replaced in the PDF by its label, no exceptions
#   "flag"   -> left readable but listed in the report for a human decision
#   "keep"   -> left readable and not reported
DEFAULT_POLICY: dict[str, str] = {t: "redact" for t in L.ALL_TYPES}
# VAT numbers, landlines and e-mails are redacted only when they look personal: a VAT number
# near a private person or a sole trader, a landline near a private person, an e-mail that is not
# an office mailbox. Use "always" to redact them without these checks, "flag" or "keep" otherwise.

ACTIONS = ("redact", "always", "flag", "keep")


@dataclass
class Config:
    # Language of labels, stamp and of the word lists used for context (titles, roles).
    language: str = "it"
    # Recognizer packs: "common" (email, IBAN, cards, international phones) + countries.
    packs: list[str] = field(default_factory=lambda: ["common", "it"])
    # Names that always stay readable (mayor, councillors, officials, secretary...).
    public_persons: list[str] = field(default_factory=list)
    # E-mail domains that stay readable (e.g. "comune.example.it").
    public_domains: list[str] = field(default_factory=list)
    # Exact values that stay readable (the organisation's own phone numbers, PEC, IBAN...).
    public_values: list[str] = field(default_factory=list)
    policy: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_POLICY))
    # Label template overrides, e.g. {"PERSON": "Citizen {n}"}.
    labels: dict[str, str] = field(default_factory=dict)
    # Names next to a public role ("Mayor", "Dirigente"...) stay readable but are flagged.
    role_context: bool = True
    # "label": light box with the label; "black": black box with a white label.
    style: str = "label"
    # Footer added to every page; None to disable, "" for the language default.
    stamp: str | None = ""
    ocr: bool = True
    ocr_language: str = "ita"
    # Optional neural NER for names without contextual cues (needs the "ner" extra).
    ner: bool = False
    ner_model: str = "urchade/gliner_multi_pii-v1"
    ner_threshold: float = 0.5

    def label(self, entity_type: str, n: int) -> str:
        template = self.labels.get(entity_type) or L.LABELS.get(self.language, L.LABELS["en"]).get(
            entity_type, entity_type.title() + " {n}")
        return template.format(n=n)

    def short_label(self, entity_type: str, n: int) -> str:
        return L.SHORT_LABELS.get(entity_type, "{n}").format(n=n)

    def stamp_text(self, metadata_only: bool = False) -> str | None:
        if self.stamp is None:
            return None
        if metadata_only:
            return L.STAMPS_METADATA.get(self.language, L.STAMPS_METADATA["en"])
        return self.stamp or L.STAMPS.get(self.language, L.STAMPS["en"])

    @classmethod
    def from_file(cls, path: str | Path) -> "Config":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        known = {f.name for f in fields(cls)}
        conf = cls()
        for key, value in data.items():
            if key.startswith("_"):
                continue   # comments: "_note": "..."
            if key not in known:
                raise ValueError(f"unknown configuration key: {key}")
            if key == "policy":
                for t, action in value.items():
                    if action not in ACTIONS:
                        raise ValueError(f"invalid action {action!r} for {t}; use one of {ACTIONS}")
                conf.policy.update(value)
            elif key == "labels":
                conf.labels.update(value)
            else:
                setattr(conf, key, value)
        if conf.style not in ("label", "black"):
            raise ValueError("style must be 'label' or 'black'")
        return conf
