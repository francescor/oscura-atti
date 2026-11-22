"""End-to-end on PDFs: nothing private left in the output, labels in place, metadata scrubbed."""

import shutil

import pymupdf
import pytest

from oscura_atti import engine, service, synthetic
from oscura_atti.bench import output_text, present
from oscura_atti.config import Config

HAS_TESSERACT = shutil.which("tesseract") is not None


@pytest.mark.parametrize("seed", range(12))
def test_no_private_value_left(seed):
    doc = synthetic.generate(seed)
    out, report = engine.redact(doc.pdf)
    text = output_text(out, ocr=False)
    for v in doc.private_values:
        assert not present(v, text), f"leak: {v}"
    for v in doc.public_values:
        assert present(v, text), f"public value lost: {v}"
    assert not report["leaks"]


def test_labels_written_in_document():
    doc = synthetic.generate(1, kind="contribution")
    out, _ = engine.redact(doc.pdf)
    text = output_text(out, ocr=False)
    assert "persona 1" in text and "codice fiscale 1" in text and "iban 1" in text


def test_report_without_values_by_default():
    doc = synthetic.generate(2, kind="contribution")
    _, report = engine.redact(doc.pdf)
    assert all("values" not in e for e in report["entities"])
    for v in doc.private_values:
        assert v not in str(report)


def test_metadata_annotations_and_attachments_removed():
    doc = synthetic.generate(3)
    src = pymupdf.open(stream=doc.pdf, filetype="pdf")
    src.embfile_add("note.txt", b"Mario Rossi secret")
    src[0].add_text_annot((100, 100), "comment by Mario Rossi")
    data = src.tobytes()
    out, _ = engine.redact(data)
    res = pymupdf.open(stream=out, filetype="pdf")
    assert not res.metadata.get("author")
    assert res.embfile_count() == 0
    assert not list(res[0].annots())


def test_stamp_and_black_style():
    doc = synthetic.generate(4)
    out, _ = engine.redact(doc.pdf, Config(style="black", stamp="REDACTED COPY"))
    text = output_text(out, ocr=False)
    assert "redacted copy" in text


def test_no_stamp():
    doc = synthetic.generate(4)
    out, _ = engine.redact(doc.pdf, Config(stamp=None))
    assert "documento generato" not in output_text(out, ocr=False)


def test_password_protected_rejected():
    doc = pymupdf.open()
    doc.new_page().insert_text((50, 50), "secret")
    data = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="x", owner_pw="y")
    with pytest.raises(ValueError):
        engine.redact(data)


def test_not_a_pdf_rejected():
    with pytest.raises(ValueError):
        service.redact(b"hello world, not a pdf")


def test_page_count_and_layout_preserved():
    doc = synthetic.generate(5, layout="narrow")
    out, _ = engine.redact(doc.pdf)
    a = pymupdf.open(stream=doc.pdf, filetype="pdf")
    b = pymupdf.open(stream=out, filetype="pdf")
    assert len(a) == len(b)
    assert [p.rect for p in a] == [p.rect for p in b]


@pytest.mark.skipif(not HAS_TESSERACT, reason="tesseract not installed")
@pytest.mark.parametrize("seed", [0, 7, 19])
def test_scanned_document(seed):
    doc = synthetic.generate(seed)
    scan = synthetic.as_scan(doc.pdf)
    out, report = engine.redact(scan)
    assert report["ocr_pages"]
    text = output_text(out, ocr=True)
    for v in doc.private_values:
        assert not present(v, text), f"leak in scan: {v}"


def test_nothing_to_redact_returns_the_original_bytes():
    doc = pymupdf.open()
    doc.new_page().insert_text((60, 80), "Approvazione del bilancio di previsione 2027-2029. Il Consiglio approva.")
    doc.set_metadata({"author": "Microsoft Office User", "title": "Bilancio"})
    data = doc.tobytes()
    out, report = engine.redact(data)
    assert out == data and report["unchanged"] and report["changes"] == "none"


def test_personal_data_only_in_properties():
    doc = pymupdf.open()
    doc.new_page().insert_text((60, 80), "Approvazione del bilancio di previsione 2027-2029.")
    doc.set_metadata({"author": "Mario Rossi"})
    out, report = engine.redact(doc.tobytes())
    res = pymupdf.open(stream=out, filetype="pdf")
    assert report["changes"] == "metadata" and not res.metadata.get("author")
    assert "proprietà del file" in res[0].get_text()


def test_stamp_wording():
    doc = synthetic.generate(1, kind="contribution")
    out, _ = engine.redact(doc.pdf)
    text = pymupdf.open(stream=out, filetype="pdf")[0].get_text()
    assert "Documento generato dall'originale oscurando i dati personali" in text
    assert "non conforme" not in text


def test_signed_document_without_personal_data_keeps_the_signature():
    from test_p7m_cli_mcp import sign
    doc = pymupdf.open()
    doc.new_page().insert_text((60, 80), "Approvazione del bilancio di previsione 2027-2029.")
    envelope = sign(doc.tobytes())
    out, report = service.redact(envelope)
    assert out == envelope and report["unchanged"] and report["signed_p7m"]
