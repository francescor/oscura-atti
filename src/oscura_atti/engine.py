"""The core: find personal data, group it into entities, assign labels, redact.

Pipeline:
  1. text of the PDF (OCR for scanned pages)                -> pdf.extract_text
  2. recognizers (rules with check digits and context; optional NER)
  3. clean-up of person mentions (cut non-name words, drop organisations)
  4. grouping: "Mario Rossi", "ROSSI Mario", "Rossi" -> the same Person
  5. propagation: every other occurrence of that person's surname in the document
  6. decision per entity: redact / flag / keep (public persons, public roles, operator choices)
  7. labels numbered per type in order of first appearance, restarting at 1 for each document
  8. rewrite the PDF and verify that redacted text can no longer be extracted

The mapping between values and labels only exists in memory during the call and in the
report returned to the caller (when `include_values`): the service never stores it.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

import pymupdf

from . import __version__
from . import labels as L
from .config import Config
from .pdf import DocumentText, Replacement, apply, boxes, extract_text, ocr_textpage
from .recognizers import PRIORITY, Finding, recognizers_for, resolve_overlaps
from .recognizers.base import CAP_PARTICLES, TOKEN, name_tokens
from .recognizers.given_names import GIVEN_NAMES
from .recognizers.it import NAMED_PLACE
from .recognizers.words import NOT_NAMES, ORGANISATION_MARKERS, ROLES, SENSITIVE


def normalise(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.replace("’", "'")).strip().lower()


class _Lexicon:
    """Language-dependent word lists compiled once per configuration."""

    def __init__(self, conf: Config):
        langs = list(dict.fromkeys([conf.language, *[p for p in conf.packs if p in NOT_NAMES], "en"]))
        self.not_names = {normalise(w) for lang in langs for w in NOT_NAMES.get(lang, "").split()}
        roles = [r for lang in langs for r in ROLES.get(lang, [])]
        self.roles = re.compile(r"(?i:\b(?:" + "|".join(roles) + r"))")
        sens = [r for lang in langs for r in SENSITIVE.get(lang, [])]
        self.sensitive = re.compile(r"(?i:" + "|".join(sens) + ")") if sens else None
        self.organisation_after = re.compile(rf"^[ \t]*[,&]?[ \t]*(?i:{ORGANISATION_MARKERS})(?![\w])")
        self.organisation_before = re.compile(
            r"(?i:\b(?:ditta|impresa|societ[àa]|studio|azienda|agenzia|cooperativa|consorzio|associazione"
            r"|fondazione|farmacia|hotel|albergo|ristorante|bar|banca|istituto|scuola|liceo|parrocchia"
            r"|carrozzeria|officina|autofficina|pizzeria|trattoria|osteria|panificio|macelleria|ferramenta"
            r"|tabaccheria|edicola|autoscuola|autotrasporti|trasporti|impianti|costruzioni|edilizia|onoranze"
            r"|company|firm|messrs)\b)(?:[ \t]+(?:di|del|della|dei|f\.lli|fratelli))?[ \t\"'“«]*$"
            r"|(?i:\b(?:s\.?n\.?c|s\.?a\.?s|s\.?r\.?l|s\.?p\.?a|snc|sas|srl|spa)\.?)[ \t]+(?i:di|dei)[ \t]+$")

    def token_key(self, s: str) -> frozenset[str]:
        out = set()
        for t in name_tokens(s):
            k = normalise(t).strip("'")
            if k and k not in self.not_names and len(k) > 1:
                out.add(k)
        return frozenset(out)


_NAMED_THING = re.compile(
    r"(?i:\b(?:ist\.|istituto|istruz|associazione|fondazione|premio|concorso|borsa\s+di\s+studio|scuola|istituto|liceo|centro|circolo"
    r"|museo|biblioteca|teatro|sala|aula|via|piazza|viale|largo|parco|giardino|stadio|palestra|torneo|trofeo|memorial"
    r"|festival|rassegna|progetto|mostra|coro|banda|gruppo|club|societ[àa]|cooperativa|comitato|amici)\b)")

# Between a role word and a name, these mean the name belongs to someone else.
_BREAKS = re.compile(
    r"[;]|\.\s+[A-Z]|\n\s*\n|(?i:\b(?:domanda|istanza|richiesta|favore|carico|confronti|ricorso|esposto|nota"
    r"|segnalazione|proprietari[oa]|cittadin[oa]|cittadini|utente|richiedente|istante|ricorrente|esponente"
    r"|interessat[oa]|vicin[oa]|defunt[oa]|coniuge|figli[oa]|erede|eredi|beneficiari[oa]|concessionari[oa]"
    r"|request|application|complaint|behalf|against|resident|applicant|citizen)\b)")
_ABBREVIATIONS = re.compile(r"(?i:\b(?:sig|sigg|dott|dr|avv|geom|ing|arch|rag|prof|p\.\s?i|mr|mrs|ms)\.(?:ssa|ra)?)")


@dataclass
class Mention:
    start: int
    end: int
    text: str
    rule: str


@dataclass
class Entity:
    type: str
    key: frozenset[str] | str
    mentions: list[Mention] = field(default_factory=list)
    action: str = "redact"
    reason: str = ""
    review: bool = False
    label: str = ""
    short_label: str = ""

    @property
    def first(self) -> int:
        return min(m.start for m in self.mentions)


@dataclass
class Analysis:
    entities: list[Entity]
    pages: int
    ocr_pages: list[int]
    unanalysed_pages: list[int]
    warnings: list[str]
    sensitive_terms: list[str]

    def report(self, include_values: bool = True) -> dict:
        items = []
        for e in self.entities:
            item = {"label": e.label or None, "type": e.type, "action": e.action, "reason": e.reason,
                    "review": e.review, "mentions": len(e.mentions),
                    "rules": sorted({m.rule for m in e.mentions})}
            if include_values:
                item["values"] = sorted({m.text for m in e.mentions})
            items.append(item)
        needs_review = (bool(self.unanalysed_pages) or any(e.review for e in self.entities)
                        or any(e.action == "flag" for e in self.entities) or bool(self.sensitive_terms))
        return {
            "oscura_atti": __version__,
            "pages": self.pages,
            "ocr_pages": self.ocr_pages,
            "unanalysed_pages": self.unanalysed_pages,
            "entities": items,
            "redacted_entities": sum(1 for e in self.entities if e.action == "redact"),
            "sensitive_terms": self.sensitive_terms,
            "warnings": self.warnings,
            "outcome": "review" if needs_review else "ok",
        }


# --------------------------------------------------------------------------- person clean-up

def _clean_person(text: str, f: Finding, lex: _Lexicon) -> Finding | None:
    """Cut the mention at the first non-name word; drop organisations and lone common words."""
    spans = [(m.start(), m.end()) for m in re.finditer(TOKEN, text[f.start:f.end])]
    kept: list[tuple[int, int]] = []
    for s, e in spans:
        raw = text[f.start + s:f.start + e]
        word = normalise(raw).strip("'")
        if word in lex.not_names:
            # A capitalised particle followed by another name token starts a surname ("Dal Bello").
            nxt = [sp for sp in spans if sp[0] > e]
            if (word in CAP_PARTICLES and raw[:1].isupper() and nxt
                    and text[f.start + e:f.start + nxt[0][0]].strip(" \t") == ""
                    and normalise(text[f.start + nxt[0][0]:f.start + nxt[0][1]]).strip("'") not in lex.not_names):
                kept.append((s, e))
                continue
            if kept:
                break
            continue   # leading non-name word: skip it
        kept.append((s, e))
    if not kept:
        return None
    start, end = f.start + kept[0][0], f.start + kept[-1][1]
    # Keep lower-case particles in between ("van der Berg") by taking the whole span.
    value = text[start:end]
    if lex.organisation_after.search(text[end:end + 25]) or lex.organisation_before.search(text[max(0, start - 30):start]):
        return None
    if not lex.token_key(value):
        return None
    before = re.sub(r"(?i:\b(?:ing|dott|avv|prof|arch|geom|sig|cav|on)\.(?:ssa|ra)?\s*)+$", "", text[max(0, start - 15):start])
    if (re.search(r"[“«\"]\s*$", before) and re.match(r"\s*[”»\"]", text[end:end + 3])
            and _NAMED_THING.search(text[max(0, start - 80):start])):
        return None   # "Associazione “Ing. Mario Rossi”", premio “Mario Rossi”: a thing named after someone
    # Rules without a strong cue need a full name (two tokens) after the clean-up.
    if f.rule.endswith(("surname_first", "given_first", "upper_name", "surname_given", "relation", "ner")) and len(kept) < 2:
        return None
    return Finding(f.type, start, end, value, f.rule, f.score)


# ------------------------------------------------------------------------------------ grouping

def _group_people(findings: list[Finding], lex: _Lexicon) -> list[Entity]:
    """Merge mentions of the same person; longer mentions act as reference."""
    entities: list[Entity] = []
    for f in sorted(findings, key=lambda f: (-len(lex.token_key(f.text)), f.start)):
        key = lex.token_key(f.text)
        if not key:
            continue
        candidates = [e for e in entities if key <= e.key or e.key <= key]
        if not candidates:
            # OCR misreadings ("ZORMELON Sarae"): every token within one edit of the other's.
            candidates = [e for e in entities if _fuzzy_subset(key, e.key) or _fuzzy_subset(e.key, key)]
        mention = Mention(f.start, f.end, f.text, f.rule)
        if len(candidates) == 1:
            e = candidates[0]
            e.mentions.append(mention)
            if len(key) > len(e.key):
                e.key = key
        elif not candidates:
            entities.append(Entity(L.PERSON, key, [mention]))
        else:
            # "Rossi" with two different Rossi in the document: attach to the first, flag both.
            e = min(candidates, key=lambda e: e.first)
            e.mentions.append(mention)
            for c in candidates:
                c.review = True
                c.reason = "ambiguous mention shared by several people with the same name"
    return entities


def _fuzzy_subset(small: frozenset[str], big: frozenset[str]) -> bool:
    if not small or len(small) > len(big):
        return False
    return all(any(t == u or (len(t) >= 4 and _within_one_edit(t, u)) for u in big) for t in small) \
        and sum(1 for t in small if t in big) >= 1


def _surname_forms(e: Entity, lex: _Lexicon) -> set[str]:
    """Forms of the surname to look for in the rest of the document."""
    forms: set[str] = set()
    for m in e.mentions:
        toks = [t for t in name_tokens(m.text) if normalise(t).strip("'") not in lex.not_names]
        # Never propagate a given name alone ("Francesco" would hit every Francesco).
        non_given = [t for t in toks if normalise(t).strip("'") not in GIVEN_NAMES] or toks
        upper = [t for t in non_given if t.isupper() and len(t) > 1]
        chosen = upper if upper and len(upper) < len(toks) else non_given[-1:]
        for t in chosen:
            base = t.rstrip("'’")
            if len(base) >= 3:
                forms.add(base)
                forms.add(base.upper())
                # "ROSSI" -> "Rossi", "D'AMICO" -> "D'Amico", "DE-LUCA" -> "De-Luca"
                forms.add(re.sub(r"[^\W\d_]+", lambda w: w.group()[0].upper() + w.group()[1:].lower(), base))
    return forms


_WEAK_RULES = ("surname_first", "given_first", "upper_name", "surname_given", "ner")


def _edit_distance(a: str, b: str, limit: int = 2) -> int:
    """Levenshtein distance, giving up (returning limit + 1) beyond `limit`."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        if min(cur) > limit:
            return limit + 1
        prev = cur
    return prev[-1]


