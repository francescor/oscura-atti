"""Names: cues, clean-up, grouping into consistent labels, propagation, public roles."""

import pymupdf
import pytest

from oscura_atti import engine
from oscura_atti.config import Config


def make_pdf(*paragraphs: str, width: float = 475) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    y = 50
    for para in paragraphs:
        rect = pymupdf.Rect(60, y, 60 + width, 800)
        left = page.insert_textbox(rect, para, fontsize=10, fontname="helv")
        y += rect.height - left + 6
    return doc.tobytes()


def people(report):
    return [e for e in report["entities"] if e["type"] == "PERSON"]


def redacted_people(report):
    return [e for e in people(report) if e["action"] == "redact"]


def test_same_person_same_label_across_forms():
    pdf = make_pdf("Vista l'istanza del sig. Mario Rossi, nato a Treviso il 01/02/1960;",
                   "Considerato che ROSSI Mario ha allegato i documenti e che Rossi ha pagato;",
                   "di concedere al sig. Rossi un contributo.")
    r = engine.analyse(pdf)
    red = redacted_people(r)
    assert len(red) == 1
    assert red[0]["label"] == "Persona 1"
    assert set(red[0]["values"]) >= {"Mario Rossi", "ROSSI Mario", "Rossi"}


def test_two_people_two_labels_in_order_of_appearance():
    pdf = make_pdf("Vista l'istanza della sig.ra Anna Bianchi e del sig. Paolo Verdi;",
                   "Verdi e Bianchi sono comproprietari.")
    r = engine.analyse(pdf)
    labels = {e["label"]: e["values"] for e in redacted_people(r)}
    assert "Anna Bianchi" in labels["Persona 1"]
    assert "Paolo Verdi" in labels["Persona 2"]


def test_labels_in_other_languages():
    pdf = make_pdf("Mr John Smith asked the council. Smith was present.")
    r = engine.analyse(pdf, Config(language="en", packs=["common", "uk"]))
    assert redacted_people(r)[0]["label"] == "Person 1"


def test_public_person_from_configuration_kept():
    pdf = make_pdf("La Sindaca dott.ssa Lucia Esemplari e il sig. Mario Rossi.")
    r = engine.analyse(pdf, Config(public_persons=["Lucia Esemplari"], role_context=False))
    by_value = {v: e for e in people(r) for v in e["values"]}
    assert by_value["Lucia Esemplari"]["action"] == "keep"
    assert by_value["Mario Rossi"]["action"] == "redact"


def test_role_in_context_kept_and_flagged():
    pdf = make_pdf("Visto il parere del Dirigente del Settore Tecnico, ing. Marco Tipicelli;")
    r = engine.analyse(pdf)
    p = people(r)[0]
    assert p["action"] == "keep" and "role" in p["reason"]


def test_role_word_does_not_protect_private_person_after_request_word():
    pdf = make_pdf("Il Dirigente, vista la richiesta del sig. Mario Rossi, dispone.")
    r = engine.analyse(pdf)
    assert redacted_people(r) and "Mario Rossi" in redacted_people(r)[0]["values"]


def test_councillor_list_after_heading_is_public():
    pdf = make_pdf("Sono presenti i Consiglieri Comunali:", "ROSSI Mario P; BIANCHI Anna A; VERDI Luca P")
    r = engine.analyse(pdf)
    assert all(e["action"] == "keep" for e in people(r)) and len(people(r)) == 3


def test_citizen_cue():
    pdf = make_pdf("Il Presidente dà la parola al cittadino Francesco Dallonello, che interviene.")
    r = engine.analyse(pdf)
    assert "Francesco Dallonello" in redacted_people(r)[0]["values"]


def test_organisations_are_not_people():
    pdf = make_pdf("La ditta ROSSI COSTRUZIONI S.r.l. e lo studio Bianchi & Verdi; Spett.le Impresa Edile Rossi Srl.")
    r = engine.analyse(pdf)
    assert not redacted_people(r)


def test_capitalised_particle_surnames():
    pdf = make_pdf("Vista l'istanza del sig. Paolo Dal Bello; Dal Bello chiede il rimborso.",
                   "La sig.ra Maria De Marchi e il sig. Luca D'Amico; D'AMICO Luca è presente.")
    r = engine.analyse(pdf)
    values = {v for e in redacted_people(r) for v in e["values"]}
    assert "Paolo Dal Bello" in values and "Dal Bello" in values
    assert "Maria De Marchi" in values
    assert "D'AMICO Luca" in values


