"""Other formats: images, office documents, text."""

import shutil
import subprocess

import pymupdf
import pytest

from oscura_atti import service, synthetic
from oscura_atti.bench import output_text, present
from oscura_atti.convert import UnsupportedFormat, to_pdf

HAS_SOFFICE = shutil.which("soffice") is not None
HAS_TESSERACT = shutil.which("tesseract") is not None


def test_text_file():
    out, rep = service.redact_file("Il sig. Mario Rossi, nato a Treviso il 01/02/1960.".encode(), "nota.txt")
    text = output_text(out, ocr=False)
    assert "rossi" not in text and rep["converted_from"] == ".txt"


@pytest.mark.skipif(not HAS_TESSERACT, reason="tesseract not installed")
def test_image_file():
    doc = synthetic.generate(1, kind="contribution")
    png = pymupdf.open(stream=doc.pdf, filetype="pdf")[0].get_pixmap(dpi=200).tobytes("png")
    out, rep = service.redact_file(png, "scan.png")
    assert rep["ocr_pages"] == [1]
    text = output_text(out, ocr=True)
    first_page = pymupdf.open(stream=doc.pdf, filetype="pdf")[0].get_text()
    leaks = [v for v in doc.private_values if present(v, text) and present(v, first_page.replace("\n", " "))]
    assert not leaks


@pytest.mark.skipif(not HAS_SOFFICE, reason="LibreOffice not installed")
def test_office_file(tmp_path):
    # The .docx is built by LibreOffice itself from a text file: no binary fixture in the repo.
    src = tmp_path / "lettera.txt"
    src.write_text("Vista l'istanza del sig. Mario Rossi, codice fiscale "
                   + synthetic.tax_code("RSSMRA60B01Z999") + ".")
    subprocess.run(["soffice", f"-env:UserInstallation=file://{tmp_path}/p", "--headless", "--convert-to", "docx",
                    "--outdir", str(tmp_path), str(src)], check=True, capture_output=True, timeout=180)
    out, rep = service.redact_file((tmp_path / "lettera.docx").read_bytes(), "lettera.docx")
    text = output_text(out, ocr=False)
    assert "rossi" not in text and "persona 1" in text and rep["converted_from"] == ".docx"


def test_unsupported():
    with pytest.raises(UnsupportedFormat):
        to_pdf(b"x", "archive.rar")