def _ocr_variants_of_codes(text: str, others: dict) -> None:
    """OCR reads the same tax code differently on different pages ("PSQ..." / "PSO...", an extra
    digit): tokens within two edits of a code already found belong to it."""
    codes = {key: e for (etype, key), e in others.items() if etype == L.TAX_CODE and len(key) == 16}
    if not codes:
        return
    taken = [(m.start, m.end) for e in others.values() for m in e.mentions]
    for m in re.finditer(r"(?<![A-Za-z0-9])[A-Za-z0-9]{14,18}(?![A-Za-z0-9])", text):
        tok = m.group().upper()
        if tok in codes or any(not (m.end() <= a or m.start() >= b) for a, b in taken):
            continue
        if sum(c.isalpha() for c in tok) < 5 or sum(c.isdigit() for c in tok) < 3:
            continue
        for key, e in codes.items():
            if _edit_distance(tok, key) <= 2:
                e.mentions.append(Mention(m.start(), m.end(), m.group(), "it:codice_fiscale_variant"))
                break


def _named_organisation(e: Entity, text: str, lex: "_Lexicon") -> bool:
    """A name that somewhere in the document is followed by a legal form ("GIUSEPPE FANTASINI SOCIETÀ
    COOPERATIVA", also across a page break) is an organisation everywhere in it."""
    if any(m.rule in ("operator",) or not m.rule.endswith(_WEAK_RULES + ("relation",)) for m in e.mentions):
        return False   # strong cues (titles, "nato a", "il sottoscritto") mean a person
    for value in {m.text for m in e.mentions if len(name_tokens(m.text)) >= 2}:
        pattern = r"\s+".join(map(re.escape, value.split()))
        for m in re.finditer(pattern, text, re.I):
            after = re.sub(r"\s*\f?\s*(?i:pagina\s+\d+\s+di\s+\d+)?\s*", " ", text[m.end():m.end() + 60], count=1)
            if lex.organisation_after.search(after) or lex.organisation_before.search(text[max(0, m.start() - 40):m.start()]):
                return True
    return False


