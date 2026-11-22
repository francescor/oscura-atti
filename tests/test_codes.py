"""Structured identifiers: check digits, formats, OCR tolerance, context rules."""

import pytest

from oscura_atti.recognizers import common, eu, it, uk
from oscura_atti.synthetic import italian_iban, piva, tax_code
import random


def types(findings):
    return [(f.type, f.text) for f in findings]


# ------------------------------------------------------------------------------ codice fiscale

VALID_CF = tax_code("SMPRST71D03Z999")


def test_cf_check_char_known_example():
    # Example from the Agenzia delle Entrate documentation format (invented person).
    assert it.cf_ok(VALID_CF)
    assert not it.cf_ok(VALID_CF[:15] + ("A" if VALID_CF[15] != "A" else "B"))


@pytest.mark.parametrize("cf", [VALID_CF, VALID_CF.lower()])
def test_cf_found_any_case(cf):
    found = list(it.find_codici_fiscali(f"codice fiscale {cf}, residente"))
    assert [f.text for f in found] == [cf]


def test_cf_omocodia():
    # Omocodic code: digits replaced by letters LMNPQRSTUV in the numeric positions.
    base = "SMPRSTL1D03Z999"  # 7 -> L in the year
    cf = tax_code(base)
    assert it.cf_ok(cf)
    assert list(it.find_codici_fiscali(cf))


def test_cf_wrong_check_not_found_without_context():
    bad = VALID_CF[:15] + ("Z" if VALID_CF[15] != "Z" else "Y")
    assert not list(it.find_codici_fiscali(f"protocollo {bad} del"))


def test_cf_wrong_check_found_with_context():
    bad = VALID_CF[:15] + ("Z" if VALID_CF[15] != "Z" else "Y")
    found = list(it.find_codici_fiscali(f"C.F. {bad}"))
    assert found and found[0].rule == "it:codice_fiscale_context"


def test_cf_ocr_confusions_repaired():
    ocr = VALID_CF.replace("0", "O", 1)  # digit zero read as letter O
    found = list(it.find_codici_fiscali(f"... {ocr} ..."))
    assert found and found[0].rule == "it:codice_fiscale_ocr"


def test_cf_trailing_ocr_digit():
    found = list(it.find_codici_fiscali(f"fiscale {VALID_CF}1, e che"))
    assert found and found[0].text.startswith(VALID_CF)


def test_cf_not_inside_longer_word():
    assert not list(it.find_codici_fiscali("X" + VALID_CF))


# --------------------------------------------------------------------------------- partita IVA

def test_piva():
    rng = random.Random(3)
    for _ in range(50):
        p = piva(rng)
        assert it.piva_ok(p)
        assert [f.text for f in it.find_partite_iva(f"P.IVA {p} ")] == [p]
    assert not it.piva_ok("01234567890")
    assert not it.piva_ok("00000000000")


def test_piva_not_in_amounts_or_dates():
    assert not list(it.find_partite_iva("euro 12.345678901,00"))


# ---------------------------------------------------------------------------------------- IBAN

def test_iban_valid_and_grouped():
    rng = random.Random(5)
    for _ in range(30):
        iban = italian_iban(rng)
        grouped = " ".join(iban[i:i + 4] for i in range(0, len(iban), 4))
        for form in (iban, grouped):
            found = list(common.find_ibans(f"IBAN {form} intestato"))
            assert [f.text for f in found] == [form]


def test_iban_followed_by_upper_word():
    iban = italian_iban(random.Random(1))
    grouped = " ".join(iban[i:i + 4] for i in range(0, len(iban), 4))
    found = list(common.find_ibans(f"{grouped} PRESSO BANCA"))
    assert [f.text for f in found] == [grouped]


@pytest.mark.parametrize("iban", ["DE89370400440532013000", "GB82WEST12345698765432", "FR1420041010050500013M02606",
                                  "ES9121000418450200051332", "NL91ABNA0417164300"])
def test_iban_other_countries(iban):
    assert common.iban_ok(iban)
    assert list(common.find_ibans(iban))


def test_iban_invalid_without_context_ignored():
    assert not list(common.find_ibans("codice IT00X0542811101000000123456 pratica"))


def test_iban_ocr_noise_with_context():
    iban = italian_iban(random.Random(2))
    noisy = iban[:10] + "8" + iban[10:]   # one extra digit read by OCR
    found = list(common.find_ibans(f"IBAN {noisy} - euro 12"))
    assert found and found[0].rule == "iban:context"


# -------------------------------------------------------------------------------- e-mail, cards

def test_email():
    assert types(common.find_emails("scrivere a mario.rossi+x@example.co.uk.")) == [("EMAIL", "mario.rossi+x@example.co.uk")]


def test_card_needs_luhn_and_context():
    assert list(common.find_cards("carta di credito 4111 1111 1111 1111"))
    assert not list(common.find_cards("protocollo 4111 1111 1111 1111"))
    assert not list(common.find_cards("carta 4111 1111 1111 1112"))


def test_international_phone():
    found = list(common.find_intl_phones("call +44 20 7946 0958 now"))
    assert found and found[0].text == "+44 20 7946 0958"


# -------------------------------------------------------------------------------- Italian phones

@pytest.mark.parametrize("text,value", [
    ("cell. 333 1234567,", "333 1234567"),
    ("cellulare 333-123-4567", "333-123-4567"),
    ("tel. 0499 123411", "0499 123411"),
    ("telefono: 049/8275111", "049/8275111"),
    ("+39 347 1234567", "+39 347 1234567"),
])
def test_it_phones(text, value):
    assert value in [f.text for f in it.find_phones(text)]


