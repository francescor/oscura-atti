"""INVENTED documents generated on the fly, with ground truth: no real PDF ever enters the repo.

The documents imitate Italian municipal acts (council resolutions, orders, payment decisions,
cemetery concessions, minutes) but organisations, people, tax codes, IBANs and addresses are
invented. Codes carry valid check digits (so recognizers must find them) but match no real
person: birth places use the unassigned cadastral code Z999 and surnames are drawn from very
common names combined at random, or built from syllables.

Each document records which values are private (must disappear) and which are public (must
stay readable), so tests and the benchmark can measure leaks and over-redaction.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

import pymupdf

from .recognizers.it import cf_check_char

FIRST_M = ["Mario", "Giuseppe", "Luca", "Marco", "Andrea", "Francesco", "Paolo", "Giovanni", "Stefano",
           "Alberto", "Davide", "Matteo", "Riccardo", "Enrico", "Fabio", "Roberto", "Sergio", "Bruno",
           "Ernesto", "Gianluigi", "Pierpaolo", "Nicolò", "Elia", "Zeno"]
FIRST_F = ["Maria", "Anna", "Giulia", "Francesca", "Chiara", "Laura", "Elena", "Sara", "Paola", "Silvia",
           "Valentina", "Federica", "Lucia", "Ada", "Rita", "Graziella", "Mariagrazia", "Noemi", "Irene",
           "Beatrice", "Agnese", "Wanda"]
SURNAMES = ["Rossi", "Bianchi", "Zanin", "Favaro", "Pavan", "Bortolato", "Zanella", "Marangon", "Basso",
            "Gallo", "Conte", "De Marchi", "Dal Bello", "Dalla Valle", "D'Amico", "Visentin", "Tonon",
            "Bonaldo", "Furlan", "Barbieri", "Simeoni", "Pellizzari", "Callegaro", "Ceccato", "Martini"]
_SYL = ["bar", "ton", "zan", "mel", "fur", "bor", "dal", "vis", "cec", "pel", "gri", "sar", "lon", "mor",
        "pas", "ret", "tin", "val", "zor", "ber"]
_END = ["etto", "ato", "in", "on", "ello", "ini", "ari", "esan", "otti", "uzzi"]
STREETS = ["via dei Campi", "via Roma", "via Giuseppe Verdi", "viale della Repubblica", "piazza Garibaldi",
           "via San Giorgio", "borgo Treviso", "vicolo del Pozzo", "via XX Settembre", "via Monte Grappa",
           "via Sile", "via Larga"]
TOWNS = ["Borgo Fittizio", "Villa Inventata", "Paese Esempio", "San Prova di Sotto", "Campagna Nuova",
         "Ponte Immaginario"]
ROLES = [("Sindaca", "F"), ("Assessore", "M"), ("Assessora", "F"), ("Dirigente del Settore Tecnico", "M"),
         ("Segretaria Generale", "F"), ("Responsabile del procedimento", "M")]
BANKS = [("05428", "11101"), ("03069", "12345"), ("08399", "61560"), ("02008", "61820")]


def tax_code(first15: str) -> str:
    return first15 + cf_check_char(first15)


def italian_iban(rng: random.Random) -> str:
    abi, cab = rng.choice(BANKS)
    bban = rng.choice("ABCDEFGHIJKLMNOPRSTUVWXYZ") + abi + cab + f"{rng.randrange(10**11):012d}"
    check = 98 - int("".join(str(int(c, 36)) for c in bban + "IT00")) % 97
    return f"IT{check:02d}{bban}"


def piva(rng: random.Random) -> str:
    base = f"{rng.randrange(10**9):09d}1"
    total = 0
    for i, c in enumerate(base):
        d = int(c)
        if i % 2 == 1:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
    return base + str((10 - total % 10) % 10)


def _plain(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).upper()


def _consonants(s: str) -> str:
    return "".join(c for c in _plain(s) if "A" <= c <= "Z" and c not in "AEIOU")


def _vowels(s: str) -> str:
    return "".join(c for c in _plain(s) if c in "AEIOU")


@dataclass
class Person:
    first: str
    last: str
    sex: str
    public: bool = False
    role: str = ""
    birth_day: int = 1
    birth_month: int = 1
    birth_year: int = 1970

    @property
    def full(self) -> str:
        return f"{self.first} {self.last}"

    @property
    def upper_first(self) -> str:
        return f"{self.last.upper()} {self.first}"

    def cf(self) -> str:
        last = (_consonants(self.last) + _vowels(self.last) + "XXX")[:3]
        c = _consonants(self.first)
        first = (c[0] + c[2] + c[3]) if len(c) >= 4 else (c + _vowels(self.first) + "XXX")[:3]
        month = "ABCDEHLMPRST"[self.birth_month - 1]
        day = self.birth_day + (40 if self.sex == "F" else 0)
        return tax_code(f"{last}{first}{self.birth_year % 100:02d}{month}{day:02d}Z999")

    def birth_date(self) -> str:
        return f"{self.birth_day:02d}/{self.birth_month:02d}/{self.birth_year}"


@dataclass
class SyntheticDoc:
    pdf: bytes
    text: str
    private_values: list[str] = field(default_factory=list)   # must disappear
    public_values: list[str] = field(default_factory=list)    # must stay readable
    private_people: int = 0                                   # distinct people to redact
    kind: str = ""


FOREIGN = [("Mamadou", "Diop", "M"), ("Fatou", "Ndiaye", "F"), ("Kwame", "Mensah", "M"), ("Blessing", "Okafor", "F"),
           ("Youssef", "Benali", "M"), ("Latifa", "El Amrani", "F"), ("Arben", "Hoxha", "M"), ("Mirela", "Kola", "F"),
           ("Ionut", "Popescu", "M"), ("Oksana", "Kovalenko", "F"), ("Gurpreet", "Singh", "M"), ("Nasrin", "Akter", "F"),
           ("Imran", "Qureshi", "M"), ("Meiling", "Chen", "F"), ("Osagie", "Igbinosa", "M"), ("Ioana", "Lungu", "F")]


def _person(rng: random.Random, used: set[str], public: bool = False, role: str = "", sex: str | None = None) -> Person:
    if not public and rng.random() < 0.15:
        for _ in range(20):
            first, last, fsex = rng.choice(FOREIGN)
            if last not in used:
                used.add(last)
                return Person(first, last, fsex, public, role, rng.randint(1, 28), rng.randint(1, 12),
                              rng.randint(1950, 2004))
    while True:
        sex = sex or rng.choice("MF")
        first = rng.choice(FIRST_M if sex == "M" else FIRST_F)
        if rng.random() < 0.6:
            last = rng.choice(SURNAMES)
        else:
            last = (rng.choice(_SYL) + rng.choice(_SYL) + rng.choice(_END)).capitalize()
        if last not in used:
            used.add(last)
            return Person(first, last, sex, public, role, rng.randint(1, 28), rng.randint(1, 12),
                          rng.randint(1935, 2004))


def _name_form(rng: random.Random, p: Person, allow_short: bool = True) -> str:
    forms = [p.full, p.upper_first, f"{p.last.upper()} {p.first}"]
    return rng.choice(forms)


def _title(p: Person) -> str:
    return "il sig." if p.sex == "M" else "la sig.ra"


def _born(p: Person) -> str:
    return "nato" if p.sex == "M" else "nata"


def _body(kind: str, rng: random.Random, people: list[Person], officials: list[Person], town: str,
          private: list[str], public: list[str]) -> list[str]:
    a, b = people[0], people[1]
    paras: list[str] = []
    street = rng.choice(STREETS)
    house = f"{rng.randint(1, 120)}{rng.choice(['', '', '/A', '/B', ' C'])}"
    iban = italian_iban(rng)
    iban_txt = " ".join(iban[i:i + 4] for i in range(0, len(iban), 4)) if rng.random() < 0.5 else iban
    mobile = f"3{rng.randint(20, 99)} {rng.randint(1000000, 9999999)}"
    landline = f"04{rng.randint(10, 99)} {rng.randint(100000, 999999)}"
    email = f"{a.first.lower()}.{a.last.lower().replace(' ', '').replace(chr(39), '')}@example.org"
    vat = piva(rng)
    plate = f"{rng.choice('ABCDEFGH')}{rng.choice('ABCDEFGHJKLMNPRSTVWXYZ')}{rng.randint(100, 999)}" \
            f"{rng.choice('ABCDEFGHJKLMNPRSTVWXYZ')}{rng.choice('ABCDEFGHJKLMNPRSTVWXYZ')}"
    a_birthplace = rng.choice(TOWNS)
    a_addr = f"{street} {house}"
    dirigente = officials[3]

    def remember(*values: str) -> None:
        private.extend(v for v in values if v)

    if kind == "contribution":
        form = _name_form(rng, a)
        paras.append(f"Vista l'istanza presentata da{'l sig.' if a.sex == 'M' else 'lla sig.ra'} {form}, "
                     f"{_born(a)} a {a_birthplace} (XX) il {a.birth_date()}, residente in {town}, {a_addr}, "
                     f"codice fiscale {a.cf()}, tel. {landline}, cell. {mobile}, email {email}, con la quale "
                     f"chiede un contributo straordinario per i danni subiti dall'abitazione;")
        remember(form, a.cf(), mobile, landline, email, a.birth_date(), a_addr)
        paras.append(f"Considerato che l'immobile risulta cointestato a{'l sig.' if b.sex == 'M' else 'lla sig.ra'} "
                     f"{b.full}, {_born(b)} il {b.birth_date()} a {rng.choice(TOWNS)}, codice fiscale {b.cf()}, "
                     f"e che {a.last} ha allegato la documentazione fotografica dei danni;")
        remember(b.full, b.cf(), b.birth_date(), a.last)
        paras.append(f"Visto il parere favorevole del {dirigente.role}, ing. {dirigente.full};")
        public.append(dirigente.full)
        paras.append("DELIBERA")
        paras.append(f"1) di concedere a{'l sig.' if a.sex == 'M' else 'lla sig.ra'} {a.full} un contributo di "
                     f"euro {rng.randint(500, 5000)},00 da accreditare sul conto IBAN {iban_txt} intestato al "
                     f"beneficiario;")
        remember(a.full, iban_txt)
        paras.append(f"2) di dare atto che la ditta Edilizia {rng.choice(["Fontanelle", "Belvedere", "Piave", "Sile", "Sile Basso"])} S.r.l., P.IVA {vat}, eseguirà i "
                     f"lavori di ripristino;")
        paras.append(f"3) di trasmettere il presente atto a {a.last.upper()} {a.first} e a {b.last}.")
        remember(f"{a.last.upper()} {a.first}", b.last)
    elif kind == "vehicle_order":
        paras.append(f"Premesso che il veicolo targato {plate}, di proprietà de{'l sig.' if a.sex == 'M' else 'lla sig.ra'} "
                     f"{a.upper_first}, residente a {town} in {a_addr}, risulta in stato di abbandono in "
                     f"{rng.choice(STREETS)} dal {rng.randint(1, 28)}/0{rng.randint(1, 9)}/2026;")
        remember(plate, a.upper_first, a_addr)
        paras.append(f"Vista la segnalazione del Comando di Polizia Locale e la relazione dell'agente "
                     f"{dirigente.full};")
        public.append(dirigente.full)
        paras.append("ORDINA")
        paras.append(f"a {a.full}, codice fiscale {a.cf()}, di rimuovere il veicolo entro 15 giorni dalla "
                     f"notifica. In caso di inottemperanza il veicolo sarà rimosso d'ufficio con spese a carico di "
                     f"{a.last}.")
        remember(a.full, a.cf(), a.last)
    elif kind == "refunds":
        paras.append("Visto l'elenco delle richieste di rimborso della tassa sui rifiuti erroneamente versata:")
        for p in people[:3]:
            amount = f"{rng.randint(20, 400)},{rng.randint(10, 99)}"
            ib = italian_iban(rng)
            paras.append(f"- {p.upper_first} - C.F. {p.cf()} - IBAN {ib} - euro {amount}")
            private.extend([p.upper_first, p.cf(), ib])
        paras.append("DETERMINA")
        paras.append(f"1) di liquidare i rimborsi indicati in premessa; 2) di dare atto che il responsabile "
                     f"del procedimento è il dott. {dirigente.full}.")
        public.append(dirigente.full)
    elif kind == "cemetery":
        paras.append(f"Vista la domanda presentata in data 03/09/2026 da{'l sig.' if a.sex == 'M' else 'lla sig.ra'} "
                     f"{a.full}, residente in {town}, {a_addr}, tel. {mobile}, in qualità di "
                     f"{'figlio' if a.sex == 'M' else 'figlia'} de{'l defunto' if b.sex == 'M' else 'lla defunta'} "
                     f"{b.full}, {_born(b)} a {rng.choice(TOWNS)} il {b.birth_date()};")
        remember(a.full, a_addr, mobile, b.full, b.birth_date())
        paras.append(f"DETERMINA di concedere a {a.last.upper()} {a.first} il loculo n. {rng.randint(1, 400)} del "
                     f"cimitero del capoluogo per la tumulazione della salma di {b.last} {b.first}.")
        remember(f"{a.last.upper()} {a.first}", f"{b.last} {b.first}")
    elif kind == "minutes":
        paras.append("Sono presenti i Consiglieri Comunali:")
        line = "; ".join(f"{o.last.upper()} {o.first}" for o in officials[:4])
        paras.append(line)
        public.extend(f"{o.last.upper()} {o.first}" for o in officials[:4])
        paras.append(f"Il Presidente dà la parola al cittadino {a.full}, intervenuto per l'interrogazione sulla "
                     f"viabilità di {street}, il quale lamenta i rumori provenienti dall'abitazione del vicino "
                     f"{b.upper_first}.")
        remember(a.full, b.upper_first)
        paras.append(f"Risponde la {officials[0].role} {officials[0].full}, che si impegna a verificare.")
        public.append(officials[0].full)
    elif kind == "assignment":
        # Patterns seen in real payment decisions: officials in many forms, organisations named
        # after people, office contacts, signature block, accounting sheet.
        d2 = officials[5]
        paras.append(f"Visto il decreto della Sindaca con il quale viene confermata al Dott. {dirigente.full} la "
                     f"dirigenza del Settore 2, sostituito in caso di assenza o di impedimento dal Dott. {d2.full};")
        public.extend([dirigente.full, d2.full])
        org_person = _person(rng, set())
        paras.append(f"Ritenuto di affidare il servizio alla ditta {org_person.first.upper()} {org_person.last.upper()} "
                     f"SOCIETÀ COOPERATIVA SOCIALE, P.IVA {vat}, con sede in {rng.choice(STREETS)} {rng.randint(1, 50)};")
        public.append(f"{org_person.first.upper()} {org_person.last.upper()}")
        paras.append(f"Vista la richiesta dell'Associazione Amici del Museo «Ing. {org_person.full}» con sede a {town};")
        paras.append(f"Vista l'istanza de{'l sig.' if a.sex == 'M' else 'lla sig.ra'} {a.full}, libero professionista, "
                     f"P.IVA {piva(rng)}, email {a.first.lower()}{a.last.lower().replace(' ', '').replace(chr(39), '')}@gmail.com;")
        remember(a.full)
        paras.append(f"Per informazioni: Ufficio Economato, tel. 0499/123458, economato@comune.esempio.tv.it; "
                     f"Responsabile del procedimento: Dott.ssa {officials[4].full}.")
        public.extend([officials[4].full, "0499/123458", "economato@comune.esempio.tv.it"])
        paras.append("DISPOSIZIONI FINALI")
        paras.append(f"Beneficiario: {rng.randint(10000, 99999)} - {b.upper_first}")
        remember(b.upper_first)
        paras.append(f"Il documento è stato firmato da:")
        paras.append(f"{dirigente.last.upper()} {dirigente.first.upper()} in data 01/10/2026")
        public.append(f"{dirigente.last.upper()} {dirigente.first.upper()}")
    elif kind == "table":
        paras.append("Vista la graduatoria dei beneficiari del contributo per l'affitto, di seguito riportata:")
        paras.append("@TABLE")
        for p in people[:3]:
            private.extend([p.upper_first if upper_table else f"{p.last} {p.first}", p.cf()])
        paras.append(f"Il responsabile del procedimento è il dott. {dirigente.full}.")
        public.append(dirigente.full)
    return paras


upper_table = True
table_names: list[str] = []
KINDS = ["contribution", "vehicle_order", "refunds", "cemetery", "minutes", "assignment", "table"]


def generate(seed: int = 0, kind: str | None = None, layout: str | None = None) -> SyntheticDoc:
    rng = random.Random(seed)
    kind = kind or rng.choice(KINDS)
    layout = layout or rng.choice(["normal", "narrow", "small", "wide"])
    used: set[str] = set()
    officials = [_person(rng, used, True, r, s) for r, s in ROLES]
    people = [_person(rng, used) for _ in range(3)]
    town = rng.choice(TOWNS)
    private: list[str] = []
    public: list[str] = []
    header = [f"COMUNE DI {town.upper()}", "PROVINCIA IMMAGINARIA",
              f"ATTO N. {rng.randint(1, 999)} DEL {rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}/2026",
              "OGGETTO: " + {"contribution": "CONCESSIONE DI CONTRIBUTO STRAORDINARIO.",
                             "vehicle_order": "ORDINANZA DI RIMOZIONE DI VEICOLO IN STATO DI ABBANDONO.",
                             "refunds": "RIMBORSO DI SOMME NON DOVUTE.",
                             "cemetery": "CONCESSIONE DI LOCULO CIMITERIALE.",
                             "minutes": "VERBALE DELLA SEDUTA DEL CONSIGLIO COMUNALE.",
                             "assignment": "AFFIDAMENTO DEL SERVIZIO DI EDUCATIVA DOMICILIARE.",
                             "table": "APPROVAZIONE GRADUATORIA CONTRIBUTI AFFITTO."}[kind]]
    global upper_table, table_names
    upper_table = rng.random() < 0.5
    table_names = [p.upper_first if upper_table else f"{p.last} {p.first}" for p in people]
    body = _body(kind, rng, people, officials, town, private, public)
    sindaca = officials[0]
    footer = [f"La {sindaca.role} {sindaca.full}    La {officials[4].role} Dott.ssa {officials[4].upper_first}"]
    public.extend([sindaca.full, officials[4].upper_first])
    paragraphs = header + body + footer

    width = {"normal": 475, "narrow": 260, "small": 475, "wide": 500}[layout]
    size = {"normal": 10, "narrow": 10, "small": 7.5, "wide": 11}[layout]
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    y = 50.0
    for i, para in enumerate(paragraphs):
        if para == "@TABLE":
            # Columns: N. | COGNOME E NOME | CODICE FISCALE | IMPORTO, each cell its own text box.
            cols = [(60, 85), (90, 260), (265, 400), (405, 480)]
            header = ["N.", "COGNOME E NOME", "CODICE FISCALE", "IMPORTO"]
            rows = [header] + [[str(k + 1), table_names[k], p.cf(), f"{rng.randint(300, 1500)},00"]
                               for k, p in enumerate(people[:3])]
            for row in rows:
                for (x0, x1), cell in zip(cols, row):
                    page.insert_textbox(pymupdf.Rect(x0, y, x1, y + 14), cell, fontsize=8, fontname="helv")
                y += 16
            y += 6
            continue
        bold = i < 4 or para in ("DELIBERA", "DETERMINA", "ORDINA")
        rect = pymupdf.Rect(60, y, 60 + width, 800)
        left = page.insert_textbox(rect, para, fontsize=size + (2 if i < 2 else 0),
                                   fontname="hebo" if bold else "helv")
        if left < 0:  # does not fit: new page
            page = doc.new_page(width=595, height=842)
            y = 50.0
            rect = pymupdf.Rect(60, y, 60 + width, 800)
            left = page.insert_textbox(rect, para, fontsize=size, fontname="hebo" if bold else "helv")
        y += (rect.height - left) + 6
    doc.set_metadata({"author": people[0].full, "title": "Invented act for testing"})
    text = "\n".join(paragraphs)
    private_people = len({v for v in private if v and v[0].isalpha() and " " in v and not v.startswith(("via", "viale", "piazza", "borgo", "vicolo"))})
    return SyntheticDoc(doc.tobytes(), text, [v for v in private if v], public, private_people, kind)


def as_scan(pdf: bytes, dpi: int = 200) -> bytes:
    """Turn a PDF into an image-only PDF, like a scan."""
    src = pymupdf.open(stream=pdf, filetype="pdf")
    out = pymupdf.open()
    for p in src:
        pix = p.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
        page = out.new_page(width=p.rect.width, height=p.rect.height)
        page.insert_image(page.rect, stream=pix.tobytes("png"))
    return out.tobytes(deflate=True)