def _common_words_only(e: Entity, text: str) -> bool:
    """A weak-rule 'person' whose other words are ordinary lower-case words in this text
    ("PUNTEGGIO MASSIMO": punteggio appears in lower case) is not a person."""
    if not all(m.rule.endswith(_WEAK_RULES) for m in e.mentions):
        return False
    others = [t for t in e.key if t not in GIVEN_NAMES]
    return bool(others) and all(
        re.search(rf"(?<![\w'’.@]){re.escape(t)}(?![\w@]|\.\w)", text) for t in others)


def _propagate(text: str, entities: list[Entity], occupied: list[tuple[int, int]], lex: _Lexicon) -> None:
    def free(i: int, j: int) -> bool:
        return all(j <= a or i >= b for a, b in occupied)

    forms_of = {id(e): _surname_forms(e, lex) for e in entities}
    shared: set[str] = set()
    seen: dict[str, int] = {}
    for e in entities:
        for f in {normalise(x) for x in forms_of[id(e)]}:
            if f in seen and seen[f] != id(e):
                shared.add(f)
            seen[f] = id(e)

    def weak_only(e: Entity) -> bool:
        return all(m.rule.endswith(_WEAK_RULES) for m in e.mentions)

    for e in sorted(entities, key=lambda e: -len(e.key)):
        for form in sorted(forms_of[id(e)], key=len, reverse=True):
            # Found only by weak rules and also written in lower case elsewhere ("punteggio"): a common
            # word, not a surname. People found by strong cues (titles, "nato a"...) propagate anyway.
            if weak_only(e) and re.search(rf"(?<![\w'’.@]){re.escape(form.lower())}(?![\w@]|\.\w)", text):
                continue
            if normalise(form) in shared:
                e.review = True
                e.reason = e.reason or "surname shared with another person: other mentions not propagated"
                continue
            for m in re.finditer(rf"(?<![\w'’]){re.escape(form)}(?![\w])", text):
                i, j = m.start(), m.end()
                # Extend over adjacent given names of the same person ("Mario" in "Mario Rossi").
                # (never into another mention: "Dei Prototti Francesco Dei Prototti Francesco" are two)
                used = {normalise(m.group()).strip("'")}
                while True:
                    before = re.search(rf"({TOKEN})(?:[ \t]+|[ \t]*\n[ \t]*)$", text[max(0, i - 40):i])
                    if not before:
                        break
                    word = normalise(before.group(1)).strip("'")
                    new_i = i - (len(text[max(0, i - 40):i]) - before.start())
                    if word in used or not free(new_i, i) or not (
                            word in e.key or (word in CAP_PARTICLES and before.group(1)[:1].isupper())):
                        break
                    used.add(word)
                    i = new_i
                while True:
                    after = re.match(rf"(?:[ \t]+|[ \t]*\n[ \t]*)({TOKEN})", text[j:j + 40])   # also across a wrap
                    if not after:
                        break
                    word = normalise(after.group(1)).strip("'")
                    # OCR glues words ("Arben e" -> "Arbene"): one edit away from a token still counts
                    in_key = word in e.key or (len(word) >= 4 and any(_within_one_edit(word, k) for k in e.key if len(k) >= 4))
                    if word in used or not in_key or not free(j, j + after.end()):
                        break
                    used.add(word)
                    j += after.end()
                # Not inside a street or school name, also when the given name sits on the previous
                # line ("ISIS DOMENICO / INVENTATI").
                before_txt = text[max(0, i - 60):i]
                for _ in range(2):
                    tail = re.search(rf"({TOKEN})\s+$", before_txt)
                    if tail and normalise(tail.group(1)).strip("'") in e.key:
                        before_txt = before_txt[:tail.start()]
                is_org = bool(lex.organisation_after.search(text[j:j + 40])
                              or re.match(rf"(?:[ \t]+{TOKEN}){{1,2}}[ \t]*[,&]?[ \t]*(?i:{ORGANISATION_MARKERS})(?![\w])", text[j:j + 60])
                              or lex.organisation_before.search(text[max(0, i - 30):i]))
                if free(i, j) and not is_org and not NAMED_PLACE.search(before_txt):
                    e.mentions.append(Mention(i, j, text[i:j], "propagation"))
                    occupied.append((i, j))