def test_sentence_words_cut_from_names():
    pdf = make_pdf("Il sig. Mario Rossi Visto il regolamento comunale;")
    r = engine.analyse(pdf)
    assert redacted_people(r)[0]["values"] == ["Mario Rossi"]


def test_shared_surname_flagged_not_propagated():
    pdf = make_pdf("Il sig. Mario Rossi e la sig.ra Anna Rossi, coniugi; Rossi ha firmato.")
    r = engine.analyse(pdf)
    red = redacted_people(r)
    assert len(red) == 2 and all(e["review"] for e in red)


def test_operator_add_and_keep():
    pdf = make_pdf("Interviene Giulia Ghiotto, poi il sig. Mario Rossi.")
    r = engine.analyse(pdf, add=["Giulia Ghiotto"], keep=["Mario Rossi"])
    by_value = {v: e for e in people(r) for v in e["values"]}
    assert by_value["Giulia Ghiotto"]["action"] == "redact"
    assert by_value["Mario Rossi"]["action"] == "keep"


def test_wrapped_name_still_found():
    pdf = make_pdf("Vista la domanda presentata dalla signora Mariagrazia Pellizzari residente in via Roma 3, "
                   "e considerato che Pellizzari ha diritto al rimborso.", width=150)
    r = engine.analyse(pdf)
    values = {v for e in redacted_people(r) for v in e["values"]}
    assert "Pellizzari" in values


@pytest.mark.parametrize("lang,text", [
    ("es", "Doña María García solicita el reembolso."),
    ("fr", "Madame Claire Dubois demande le remboursement."),
    ("de", "Frau Anna Müller beantragt die Erstattung."),
])
def test_title_cues_other_languages(lang, text):
    pdf = make_pdf(text)
    r = engine.analyse(pdf, Config(language=lang, packs=["common", lang]))
    assert redacted_people(r)


def test_sensitive_terms_flag_document():
    pdf = make_pdf("Contributo economico al sig. Mario Rossi, in condizioni di disagio economico, ISEE 3.000.")
    r = engine.analyse(pdf)
    assert r["sensitive_terms"] and r["outcome"] == "review"


# ------------------------------------------------------------- lessons from real documents
# (each case below reproduces, with invented names, a pattern seen in real municipal acts)

def test_headings_are_not_people():
    pdf = make_pdf("ART. 5 - PROVE D'ESAME", "DISPOSIZIONI FINALI", "COMANDO PROVINCIALE Vigili del Fuoco",
                   "DIFESA CIVILE Beneficiario", "DIVERSI FORNITORI Beneficiario", "SAI Ordinari", "IMPIEGO Quota",
                   "BASE D'APPALTO Esecutivo", "COMMISSIONE ESAMINATRICE La Commissione è nominata")
    assert not redacted_people(engine.analyse(pdf))


def test_name_without_cue_found_by_given_name():
    pdf = make_pdf("Il contributo è assegnato a Elisa Brunfittotto per l'anno 2026.", "Brunfittotto ha accettato.")
    r = engine.analyse(pdf)
    assert {"Elisa Brunfittotto", "Brunfittotto"} <= {v for e in redacted_people(r) for v in e["values"]}


def test_streets_and_schools_named_after_people_kept():
    pdf = make_pdf("Lavori in via Giuseppe Verdi e presso il Liceo Tito Livio e l'Istituto Maria Ausiliatrice; "
                   "concerto in piazza Esempio.")
    assert not redacted_people(engine.analyse(pdf))


def test_officials_from_signature_phrases_kept():
    pdf = make_pdf("con il quale viene confermata al Dott. Gianfranco Fintolato la dirigenza del Settore 2;",
                   "sostituito in caso di assenza o di impedimento dal Dott. Ermes Esempradin;",
                   "Responsabile del procedimento: Dott.ssa Lia Fittonese",
                   "Parere Favorevole", "Dott. Oreste Modellaton", "Il Responsabile della Protezione dei Dati "
                   "designato per il Comune di Esempio è Avv. ODINO FINVELLUTI via Roma 4")
    r = engine.analyse(pdf)
    assert not redacted_people(r), redacted_people(r)