def test_landline_without_context_ignored():
    assert not list(it.find_phones("prot. n. 0499 123411 del"))


def test_amount_not_phone():
    assert not list(it.find_phones("euro 345.123,45"))


# ------------------------------------------------------------------------- documents and plates

def test_plate_needs_context():
    assert [f.text for f in it.find_plates("veicolo targato AB123CD abbandonato")] == ["AB123CD"]
    assert not list(it.find_plates("codice AB123CD"))


def test_identity_card():
    assert [f.text for f in it.find_documents("carta d'identità n. CA12345AB rilasciata")] == ["CA12345AB"]


# ----------------------------------------------------------------------------- birth, address

@pytest.mark.parametrize("text,value", [
    ("nato a Treviso (TV) il 03/04/1971,", "a Treviso (TV) il 03/04/1971"),
    ("nata il 5 maggio 1980 a Villa Inventata,", "il 5 maggio 1980 a Villa Inventata"),
    ("nato a San Prova di Sotto il 1/2/1950", "a San Prova di Sotto il 1/2/1950"),
    ("nata in data 02.03.1961", "in data 02.03.1961"),
    ("data di nascita: 12/12/1999", "12/12/1999"),
])
def test_birth(text, value):
    assert value in [f.text for f in it.find_birth(text)]


@pytest.mark.parametrize("text,value", [
    ("residente in Borgo Fittizio, via dei Campi 12/A, codice", "Borgo Fittizio, via dei Campi 12/A"),
    ("residente a Paese in via Giuseppe Verdi 70 C, risulta", "Paese in via Giuseppe Verdi 70 C"),
    ("domiciliato in viale della Repubblica n. 5 int. 3,", "viale della Repubblica n. 5 int. 3"),
    ("residente in via XX Settembre 27 - 31033 Castelnuovo (TV)", "via XX Settembre 27 - 31033 Castelnuovo (TV)"),
])
def test_address(text, value):
    assert value in [f.text for f in it.find_addresses(text)]


def test_address_after_name():
    found = list(it.find_addresses_after_names("Mario Rossi, via Roma 3, Treviso"))
    assert found and found[0].text.startswith("via Roma 3")


# ------------------------------------------------------------------------ other countries

def test_uk_nino_and_nhs():
    assert [f.text for f in uk.find_ninos("NI number QQ 12 34 56 C ")] == []  # QQ is not a valid prefix
    assert [f.text for f in uk.find_ninos("NI number AB 12 34 56 C ")] == ["AB 12 34 56 C"]
    assert uk.nhs_ok("943 476 5919")
    assert [f.text for f in uk.find_nhs("NHS number 943 476 5919")] == ["943 476 5919"]
    assert not list(uk.find_nhs("order 943 476 5919"))


def test_uk_address_and_phone():
    assert list(uk.find_uk_addresses("lives at 10 Downing Street, London, SW1A 2AA"))
    assert list(uk.find_uk_phones("mobile 07700 900123"))


def test_spain_dni_nie():
    assert eu.dni_ok("12345678", "Z")
    assert [f.text for f in eu.find_dni_nie("DNI 12345678Z")] == ["12345678Z"]
    assert [f.text for f in eu.find_dni_nie("NIE X1234567L")] == ["X1234567L"]
    assert not list(eu.find_dni_nie("DNI 12345678A"))


def test_france_nir():
    # Example NIR with a valid key (invented).
    body = "1850578006084"
    key = 97 - int(body) % 97
    nir = f"{body}{key:02d}"
    assert list(eu.find_nir(f"NIR {nir}"))
    assert not list(eu.find_nir(f"NIR {body}{(key + 1) % 97:02d}"))


def test_germany_steuer_id():
    assert eu.steuer_id_ok("86095742719")
    assert list(eu.find_steuer_id("Steuer-ID 86095742719"))
    assert not list(eu.find_steuer_id("Bestellnummer 86095742719"))


def test_ocr_variants_of_a_tax_code_on_other_pages():
    import pymupdf
    from oscura_atti import engine
    doc = pymupdf.open()
    bad1 = VALID_CF[:6] + VALID_CF[6:12] + "7" + VALID_CF[12:]          # extra digit
    bad2 = VALID_CF[:2] + "O" + VALID_CF[3:] if VALID_CF[2] != "O" else VALID_CF[:2] + "Q" + VALID_CF[3:]
    for v in (VALID_CF, bad1, bad2):
        doc.new_page().insert_text((60, 80), f"Data: 08/10/2026 - Richiedente: {v}")
    out, rep = engine.redact(doc.tobytes())
    text = " ".join(p.get_text() for p in pymupdf.open(stream=out, filetype="pdf"))
    assert VALID_CF not in text and bad1 not in text and bad2 not in text


def test_form_headers_are_not_birth_data():
    assert not list(it.find_birth("Luogo di nascita Data di Nascita Codice Fiscale"))
    assert not list(it.find_birth("LUOGO DI NASCITA RESIDENZA CODICE FISCALE QUALIFICA"))
    assert list(it.find_birth("luogo di nascita: Treviso"))


def test_nine_digit_codes_are_not_mobiles():
    assert not list(it.find_phones("codice 366325-531 del"))


def test_birth_with_ocr_glued_words():
    assert [f.text for f in it.find_birth("della defunta Lucia Zanin, nataa Villa Inventata il 05/02/1993;")] == \
        ["a Villa Inventata il 05/02/1993"]