def _within_one_edit(a: str, b: str) -> bool:
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]


def _propagate_fuzzy(text: str, entities: list[Entity], occupied: list[tuple[int, int]],
                     ranges: list[tuple[int, int]], lex: _Lexicon) -> None:
    """On OCR pages a surname may be misread by one character ("Zormel0n"): match those too."""
    if not ranges:
        return
    forms: dict[str, set[int]] = {}
    for e in entities:
        for f in _surname_forms(e, lex):
            if len(f) >= 6:
                forms.setdefault(normalise(f), set()).add(id(e))
    if not forms:
        return
    by_id = {id(e): e for e in entities}
    for lo, hi in ranges:
        for m in re.finditer(r"[^\W\d_][\w'’]{4,}", text[lo:hi]):
            i, j = lo + m.start(), lo + m.end()
            if not m.group()[:1].isupper():
                continue
            if any(not (j <= a or i >= b) for a, b in occupied):
                continue
            word = normalise(m.group())
            if word in lex.not_names:
                continue
            owners = {o for f, ids in forms.items() if _within_one_edit(word, f) for o in ids}
            if len(owners) == 1:
                e = by_id[owners.pop()]
                e.mentions.append(Mention(i, j, text[i:j], "propagation:ocr"))
                occupied.append((i, j))


# Function mailboxes and public-body domains: an e-mail like these is not personal data.
_GENERIC_LOCAL = re.compile(
    r"^(?:info|segreteria|protocollo|personale|ufficio|uff|economato|urp|pec|servizi|servizio|settore|tributi"
    r"|anagrafe|statocivile|elettorale|sindaco|sindaca|comune|amministrazione|contabilita|ragioneria|tecnico"
    r"|lavoripubblici|llpp|ambiente|cultura|biblioteca|scuola|istruzione|polizialocale|poliziamunicipale|vigili"
    r"|suap|sue|edilizia|urbanistica|appalti|gare|contratti|direzione|presidenza|privacy|dpo|rpd|legale|posta"
    r"|mail|postmaster|noreply|no-reply|staff|cimiteri|sociale|servizisociali|patrimonio|messi)"
    r"(?:[._-]\w+)*$")