def test_office_contacts_kept_private_contacts_redacted():
    pdf = make_pdf("Per informazioni: Ufficio Economato tel. 0499/123458, economato@comune.esempio.tv.it, "
                   "PEC comune.esempio.tv@pecveneto.it.",
                   "Vista l'istanza del sig. Mario Rossi, tel. 0499 491855, email mario.rossi@gmail.com;")
    r = engine.analyse(pdf)
    by_value = {v: e for e in r["entities"] for v in e["values"]}
    assert by_value["0499/123458"]["action"] == "keep"
    assert by_value["economato@comune.esempio.tv.it"]["action"] == "keep"
    assert by_value["comune.esempio.tv@pecveneto.it"]["action"] == "keep"
    assert by_value["0499 491855"]["action"] == "redact"
    assert by_value["mario.rossi@gmail.com"]["action"] == "redact"


def test_numeric_tax_code_of_organisation_not_a_phone():
    pdf = make_pdf("Comune di Esempio - C.F. 00123450678 - P.IVA 00123450678")
    r = engine.analyse(pdf)
    assert not [e for e in r["entities"] if e["type"] == "PHONE"]


def test_vat_numbers_of_companies_kept_of_sole_traders_redacted():
    from oscura_atti.synthetic import piva
    import random
    a, b = piva(random.Random(1)), piva(random.Random(2))
    pdf = make_pdf(f"Affidamento alla ditta Edilizia Esempio S.r.l., P.IVA {a};",
                   f"Incarico al geom. Mario Rossi, libero professionista, P.IVA {b};")
    r = engine.analyse(pdf)
    by_value = {v: e for e in r["entities"] for v in e["values"]}
    assert by_value[a]["action"] == "keep"
    assert by_value[b]["action"] == "redact"


def test_professional_in_quotes_is_a_person_but_association_name_is_not():
    pdf = make_pdf("di individuare come beneficiario l'operatore economico Ing.«Marco Inventaro», al Capitolo 495000;",
                   "l'Associazione Amici della Storica Lancia «Ing. Ettore Campionari», con sede a Paesello;")
    values = {v for e in redacted_people(engine.analyse(pdf)) for v in e["values"]}
    assert "Marco Inventaro" in values and "Ettore Campionari" not in values


def test_sensitive_terms_ignored_far_from_private_people():
    pdf = make_pdf("Bando di concorso: non possono partecipare i candidati con condanne penali; servizi sociali.")
    r = engine.analyse(pdf)
    assert not r["sensitive_terms"]


def test_redact_plain_text():
    out, rep = engine.redact_text("PUBBLICAZIONE DI MATRIMONIO - sig. Mario Rossi e sig.ra Anna Bianchi; Rossi firma.")
    assert "Mario Rossi" not in out and "Anna Bianchi" not in out and "Rossi firma" not in out
    assert "Persona 1" in out and "Persona 2" in out


def test_street_address_redacted_only_next_to_private_person():
    pdf = make_pdf("Lavori di manutenzione presso la scuola di via Larga n. 12.",
                   "RISTRUTTURAZIONE FABBRICATO - VIA DEI CAMPI DI BORGOFINTO, n. 25 - richiedente sig. Mario Rossi")
    r = engine.analyse(pdf)
    by_value = {v: e for e in r["entities"] for v in e["values"]}
    assert by_value["via Larga n. 12"]["action"] == "keep"
    assert by_value["VIA DEI CAMPI DI BORGOFINTO, n. 25"]["action"] == "redact"


def test_stamp_on_rotated_page_is_visible():
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 100), "Il sig. Mario Rossi chiede.")
    page.set_rotation(90)
    out, _ = engine.redact(doc.tobytes())
    res = pymupdf.open(stream=out, filetype="pdf")[0]
    hits = res.search_for("Documento generato")
    assert hits and all(res.mediabox.contains(h) for h in hits)


def test_name_recognizers_see_line_breaks():
    """Name recognizers must run on the text with line breaks, or names merge across lines."""
    from oscura_atti.recognizers import PACKS
    for pack in PACKS.values():
        for r in pack:
            if ("person" in r.__name__ or "name" in r.__name__ or "title" in r.__name__) and "address" not in r.__name__:
                assert getattr(r, "uses_lines", False), r.__name__


def test_name_does_not_continue_on_next_line():
    pdf = make_pdf("Il Responsabile del procedimento Dott. Emanuele Zanotto", "SIOPE 1234 Parere Contabile")
    r = engine.analyse(pdf)
    for e in people(r):
        assert all("\n" not in v and "SIOPE" not in v for v in e["values"])


