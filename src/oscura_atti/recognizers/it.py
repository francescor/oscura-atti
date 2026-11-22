"""Italy: codice fiscale, partita IVA, phone numbers, identity documents, plates, birth data,
home addresses and contextual cues for people's names ("il sig.", "il sottoscritto", "nato a")."""

from __future__ import annotations

import re
from typing import Iterable

from .. import labels as L
from .base import CAP_PARTICLES, LO, NAME_WITH_PARTICLES, T_CAP, T_UPPER_ANY as T_UPPER, UP, Finding
from .given_names import AMBIGUOUS, GIVEN_NAMES
from .words import TITLES

# ------------------------------------------------------------------------------- codice fiscale

_OMOCODIA = "LMNPQRSTUV"   # letters replacing digits in "omocodic" codes
_ODD = {**dict(zip("0123456789", [1, 0, 5, 7, 9, 13, 15, 17, 19, 21])),
        **dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                   [1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23]))}
_EVEN = {**{str(i): i for i in range(10)}, **{c: i for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")}}
_D = f"[0-9{_OMOCODIA}]"
CF_RE = re.compile(rf"(?<![A-Za-z0-9])[A-Za-z]{{6}}{_D}{{2}}[ABCDEHLMPRSTabcdehlmprst]{_D}{{2}}[A-Za-z]{_D}{{3}}[A-Za-z](?![A-Za-z])")


def cf_check_char(first15: str) -> str:
    first15 = first15.upper()
    total = sum(_ODD[c] if i % 2 == 0 else _EVEN[c] for i, c in enumerate(first15))
    return chr(ord("A") + total % 26)


def cf_ok(cf: str) -> bool:
    cf = cf.upper()
    return len(cf) == 16 and CF_RE.fullmatch(cf) is not None and cf_check_char(cf[:15]) == cf[15]


# Typical OCR confusions: letters read as digits and vice versa.
_TO_LETTER = str.maketrans("0125846", "OIZSBAG")
_TO_DIGIT = str.maketrans("OoIlLZSBGQDT", "001112586007")
_CF_LETTER_POS = (0, 1, 2, 3, 4, 5, 8, 11, 15)
CF_LOOSE_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9]{16}(?![A-Za-z])")
_CF_CONTEXT = re.compile(r"(?i:codice\s+fiscale|cod\.\s*fisc\.?|c\.\s?f\.|\bcf\b|tax\s+code|richiedente|dichiarante"
                         r"|intestatari[oa]|contribuente)\s*[:.n°]*\s*$")


def cf_ocr_repair(token: str) -> str:
    """Undo common OCR confusions position by position (letters vs digits)."""
    out = []
    for i, c in enumerate(token.upper()):
        if i in _CF_LETTER_POS:
            out.append(c.translate(_TO_LETTER))
        elif c not in _OMOCODIA:
            out.append(c.translate(_TO_DIGIT))
        else:
            out.append(c)
    return "".join(out)


def find_codici_fiscali(text: str) -> Iterable[Finding]:
    seen: set[int] = set()
    for m in CF_RE.finditer(text):
        if cf_ok(m.group()):
            seen.add(m.start())
            yield Finding(L.TAX_CODE, m.start(), m.end(), m.group(), "it:codice_fiscale")
    # Fallbacks for OCR text: repaired code with a valid check character, or any 16-character
    # token right after "codice fiscale"/"C.F." (an act would not print anything else there).
    for m in CF_LOOSE_RE.finditer(text):
        if m.start() in seen:
            continue
        token = m.group()
        if not (any(c.isdigit() for c in token) and sum(c.isalpha() for c in token) >= 6):
            continue
        if cf_ok(cf_ocr_repair(token)):
            seen.add(m.start())
            yield Finding(L.TAX_CODE, m.start(), m.end(), token, "it:codice_fiscale_ocr", 0.9)
        elif _CF_CONTEXT.search(text[max(0, m.start() - 25):m.start()]):
            seen.add(m.start())
            yield Finding(L.TAX_CODE, m.start(), m.end(), token, "it:codice_fiscale_context", 0.8)


# ----------------------------------------------------------------------------------- partita IVA

PIVA_RE = re.compile(r"(?<![\d/.,])(?:IT[ ]?)?(\d{11})(?![\d/]|[.,]\d)")


def piva_ok(piva: str) -> bool:
    if len(piva) != 11 or not piva.isdigit() or piva == "0" * 11:
        return False
    total = 0
    for i, c in enumerate(piva[:10]):
        d = int(c)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (10 - total % 10) % 10 == int(piva[10])


def find_partite_iva(text: str) -> Iterable[Finding]:
    for m in PIVA_RE.finditer(text):
        if piva_ok(m.group(1)):
            yield Finding(L.VAT_NUMBER, m.start(), m.end(), m.group(), "it:partita_iva")


# ---------------------------------------------------------------------------------------- phones

_PHONE_CONTEXT = re.compile(
    r"(?i:tel|telefono|telefonico|cell|cellulare|fax|recapito|recapiti|contatto|mobile|whatsapp)"
    r"[.:]?\s*(?:n\.?|nr\.?|num\.?|:)?\s*$")
MOBILE_RE = re.compile(r"(?<![\d.,/+])(?:\+39[ .]?|0039[ .]?)?3\d{2}[ .\-/]?\d{3}[ .\-]?\d{3,4}(?!\d|[.,]\d)")
LANDLINE_RE = re.compile(
    r"(?<![\d.,/+])(?:\+39[ .]?|0039[ .]?)?0\d{1,3}[ .\-/]?\d{2,4}[ .\-]?\d{2,4}(?:[ .\-]?\d{2,4})?(?!\d|[.,]\d)")


def find_phones(text: str) -> Iterable[Finding]:
    for m in MOBILE_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        national = digits[2:] if digits.startswith("39") and len(digits) > 10 else digits[4:] if digits.startswith("0039") else digits
        if len(national) == 10:
            yield Finding(L.PHONE, m.start(), m.end(), m.group(), "it:mobile")
    for m in LANDLINE_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        # Landlines only with a cue ("tel.", "fax"): otherwise too easily a protocol number.
        if m.group().startswith(("+39", "0039")) and len(digits) < 10:
            continue
        if re.match(r"/\d{2,4}\b", text[m.end():m.end() + 5]) or re.search(r"(?i:prot|n\.)\W{0,4}$", text[max(0, m.start() - 12):m.start()]):
            continue  # protocol number "0022533/2026", "prot. 0499..."
        if 6 <= len(digits) <= 13 and (m.group().startswith(("+39", "0039"))
                                        or _PHONE_CONTEXT.search(text[max(0, m.start() - 30):m.start()])):
            yield Finding(L.PHONE, m.start(), m.end(), m.group(), "it:landline")


# ------------------------------------------------------------------------- documents and plates

_DOC_CONTEXT = re.compile(
    r"(?i:carta\s+d['’]\s?identit[àa]|c\.\s?i\.|documento(?:\s+di\s+riconoscimento)?|passaporto|patente"
    r"|n\.\s*documento)[^\n]{0,30}$")
ID_DOC_RE = re.compile(r"(?<![A-Z0-9])(?:C[A-Z]\d{5}[A-Z]{2}|[A-Z]{2}\d{7}|\d{7}[A-Z]{2}|[A-Z]{2}\d{6}[A-Z]?|U1[A-Z0-9]{7}[A-Z])(?![A-Z0-9])")
PLATE_RE = re.compile(r"(?<![A-Z0-9])[A-HJ-NPR-Z]{2}[ ]?\d{3}[ ]?[A-HJ-NPR-Z]{2}(?![A-Z0-9])")
_PLATE_CONTEXT = re.compile(r"(?i:targa|targat[oa]|veicolo|autoveicolo|motoveicolo|autovettura|ciclomotore)[^\n]{0,40}$")


def find_documents(text: str) -> Iterable[Finding]:
    for m in ID_DOC_RE.finditer(text):
        if _DOC_CONTEXT.search(text[max(0, m.start() - 60):m.start()]):
            yield Finding(L.ID_DOCUMENT, m.start(), m.end(), m.group(), "it:document")


def find_plates(text: str) -> Iterable[Finding]:
    for m in PLATE_RE.finditer(text):
        if _PLATE_CONTEXT.search(text[max(0, m.start() - 60):m.start()]):
            yield Finding(L.PLATE, m.start(), m.end(), m.group(), "it:plate")


# ---------------------------------------------------------------------------- birth and address

_PLACE_WORD = rf"(?:[{UP}][{LO}{UP}'’.]*|(?:di|del|della|sul|sulla|al|de|san|santa)(?![\w'’])|d['’](?=[{UP}]))"
PLACE = rf"[{UP}][{LO}{UP}'’.]*(?:[ \-]{_PLACE_WORD}){{0,4}}"
_MONTHS = "(?i:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)"
DATE = rf"(?:\d{{1,2}}[./\-]\d{{1,2}}[./\-]\d{{2,4}}|\d{{1,2}}(?:°|º)?\s+{_MONTHS}\s+\d{{4}})"
_PROV = r"(?:\s*\(\s*[A-Z]{2}\s*\)|\s+[A-Z]{2}(?=[\s,]))?"
_NATO = r"(?i:nat[oaei]|nascit[ao])"
_STATE = r"(?:\s*\(\s*[A-Z][a-zA-Z ]+\))?"

BIRTH_RES = [
    # "\s*" after "nato": OCR often glues "nata a" into "nataa"
    re.compile(rf"\b{_NATO}\s*(?P<v>(?i:a|in|ad)\s+{PLACE}{_PROV}{_STATE}\s*,?\s*(?i:il|in\s+data|in\s+data\s+del|l['’])\s*{DATE})"),
    re.compile(rf"\b{_NATO}\s+(?P<v>(?i:il|in\s+data)\s+{DATE}\s*,?\s*(?i:a|in|ad)\s+{PLACE}{_PROV}{_STATE})"),
    re.compile(rf"\b{_NATO}\s+(?P<v>(?i:il|in\s+data)\s+{DATE})"),
    re.compile(rf"\b(?i:data\s+(?:e\s+luogo\s+)?di\s+nascita)\s*[:.]?\s*(?P<v>{DATE}(?:\s*,?\s*(?i:a|in)?\s*{PLACE}{_PROV})?)"),
    re.compile(rf"\b(?i:luogo\s+di\s+nascita)\s*[:.]?\s*(?P<v>{PLACE}{_PROV})"),
]

STREET = (r"(?i:via|viale|v\.le|piazza|p\.zza|p\.za|piazzale|p\.le|vicolo|borgo|corso|c\.so|largo|localit[àa]|loc\."
          r"|strada|str\.|contr[àa]|contrada|riviera|salita|calle|campo|frazione|fraz\.|galleria|lungomare"
          r"|lungofiume|vicoletto|traversa|rampa|stradella|cascina)")
_STREET_WORD = rf"(?:[{UP}0-9][{LO}{UP}0-9'’.\-/]*|(?:di|del|della|dei|degli|delle|da|dal|dalla|san|santa|e|ai|al|alla|alle|sul|sulla)(?![\w'’])|(?:d|sant)['’](?=[{UP}]))"
_HOUSE_NO = r"(?:\s*,?\s*(?i:n\.|n°|nr\.|num\.|civ\.|civico)?\s*\d+(?:\s?[A-Za-z](?![A-Za-z]))?(?:/[A-Za-z0-9]+)?(?:\s*(?i:int\.|interno|sc\.|scala)\s*\w+)*)?"
_CAP = r"(?:\s*[-,]?\s*\d{5}\s+[A-Z][\w'’]*(?:[ \-][A-Z][\w'’]*|\s(?:di|del|della|sul|al)\b){0,4}(?:\s*\(\s*[A-Z]{2}\s*\))?)?"
_RESIDENCE = r"(?i:residente|residenti|domiciliat[oaie]|abitante|abitanti|dimorante|elettivamente\s+domiciliat[oaie]|residenza|domicilio|recapito)"
ADDRESS_RE = re.compile(
    rf"\b{_RESIDENCE}\s*(?i:a|in|ad|presso|:|nel\s+comune\s+di)?\s*"
    rf"(?P<v>(?:{PLACE}{_PROV}\s*[,\-]?\s*(?i:in\s+)?)?{STREET}\s+{_STREET_WORD}(?:[ ]{_STREET_WORD}){{0,6}}{_HOUSE_NO}{_CAP}"
    rf"|{PLACE}{_PROV})")
# "via Rossi 12" right after a person: "Mario Rossi, via Roma 3, Treviso"
ADDRESS_AFTER_NAME_RE = re.compile(
    rf"(?<=,)\s*(?P<v>{STREET}\s+{_STREET_WORD}(?:[ ]{_STREET_WORD}){{0,6}}\s*,?\s*(?i:n\.|n°)?\s*\d+[A-Za-z]?(?:/[A-Za-z0-9]+)?{_CAP})")


_NOT_PLACES = {"comune", "città", "citta", "italia", "provincia", "regione", "territorio", "zona", "area", "sede",
               "stato", "paese", "luogo", "via", "frazione", "località", "localita", "quartiere"}


# Words of form headers ("Luogo di nascita | Data di nascita | Codice fiscale"): not a value.
_FORM_LABELS = {"data", "codice", "fiscale", "residenza", "residente", "qualifica", "cognome", "nome", "indirizzo",
                "telefono", "email", "e-mail", "pec", "comune", "provincia", "prov", "via", "firma", "luogo",
                "nascita", "cittadinanza", "sesso", "stato", "documento", "cap", "recapito", "sede"}


def find_birth(text: str) -> Iterable[Finding]:
    for r in BIRTH_RES:
        for m in r.finditer(text):
            words = re.findall(r"[^\W\d_]+", m.group("v").lower())
            if words and sum(w in _FORM_LABELS for w in words) >= max(1, len(words) // 2) and not re.search(r"\d", m.group("v")):
                continue
            yield Finding(L.BIRTH, m.start("v"), m.end("v"), m.group("v"), "it:birth")


def find_addresses(text: str) -> Iterable[Finding]:
    for m in ADDRESS_RE.finditer(text):
        v = m.group("v").rstrip(" ,.;-")
        # A bare place name after "residente a" is a municipality: personal only with a street.
        verb = m.group(0)[:m.start("v") - m.start()].lower()
        if not re.search(STREET, v):
            if not re.search(r"\b(?:residente|domiciliat[oa]|abitante|dimorante)\b", verb) or \
                    v.split()[0].lower().strip("'’") in _NOT_PLACES:
                continue
            rule = "it:residence_town"
        elif re.search(r"residen[tz]|domiciliat|abitant|dimorant", verb) and not re.search(r"residenza|domicilio", verb):
            rule = "it:address"
        else:
            rule = "it:address_weak"
        yield Finding(L.ADDRESS, m.start("v"), m.start("v") + len(v), v, rule, 1.0 if rule == "it:address" else 0.7)


STREET_ADDRESS_RE = re.compile(
    rf"(?<![\w])(?P<v>{STREET}\s+{_STREET_WORD}(?:[ ]{_STREET_WORD}){{0,6}}\s*,?\s*(?i:n\.|n°|nr\.|civ\.)?\s*\d+(?:\s?[A-Za-z](?![A-Za-z]))?(?:/[A-Za-z0-9]+)?)")


def find_street_addresses(text: str) -> Iterable[Finding]:
    """Any street address with a house number. Personal only next to a private person: the
    engine keeps the others (offices, public buildings, works sites)."""
    for m in STREET_ADDRESS_RE.finditer(text):
        yield Finding(L.ADDRESS, m.start("v"), m.end("v"), m.group("v"), "it:address_weak", 0.5)


def find_addresses_after_names(text: str) -> Iterable[Finding]:
    """Addresses written right after a person's name ("Mario Rossi, via Roma 3")."""
    for m in ADDRESS_AFTER_NAME_RE.finditer(text):
        before = text[max(0, m.start() - 60):m.start()]
        name = re.search(rf"({T_CAP}|{T_UPPER})[ \t]+({T_CAP}|{T_UPPER})\s*,\s*$", before)
        if name and (_given(name.group(1)) or _given(name.group(2))):
            v = m.group("v").rstrip(" ,.;-")
            yield Finding(L.ADDRESS, m.start("v"), m.start("v") + len(v), v, "it:address_after_name", 0.8)


# ---------------------------------------------------------------------------------- people cues

_TITLES = "|".join(TITLES["it"])
PERSON_CUES = [
    # "il sig. Mario Rossi", "dott.ssa ROSSI Maria"
    (re.compile(rf"(?<![\w.])(?i:{_TITLES})\s*[“«\"]?\s*(?P<v>{NAME_WITH_PARTICLES})"), "it:title", 0.9),
    # "il sottoscritto Mario Rossi", "la sottoscritta"
    (re.compile(rf"\b(?i:(?:il|la|i|le)\s+sottoscritt[oaie]\s+(?:(?:{_TITLES})\s*)?)(?P<v>{NAME_WITH_PARTICLES})"),
     "it:undersigned", 0.9),
    # "Mario Rossi, nato a", "ROSSI Mario nata il"
    (re.compile(rf"(?P<v>{NAME_WITH_PARTICLES})\s*,?\s*(?:\([^)]{{0,30}}\)\s*,?\s*)?\b(?i:nat[oa]\s+(?:a|ad|in|il)\b|C\.?\s?F\.?\s*[:.]?\s*[A-Z]{{6}}\d)"),
     "it:born", 0.9),
    # "a favore di Mario Rossi", "nei confronti del sig. ..." (titles are caught above)
    (re.compile(rf"\b(?i:a\s+favore\s+d[ie]l?l?[ao]?|in\s+favore\s+d[ie]l?l?[ao]?|nei\s+confronti\s+d[ie]l?l?[ao]?"
                rf"|intestat[oa]\s+a|eredi\s+d[ie]l?l?[ao]?|richiesta\s+d[ie]l?l?[ao]?|istanza\s+d[ie]l?l?[ao]?"
                rf"|domanda\s+d[ie]l?l?[ao]?|esposto\s+d[ie]l?l?[ao]?|ricorso\s+d[ie]l?l?[ao]?|presentat[oa]\s+da"
                rf"|propriet[àa]\s+d[ie]l?l?[ao]?|proprietari[oa]\s+(?:sig\S*\s+)?|coniuge|figli[oa]|madre|padre"
                rf"|defunt[oa]|de\s+cuius|vedov[oa]|tutore|curatore|amministratore\s+di\s+sostegno\s+(?:di|del|della)?"
                rf"|cittadin[oa]|cittadini|utente|richiedente|istante|ricorrente|esponente|interessat[oa]|dichiarante"
                rf"|proponente|concessionari[oa]|beneficiari[oa]|vicin[oa]|condomin[oa]|inquilin[oa]|locatari[oa]"
                rf"|conduttore|conduttrice|assegnatari[oa]|occupante|trasgressore|contravventore|obbligat[oa]"
                rf"|intestatari[oa]|erede|eredi|sig(?:nor)?\.?(?:ra)?|nominativo|generalit[àa]\s*:?)"
                rf"[ \t]+(?P<v>{T_CAP}[ \t]+{T_CAP}(?:[ \t]+{T_CAP})?|{T_UPPER}[ \t]+{T_CAP}(?:[ \t]+{T_CAP})?|{T_CAP}[ \t]+{T_UPPER})"),
     "it:relation", 0.8),
]
# "ROSSI Mario", "Mario ROSSI", "Mario Rossi" without any cue: accepted only when a token is a
# known given name, and not when the name is part of a street, school or institution name.
# Lookahead patterns: matches may overlap, so "Il Dirigente Paolo Modellaton" also tries "Paolo Modellaton".
SURNAME_FIRST_RE = re.compile(
    rf"(?<![\w'’])(?=(?P<v>{T_UPPER}(?:[ \t]+{T_UPPER})?[ \t]+{T_CAP}(?:[ \t]+{T_CAP})?)(?![\w'’]))")
GIVEN_FIRST_RE = re.compile(
    rf"(?<![\w'’.])(?=(?P<v>{T_CAP}(?:[ \t]+{T_CAP})?[ \t]+(?:(?:De|Di|Da|Dal|Dalla|Del|Della|Dei|Lo|La|Van|Von|D['’])[ \t]*)?(?:{T_CAP}|{T_UPPER}))(?![\w'’]))")
# "Rossi Mario": capitalised surname then a given name (lists, tables).
SURNAME_GIVEN_RE = re.compile(
    rf"(?<![\w'’.])(?=(?P<v>(?:(?:De|Di|Da|Dal|Dalla|Del|Della|Dei|Lo|La|Van|Von|D['’])[ \t]*)?(?P<s>{T_CAP})[ \t]+(?P<g1>{T_CAP})(?:[ \t]+(?P<g2>{T_CAP}))?)(?![\w'’]))")
UPPER_PAIR_RE = re.compile(rf"(?<![\w'’])(?=(?P<v>{T_UPPER}[ \t]+{T_UPPER}(?:[ \t]+{T_UPPER})?)(?![\w'’]))")
NAMED_PLACE = re.compile(
    r"(?i:\b(?:via|viale|v\.le|piazza|p\.zza|piazzale|largo|corso|vicolo|borgo|contr[àa]|strada|riviera|ponte"
    r"|istituto|ist\.|istruz\.?|istruzione|secondaria|superiore|primaria|liceo|scuola|i\.?c\.?|i\.?s\.?i\.?s\.?|i\.?t\.?i\.?s\.?|i\.?t\.?c\.?|i\.?p\.?s\.?i\.?a\.?|i\.?i\.?s\.?"
    r"|i\.?t\.?s\.?|i\.?p\.?s\.?|c\.?f\.?p\.?|ipab|c\.?s\.?|centro\s+servizi|fondazione|parrocchia|chiesa|duomo|ospedale|teatro|premio|villa|palazzo"
    r"|casa|centro|biblioteca|museo|stadio|palestra|palazzetto|asilo|collegio|associazione|circolo|cooperativa"
    r"|intitolat[oa]\s+a|dedicat[oa]\s+a|san|santa|sant['’]|s\.|beato|beata|papa|madonna|corte|galleria|aula|sala"
    r"|auditorium|cinema|parco|giardino|giardini|rotonda|caserma|scuole|plesso|nido|accademia|conservatorio))"
    r"\W{0,3}(?:(?i:don|mons|monsignor|padre|suor|beato|beata|san|santa|card|cardinale|gen|generale|maresciallo"
    r"|dott|prof|ing|avv|cav|on|papa|re|regina|fratelli|f\.lli)\.?\s+|[A-Z]\.\s*)*$")


# Place names whose second word is also a given name.
PLACE_PAIRS = {"reggio emilia", "venezia giulia", "emilia romagna", "san marino", "porto viro", "santa lucia",
               "monte grappa", "piazza armerina", "villa santina", "castel maggiore", "porto tolle", "lido adriano",
               "valle d'aosta", "trentino alto", "colle umberto", "san donà", "ponte giulio", "castel giorgio"}


def _plain(t: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", t)
    return "".join(c for c in t if not unicodedata.combining(c)).lower().strip("'’")


def _given(t: str, strict: bool = False) -> bool:
    p = _plain(t)
    return p in GIVEN_NAMES and not (strict and p in AMBIGUOUS)


def _named_place_before(text: str, m: re.Match) -> bool:
    """A street/school/institution word right before the name, or as its first word ("ISIS DOMENICO")."""
    before = text[max(0, m.start() - 30):m.start()]
    first = m.group("v").split()[0]
    return bool(NAMED_PLACE.search(before) or NAMED_PLACE.search(before + first + " "))


def find_names_by_given_name(text: str) -> Iterable[Finding]:
    """Names without contextual cues, validated with the list of given names."""
    for m in SURNAME_FIRST_RE.finditer(text):
        toks = m.group("v").split()
        caps = [t for t in toks if not t.isupper()]
        if caps and _given(caps[0]) and not _named_place_before(text, m):
            yield Finding(L.PERSON, m.start("v"), m.end("v"), m.group("v"), "it:surname_first", 0.7)
    for m in GIVEN_FIRST_RE.finditer(text):
        toks = m.group("v").split()
        last = _plain(toks[-1])
        if _given(toks[0], strict=True) and len(last) >= 3 and (last not in GIVEN_NAMES or len(toks) >= 3):
            if not _named_place_before(text, m):
                yield Finding(L.PERSON, m.start("v"), m.end("v"), m.group("v"), "it:given_first", 0.65)
    for m in SURNAME_GIVEN_RE.finditer(text):
        surname, g1, g2 = m.group("s"), m.group("g1"), m.group("g2")
        if not _given(g1, strict=True) or _given(surname) or len(_plain(surname)) < 3 \
                or _plain(surname) in CAP_PARTICLES or _named_place_before(text, m) \
                or f"{_plain(surname).split('-')[-1]} {_plain(g1)}" in PLACE_PAIRS or text[max(0, m.start() - 1):m.start()] == "-":
            continue
        end = m.end("g2") if g2 and _given(g2) else m.end("g1")   # "Favaro Anna Maria"
        yield Finding(L.PERSON, m.start("v"), end, text[m.start("v"):end], "it:surname_given", 0.6)
    for m in UPPER_PAIR_RE.finditer(text):
        toks = m.group("v").split()
        given = [i for i, t in enumerate(toks) if _given(t, strict=True)]
        # Part of a longer upper-case sentence ("INCARICO ALL'AVVOCATO ALESSANDRO INVENTARI ...")?
        before = text[max(0, m.start() - 25):m.start()]
        after = text[m.end("v"):m.end("v") + 25]
        in_heading = bool(re.search(rf"{T_UPPER}[ \t'’\"“«]+$", before) or re.match(rf"[ \t'’\"”»]+{T_UPPER}", after))
        if len(given) == 1 and given[0] in (0, len(toks) - 1) and len(toks) >= 2 and not in_heading:
            if not _named_place_before(text, m):
                yield Finding(L.PERSON, m.start("v"), m.end("v"), m.group("v"), "it:upper_name", 0.6)


find_names_by_given_name.uses_lines = True


def find_person_cues(text: str) -> Iterable[Finding]:
    for regex, rule, score in PERSON_CUES:
        for m in regex.finditer(text):
            if rule == "it:relation" and not any(_given(t) for t in m.group("v").split()):
                continue
            yield Finding(L.PERSON, m.start("v"), m.end("v"), m.group("v"), rule, score)


find_person_cues.uses_lines = True

RECOGNIZERS = [find_codici_fiscali, find_partite_iva, find_phones, find_documents, find_plates,
               find_birth, find_addresses, find_addresses_after_names, find_street_addresses, find_person_cues,
               find_names_by_given_name]