_PUBLIC_DOMAIN = re.compile(
    r"(?:^|[.@])(?:comune|comuni|provincia|regione|prefettura|aulss\d*|ulss\d*|asl\w*|ats\w*|inps|inail"
    r"|agenziaentrate|istruzione|camcom|pecveneto|carabinieri|poliziadistato|vigilfuoco|giustizia|mef|interno"
    r"|cittametropolitana)\b"
    r"|\.(?:gov\.it|gov\.uk|gob\.es|gouv\.fr|bund\.de|edu\.it|europa\.eu|nhs\.uk|police\.uk)$")
_ORG_ACCOUNT = re.compile(
    r"(?i:\b(?:tesoreria|contabilit[àa]\s+speciale|banca\s+d['’]italia|intestat[oa]\s+(?:al|alla|all['’])\s*(?:ministero|comune"
    r"|regione|provincia|agenzia|ente|azienda|istituto|universit[àa]|societ[àa]|ditta|impresa|cooperativa|associazione"
    r"|fondazione|consorzio)|s\.?r\.?l\.?|s\.?p\.?a\.?|soc\.?\s*coop)(?!\w))")
_SENTENCE_BREAK = re.compile(r";|(?<=[a-zà-ÿ]{3})\.\s+[A-Z]|\n\s*\n")
_OFFICE = re.compile(
    r"(?i:\b(?:ufficio|uffici|servizio|servizi|settore|centralino|urp|sportello|comando|segreteria|protocollo"
    r"|per\s+informazioni|informazioni|orari|reception|switchboard|office|council)\b)")
_SOLE_TRADER = re.compile(r"(?i:ditta\s+individuale|impresa\s+individuale|libero\s+professionista|professionista"
                          r"|lavoratore\s+autonomo|sole\s+trader|titolare\s+della\s+ditta)")


_FREE_MAIL = re.compile(
    r"(?:^|\.)(?:gmail|googlemail|libero|hotmail|outlook|live|msn|yahoo|ymail|alice|tin|tiscali|virgilio|icloud"
    r"|me|email|fastwebnet|aruba|pec|legalmail|postecert|gmx|web|proton|protonmail|orange|free|wanadoo|btinternet"
    r"|sky|bigpond|t-online|freenet|telefonica|movistar)\.[a-z.]+$")


def _starts_with_given_name(chunk: str) -> bool:
    from .recognizers.given_names import AMBIGUOUS, GIVEN_NAMES
    chunk = chunk.lower()
    return any(chunk.startswith(g) and len(chunk) - len(g) >= 3 for g in GIVEN_NAMES if len(g) >= 4 and g not in AMBIGUOUS)


def _personal_email(local: str, domain: str) -> bool:
    from .recognizers.given_names import GIVEN_NAMES
    if _GENERIC_LOCAL.match(local):
        return False
    parts = [x for x in re.split(r"[._\-0-9]+", local) if x]
    if any(p in GIVEN_NAMES for p in parts) or any(_starts_with_given_name(p) for p in parts):
        return True
    first_label = domain.split(".")[0]
    if _starts_with_given_name(first_label) or first_label in GIVEN_NAMES:
        return True   # mt@mariorossi.it: a personal domain
    if _FREE_MAIL.search(domain) and not _PUBLIC_DOMAIN.search("@" + domain):
        return True   # any non-generic address at a free-mail or PEC provider
    return len(parts) >= 2 and not _PUBLIC_DOMAIN.search("@" + domain)


def _contextual_decisions(text: str, people: list[Entity], others: dict, lex: _Lexicon) -> None:
    """Values that are personal only near a private person: landlines, office e-mails, VAT numbers."""
    private_spans = [(m.start, m.end) for e in people if e.action == "redact" for m in e.mentions]

    def private_nearby(start: int, window: int) -> bool:
        """A private person's mention shortly before, in the same sentence."""
        for a, b in private_spans:
            if start - window <= b <= start:
                if not re.search(_SENTENCE_BREAK, text[b:start]):
                    return True
            elif start < a <= start + 20:
                return True
        return False

    def private_after(end: int, window: int) -> bool:
        """A private person's mention right after (e.g. next table column), same sentence."""
        for a, _b in private_spans:
            if end <= a <= end + window and not re.search(_SENTENCE_BREAK, text[end:a]):
                return True
        return False

    def office_cue(start: int) -> bool:
        return bool(_OFFICE.search(text[max(0, start - 70):start]))

    for (etype, key), e in others.items():
        if e.action != "redact" or e.reason.startswith("always"):
            continue
        if etype == L.EMAIL:
            local, _, domain = key.lower().partition("@")
            if not _personal_email(local, domain):
                e.action, e.reason = "keep", "office or organisation e-mail"
        elif etype == L.PHONE and all(m.rule == "it:landline" for m in e.mentions):
            if all(office_cue(m.start) for m in e.mentions) or not any(private_nearby(m.start, 200) for m in e.mentions):
                e.action, e.reason = "keep", "office landline (no private person nearby)"
        elif etype == L.IBAN:
            m0 = e.mentions[0]
            around = text[max(0, m0.start - 150):m0.end + 100]
            if (_ORG_ACCOUNT.search(around) and not any(private_nearby(m.start, 300) for m in e.mentions)):
                e.action, e.reason = "keep", "account of an organisation or public body"
        elif etype == L.ADDRESS and all(m.rule == "it:address_weak" for m in e.mentions):
            if not any(private_nearby(m.start, 250) or private_after(m.end, 80) for m in e.mentions):
                e.action, e.reason = "keep", "address of an office or building (no private person nearby)"
        elif etype == L.VAT_NUMBER:
            if not any(private_nearby(m.start, 150) or _SOLE_TRADER.search(text[max(0, m.start - 150):m.start])
                       for m in e.mentions):
                e.action, e.reason = "keep", "VAT number of an organisation"