def test_false_positives_from_real_acts():
    pdf = make_pdf("Oggetto: ORDINANZA DI SENSO ALTERNATO IN VIA ROMA. IL SENSO UNICO ALTERNATO è istituito.",
                   "incendio presso via don Ernesto Fantasin n. 30; tettoia sita in Via Don E. Fantasin.",
                   "contributi per i minori residenti in Città; Sede / residenza: Comune – CAP – Stato")
    r = engine.analyse(pdf)
    assert not [e for e in r["entities"] if e["action"] == "redact"], r["entities"]


def test_repeated_adjacent_mentions_both_covered():
    pdf = make_pdf("da parte dell'operatore economico Dei Prototti Francesco Dei Prototti Francesco., p.Iva",
                   "all'operatore economico DEI PROTOTTI FRANCESCO con sede legale in via Roma")
    out, rep = engine.redact(pdf)
    text = pymupdf.open(stream=out, filetype="pdf")[0].get_text()
    assert "Rossi" not in text and "ROSSI" not in text and not rep["leaks"]


def test_upper_heading_with_given_name_word_is_not_a_person():
    pdf = make_pdf("TOTALE PUNTEGGIO MASSIMO", "PUNTEGGIO MASSIMO", "il punteggio massimo attribuibile è 100")
    assert not redacted_people(engine.analyse(pdf))


def test_school_names_in_various_forms_kept():
    pdf = make_pdf('0002123 - IST. STAT. DI ISTRUZ. SECONDARIA SUPERIORE "DOMENICO INVENTATI" Debitore:',
                   "2026/14* ISIS DOMENICO", "INVENTATI 2.833,95", "CONTRATTO DI AFFITTO I.S.I.S. DOMENICO INVENTATI, ANNATE")
    assert not redacted_people(engine.analyse(pdf))


def test_name_after_capitalised_role_word():
    pdf = make_pdf("Il Dirigente Paolo Modellaton dispone; Visto Elisa Brunfittotto residente in via Roma 3.")
    r = engine.analyse(pdf)
    by_value = {v: e for e in people(r) for v in e["values"]}
    assert by_value["Paolo Modellaton"]["action"] == "keep"
    assert by_value["Elisa Brunfittotto"]["action"] == "redact"


def test_company_named_like_a_private_person_not_propagated():
    pdf = make_pdf("Vista l'istanza del sig. Mario Rossi; Rossi chiede il contributo.",
                   "Affidamento alla ditta SERGIO ROSSI SOCIETÀ COOPERATIVA SOCIALE e a ROSSI COSTRUZIONI S.r.l.")
    out, rep = engine.redact(pdf)
    text = pymupdf.open(stream=out, filetype="pdf")[0].get_text()
    assert "SERGIO ROSSI" in text and "ROSSI COSTRUZIONI" in text and "Mario Rossi" not in text


def test_company_name_split_by_page_break_and_business_names():
    pdf = make_pdf("affidamento alla ditta GIUSEPPE FANTASINI SOCIETÀ COOPERATIVA SOCIALE;",
                   "a favore di GIUSEPPE FANTASINI", "Pagina 4 di 4", "SOCIETÀ COOPERATIVA SOCIALE",
                   "rimborso al custode acquirente CARROZZERIA DI ROBERTO ESEMPIOTTI; 0020467 - CARROZZERIA DI ROBERTO ESEMPIOTTI Debitore")
    assert not redacted_people(engine.analyse(pdf))


def test_lists_written_surname_given():
    pdf = make_pdf("COMUNE RILEVATORE", "Borgofinto Prototon Lucia", "Paesello Esempiaro Matteo", "Beneficiari: Zanin Bruno; Favaro Anna Maria.")
    values = {v for e in redacted_people(engine.analyse(pdf)) for v in e["values"]}
    assert {"Prototon Lucia", "Esempiaro Matteo", "Zanin Bruno", "Favaro Anna Maria"} <= values, values


def test_place_and_shop_names_are_not_people():
    pdf = make_pdf("ditta RISTORAZIONE ESEMPIO S.C. di Reggio Emilia; lotto 3 - Veneto, Friuli-Venezia Giulia, Trentino;",
                   "fino al civico 29 (“Bar Lucia”); deposito presso Carrozzeria Roberto; marciapiede (Passaggio Dante).")
    assert not redacted_people(engine.analyse(pdf))


def test_partners_named_in_partnership_names_kept():
    pdf = make_pdf("a favore della Ditta Leggendo snc di Fittavola Valeria e Inventini di Vicenza;",
                   "0019971 - LEGGENDO S.N.C. DI FITTAVOLA VALERIA E INVENTINI V.")
    assert not redacted_people(engine.analyse(pdf))
