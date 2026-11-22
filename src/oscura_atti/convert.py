"""Turn other document formats into PDF before redaction.

- images (PNG, JPEG, TIFF, BMP, GIF): wrapped into a PDF, then OCR'd like a scan;
- office documents (DOC, DOCX, ODT, RTF, XLS, XLSX, ODS, PPT, PPTX, ODP): converted with
  LibreOffice in headless mode (must be installed: `soffice` on the PATH);
- plain text, CSV, XML, HTML: typeset into a simple PDF.

The redacted copy of a non-PDF document is always a PDF.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pymupdf

IMAGE = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif")
OFFICE = (".doc", ".docx", ".odt", ".rtf", ".xls", ".xlsx", ".ods", ".ppt", ".pptx", ".odp")
TEXT = (".txt", ".csv", ".xml", ".html", ".htm", ".json", ".md")
SUPPORTED = (".pdf", ".p7m") + IMAGE + OFFICE + TEXT


class UnsupportedFormat(ValueError):
    pass


def extension(filename: str) -> str:
    name = filename.lower()
    if name.endswith(".p7m"):
        return ".p7m"
    return Path(name).suffix


def image_to_pdf(data: bytes, ext: str) -> bytes:
    img = pymupdf.open(stream=data, filetype=ext.lstrip("."))
    return img.convert_to_pdf()


def text_to_pdf(text: str) -> bytes:
    doc = pymupdf.open()
    lines = text.splitlines() or [""]
    per_page = 70
    for start in range(0, len(lines), per_page):
        page = doc.new_page(width=595, height=842)
        rect = pymupdf.Rect(40, 40, 555, 802)
        chunk = "\n".join(lines[start:start + per_page])
        page.insert_textbox(rect, chunk, fontsize=8, fontname="cour")
    return doc.tobytes()


def office_to_pdf(data: bytes, ext: str, timeout: int = 180) -> bytes:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise UnsupportedFormat(f"{ext} needs LibreOffice (soffice) to be converted to PDF")
    with tempfile.TemporaryDirectory(prefix="oscura-atti-") as tmp:
        src = Path(tmp) / f"input{ext}"
        src.write_bytes(data)
        profile = Path(tmp) / "profile"   # a private profile lets conversions run in parallel
        subprocess.run([soffice, f"-env:UserInstallation=file://{profile}", "--headless", "--norestore",
                        "--convert-to", "pdf", "--outdir", tmp, str(src)],
                       check=True, timeout=timeout, capture_output=True)
        out = Path(tmp) / "input.pdf"
        if not out.exists():
            raise UnsupportedFormat(f"LibreOffice could not convert this {ext} file")
        return out.read_bytes()


def to_pdf(data: bytes, filename: str) -> tuple[bytes, str | None]:
    """Return (pdf_bytes, converted_from) where converted_from is None for PDF / .p7m input."""
    ext = extension(filename)
    if ext in (".pdf", ".p7m"):
        return data, None
    if ext in IMAGE:
        return image_to_pdf(data, ext), ext
    if ext in OFFICE:
        return office_to_pdf(data, ext), ext
    if ext in TEXT:
        return text_to_pdf(data.decode("utf-8", errors="replace")), ext
    raise UnsupportedFormat(f"unsupported format: {ext or filename}")