_LIST_MARKERS = {"p", "a", "ag", "as", "g", "pr", "pres", "ass", "presente", "presenti", "assente", "assenti",
                 "giustificato", "giustificata", "e", "ed", "vice", "sindaco", "sindaca", "assessore", "assessora",
                 "consigliere", "consigliera", "presidente"}
_LIST_TOKEN = re.compile(r"[^\W\d_][\w'’\-]*|\d+|\S")


def _only_names_between(between: str) -> bool:
    """True when the text holds only names, presence marks and punctuation (linear scan)."""
    for tok in _LIST_TOKEN.findall(between):
        if not tok[0].isalnum() or tok.isdigit() or tok.lower() in _LIST_MARKERS or tok[0].isupper():
            continue
        return False
    return True


def _role_in_context(text: str, m: Mention, lex: _Lexicon) -> str | None:
    before = _ABBREVIATIONS.sub(lambda x: " " * len(x.group()), text[max(0, m.start - 120):m.start])
    for r in lex.roles.finditer(before):
        between = before[r.end():]
        if not _BREAKS.search(between) and len(name_tokens(between)) <= 8:
            return r.group().strip()
    # A list of names under a heading: "Sono presenti i Consiglieri Comunali: ROSSI Mario; ..."
    wide = text[max(0, m.start - 1500):m.start]
    heads = list(re.finditer(r"(?i:\b(?:consiglieri|assessori|componenti|membri|presenti|councillors|members)\b[^\n:]{0,40}:)", wide))
    if heads:
        h = heads[-1]
        between = wide[h.end():]
        if _only_names_between(between) and not _BREAKS.search(between.replace(";", ",").replace(":", ",")):
            return h.group().rstrip(":").strip()
    after = text[m.end:m.end + 60]
    r = re.match(r"[ \t]*[-–,(]?[ \t]*(?:(?:la|il|lo|l['’]|in\s+quanto|quale|nella\s+(?:sua\s+)?qualit[àa]\s+di"
                 r"|in\s+qualit[àa]\s+di|nominat[oa]|designat[oa])\s*)*(" + lex.roles.pattern + ")", after)
    if r:
        return r.group(1).strip()
    return None


# -------------------------------------------------------------------------------------- analysis

def analyse_document(doc: pymupdf.Document, conf: Config, add: list[str] | None = None,
                     keep: list[str] | None = None) -> tuple[Analysis, DocumentText]:
    dt = extract_text(doc, ocr=conf.ocr, ocr_language=conf.ocr_language)
    return _analyse(dt, len(doc), conf, add, keep), dt


def _fix_ocr_initial_l(text: str, dt: DocumentText) -> str:
    """OCR reads a capital I at the start of a word as l ("Ioana" -> "loana"). On OCR pages, turn it
    back when the result is a known given name. Same length, so offsets and boxes are unchanged."""
    if not dt.ocr_pages:
        return text
    chars = list(text)
    for m in re.finditer(r"(?<![\w'’])l([a-zà-ÿ]{2,})(?![\w])", text):
        info = dt.chars[m.start()] if m.start() < len(dt.chars) else None
        if info is not None and info.page + 1 in dt.ocr_pages and ("i" + m.group(1)) in GIVEN_NAMES:
            chars[m.start()] = "I"
    fixed = "".join(chars)
    dt.text = fixed
    return fixed


def analyse_text(text: str, conf: Config | None = None, add: list[str] | None = None,
                 keep: list[str] | None = None) -> Analysis:
    """Same analysis on plain text (titles, metadata, e-mails...): no PDF involved."""
    dt = DocumentText(text, [None] * len(text))
    return _analyse(dt, 0, conf or Config(), add, keep)


def redact_text(text: str, conf: Config | None = None, add: list[str] | None = None,
                keep: list[str] | None = None) -> tuple[str, dict]:
    """Return (text with labels, report without values)."""
    analysis = analyse_text(text, conf, add, keep)
    spans = sorted(((m.start, m.end, e.label) for e in analysis.entities if e.action == "redact" for m in e.mentions),
                   reverse=True)
    out = text
    for start, end, label in spans:
        out = out[:start] + label + out[end:]
    return out, analysis.report(include_values=False)


def _analyse(dt: DocumentText, pages: int, conf: Config, add: list[str] | None,
             keep: list[str] | None) -> Analysis:
    lex = _Lexicon(conf)
    text = dt.text

    text = _fix_ocr_initial_l(text, dt)
    # Structured values (codes, phones, addresses) may wrap onto the next line or block: they are
    # searched in a copy where line breaks are spaces (same length, so offsets still match).
    # Name sequences are searched in the original, so table cells never merge into one name.
    flat = text.replace("\n", " ")
    findings: list[Finding] = []
    for recognizer in recognizers_for(conf.packs):
        findings.extend(recognizer(text if getattr(recognizer, "uses_lines", False) else flat))
    if conf.ner:
        from .ner import find_people
        findings.extend(find_people(text, conf.ner_model, conf.ner_threshold))
    cleaned: list[Finding] = []
    for f in findings:
        if f.type == L.PERSON:
            f = _clean_person(text, f, lex)
            if f is None:
                continue
        cleaned.append(f)
    # Operator additions (human review): always people, every exact occurrence.
    for value in add or []:
        if value.strip():
            pattern = r"\s+".join(map(re.escape, value.split()))
            for m in re.finditer(rf"(?<!\w){pattern}(?!\w)", text, re.I):
                cleaned.append(Finding(L.PERSON, m.start(), m.end(), m.group(), "operator", 1.0))
    priority = dict(PRIORITY)
    findings = resolve_overlaps(cleaned, priority)

    people = _group_people([f for f in findings if f.type == L.PERSON], lex)
    others: dict[tuple[str, str], Entity] = {}
    for f in findings:
        if f.type == L.PERSON:
            continue
        if f.type in (L.BIRTH, L.ADDRESS):
            key = normalise(f.text)
        elif f.type == L.EMAIL:
            key = f.text.lower()
        else:
            key = re.sub(r"[\s.\-/()]", "", f.text).upper()
        e = others.setdefault((f.type, key), Entity(f.type, key))
        e.mentions.append(Mention(f.start, f.end, f.text, f.rule))

    _ocr_variants_of_codes(text, others)
    people = [e for e in people if not _common_words_only(e, text) and not _named_organisation(e, text, lex)]
    occupied = [(f.start, f.end) for f in findings if f.type != L.PERSON] + \
               [(m.start, m.end) for e in people for m in e.mentions]
    _propagate(text, people, occupied, lex)
    page_starts = [0] + [i + 1 for i, c in enumerate(text) if c == "\f"]
    ocr_ranges = [(page_starts[p - 1], page_starts[p] if p < len(page_starts) else len(text))
                  for p in dt.ocr_pages if p - 1 < len(page_starts)]
    _propagate_fuzzy(text, people, occupied, ocr_ranges, lex)

    public = [lex.token_key(p) for p in conf.public_persons]
    kept_people = [lex.token_key(x) for x in keep or []]
    kept_values = {normalise(x) for x in keep or []} | {re.sub(r"[\s.\-/()]", "", x).upper() for x in keep or []}
    domains = [d.lower().lstrip("@") for d in conf.public_domains]
    public_values = {re.sub(r"[\s.\-/()]", "", v).upper() for v in conf.public_values}

    def matches(key: frozenset[str], refs: list[frozenset[str]]) -> bool:
        return any(r and (r <= key or (key <= r and len(key) >= 1)) for r in refs)

    for e in people:
        e.action = conf.policy.get(L.PERSON, "redact")
        if e.action == "always":
            e.action, e.reason = "redact", "always redacted (policy)"
            continue
        if any(m.rule == "operator" for m in e.mentions):
            e.reason = "added by the operator"
        elif matches(e.key, kept_people):
            e.action, e.reason = "keep", "kept by the operator"
        elif matches(e.key, public):
            e.action, e.reason = "keep", "public person (configuration)"
        elif conf.role_context:
            for m in e.mentions:
                role = _role_in_context(text, m, lex)
                if role:
                    e.action, e.reason = "keep", f"public role in context: '{role}'"
                    break
    for (etype, key), e in others.items():
        e.action = conf.policy.get(etype, "redact")
        if e.action == "always":
            e.action, e.reason = "redact", "always redacted (policy)"
            continue
        if normalise(e.mentions[0].text) in kept_values or key in kept_values:
            e.action, e.reason = "keep", "kept by the operator"
        elif etype == L.EMAIL and any(key.lower().endswith("@" + d) or key.lower().endswith("." + d) for d in domains):
            e.action, e.reason = "keep", "public domain (configuration)"
        elif key in public_values:
            e.action, e.reason = "keep", "public value (configuration)"
        elif any(m.rule == "it:residence_town" for m in e.mentions):
            e.review = True
            e.reason = "town of residence without street: check whether it identifies the person"

    _contextual_decisions(text, people, others, lex)

    entities = sorted(people + list(others.values()), key=lambda e: e.first)
    counters: dict[str, int] = {}
    for e in entities:
        e.mentions.sort(key=lambda m: m.start)
        if e.action == "keep":
            continue
        counters[e.type] = counters.get(e.type, 0) + 1
        e.label = conf.label(e.type, counters[e.type])
        e.short_label = conf.short_label(e.type, counters[e.type])

    private_spans = [(m.start, m.end) for e in entities if e.type == L.PERSON and e.action == "redact" for m in e.mentions]
    sensitive = sorted({normalise(m.group()) for m in lex.sensitive.finditer(text)
                        if any(abs(m.start() - a) < 400 for a, _ in private_spans)}) if lex.sensitive else []
    return Analysis(entities, pages, dt.ocr_pages, dt.unanalysed_pages, list(dt.warnings), sensitive)


def analyse(pdf: bytes, conf: Config | None = None, add: list[str] | None = None,
            keep: list[str] | None = None, include_values: bool = True) -> dict:
    conf = conf or Config()
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        if doc.needs_pass:
            raise ValueError("password-protected PDF")
        analysis, _ = analyse_document(doc, conf, add, keep)
    return analysis.report(include_values)


def redact(pdf: bytes, conf: Config | None = None, add: list[str] | None = None,
           keep: list[str] | None = None, include_values: bool = False,
           verify_ocr: bool = True) -> tuple[bytes, dict]:
    """Return (redacted PDF, report)."""
    conf = conf or Config()
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        if doc.needs_pass:
            raise ValueError("password-protected PDF")
        analysis, dt = analyse_document(doc, conf, add, keep)
        if not any(e.action == "redact" for e in analysis.entities):
            if not _personal_data_in_properties(doc, conf):
                # Nothing to redact: the "copy" is the original, byte for byte (same SHA-256, no stamp).
                report = analysis.report(include_values)
                report.update(unchanged=True, changes="none", leaks=[])
                return pdf, report
            analysis.warnings.extend(apply(doc, [], conf.style, conf.stamp_text(metadata_only=True)))
            output = doc.tobytes(garbage=4, deflate=True, clean=True)
            report = analysis.report(include_values)
            report.update(unchanged=False, changes="metadata", leaks=[])
            return output, report
        replacements: list[Replacement] = []
        for e in analysis.entities:
            if e.action != "redact":
                continue
            for m in e.mentions:
                parts = boxes(dt, m.start, m.end)
                # The label goes on the widest piece of a value that wraps onto several lines.
                widest = max(range(len(parts)), key=lambda k: parts[k][1].width) if parts else -1
                for k, (page, rect) in enumerate(parts):
                    if page + 1 in dt.ocr_pages:
                        rect = rect + (-2.0, -1.0, 2.0, 1.0)   # OCR boxes are tight: no glyph fragments left
                    replacements.append(Replacement(page, rect, e.label if k == widest else None,
                                                    e.short_label if k == widest else None))
        analysis.warnings.extend(apply(doc, replacements, conf.style, conf.stamp_text()))
        output = doc.tobytes(garbage=4, deflate=True, clean=True)

    report = analysis.report(include_values)
    report.update(unchanged=False, changes="redacted")
    report["leaks"] = verify(output, analysis, dt.ocr_pages if verify_ocr else [], conf.ocr_language,
                             skip_pages=[] if verify_ocr else dt.ocr_pages)
    if report["leaks"]:
        report["outcome"] = "review"
    return output, report


def _personal_data_in_properties(doc: pymupdf.Document, conf: Config) -> bool:
    """Personal data outside the page text: file properties, XMP, annotations, embedded files."""
    if doc.embfile_count():
        return True
    for page in doc:
        for annot in page.annots() or []:
            info = annot.info or {}
            if (info.get("content") or "").strip() or (info.get("title") or "").strip():
                return True
    meta = doc.metadata or {}
    values = [meta.get(k) or "" for k in ("author", "title", "subject", "keywords")]
    xmp = doc.get_xml_metadata() or ""
    values.append(re.sub(r"<[^>]+>", " ", xmp))
    text = "\n".join(v for v in values if v.strip())
    if not text.strip():
        return False
    # Same rules as the page text (names validated by given names, codes by check digits); public
    # persons of the configuration stay allowed. "Microsoft Office User" is not a person.
    probe = conf.__class__(**{**conf.__dict__, "role_context": False, "ocr": False})
    analysis = analyse_text(text, probe)
    return any(e.action == "redact" for e in analysis.entities)


def verify(pdf: bytes, analysis: Analysis, ocr_pages: list[int], ocr_language: str = "ita",
           skip_pages: list[int] | None = None) -> list[dict]:
    """Re-read the output and look for redacted values: they must no longer be extractable.
    Scanned pages are OCR'd again, so a value still visible in the image is caught too."""
    texts = []
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        for i, page in enumerate(doc):
            if skip_pages and i + 1 in skip_pages:
                continue
            if i + 1 in ocr_pages:
                try:
                    texts.append(page.get_text(textpage=ocr_textpage(page, ocr_language)))
                except Exception:
                    continue
            else:
                texts.append(page.get_text())
    haystack = normalise(" ".join(texts))
    leaks = []
    for e in analysis.entities:
        if e.action != "redact":
            continue
        for value in sorted({m.text for m in e.mentions}, key=len, reverse=True):
            v = normalise(value)
            if len(v) >= 4 and re.search(rf"(?<!\w){re.escape(v)}(?!\w)", haystack):
                leaks.append({"label": e.label, "type": e.type})
                break
    return leaks
