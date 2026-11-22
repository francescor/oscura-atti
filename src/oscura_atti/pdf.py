"""PDF text model (character by character) and rewriting with labels.

The document text is rebuilt keeping, for every character, its page, line and bounding box.
A finding in the text therefore maps to the exact boxes to redact, even when the PDF splits a
name into several text runs or wraps it onto the next line. Scanned pages (or pages that are
mostly an image with a thin text overlay, e.g. a registry stamp) go through OCR, and redaction
wipes the image pixels under the boxes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pymupdf

# Without ligatures ("fi" as one glyph) names can be matched character by character.
_FLAGS = pymupdf.TEXTFLAGS_RAWDICT & ~pymupdf.TEXT_PRESERVE_LIGATURES & ~pymupdf.TEXT_PRESERVE_IMAGES

# A page is treated as scanned when images cover this share of it and it has little text.
_IMAGE_COVERAGE = 0.35
_MAX_TEXT_FOR_SCAN = 1500


@dataclass
class Char:
    page: int
    line: tuple[int, int, int]   # (page, block, line)
    bbox: tuple[float, float, float, float]


@dataclass
class DocumentText:
    text: str
    # One entry per character of `text`; None for spaces and line breaks we inserted.
    chars: list[Char | None]
    ocr_pages: list[int] = field(default_factory=list)          # 1-based
    unanalysed_pages: list[int] = field(default_factory=list)   # 1-based
    warnings: list[str] = field(default_factory=list)

    def page_of(self, offset: int) -> int | None:
        for c in self.chars[offset:offset + 200]:
            if c is not None:
                return c.page
        return None


def image_coverage(page: pymupdf.Page) -> float:
    """Share of the page covered by images (overlaps counted twice, capped at 1)."""
    area = abs(page.rect)
    if not area:
        return 0.0
    total = 0.0
    for info in page.get_image_info():
        r = pymupdf.Rect(info["bbox"]) & page.rect
        if not r.is_empty:
            total += abs(r)
    return min(1.0, total / area)


def needs_ocr(page: pymupdf.Page) -> bool:
    if not page.get_images():
        return False
    text_len = len(page.get_text().strip())
    return text_len < 40 or (text_len < _MAX_TEXT_FOR_SCAN and image_coverage(page) >= _IMAGE_COVERAGE)


def ocr_textpage(page: pymupdf.Page, language: str):
    return page.get_textpage_ocr(language=language, dpi=300, full=True)


def extract_text(doc: pymupdf.Document, ocr: bool = True, ocr_language: str = "ita") -> DocumentText:
    parts: list[str] = []
    chars: list[Char | None] = []
    result = DocumentText("", [])

    def add(c: str, info: Char | None) -> None:
        parts.append(c)
        chars.append(info)

    for n, page in enumerate(doc):
        textpage = None
        if needs_ocr(page):
            if not ocr:
                result.unanalysed_pages.append(n + 1)
                result.warnings.append(f"page {n + 1}: scanned, OCR disabled")
            else:
                try:
                    textpage = ocr_textpage(page, ocr_language)
                    result.ocr_pages.append(n + 1)
                except Exception as e:  # tesseract missing, language data missing...
                    result.unanalysed_pages.append(n + 1)
                    result.warnings.append(f"page {n + 1}: OCR failed ({e})")
        data = page.get_text("rawdict", flags=_FLAGS, textpage=textpage)
        for block in data["blocks"]:
            if block.get("type") != 0:
                continue
            for ln, line in enumerate(block["lines"]):
                # Lines of the same block are one paragraph wrapped: join them with a space, so a
                # value split across two lines is still found. Blocks are separated by a newline.
                if ln > 0 and parts and parts[-1] != " ":
                    add(" ", None)
                key = (n, block["number"], ln)
                prev = None
                for span in line["spans"]:
                    for ch in span["chars"]:
                        c, bb = ch["c"], tuple(ch["bbox"])
                        if c in "­":   # soft hyphen
                            continue
                        # Visual space: two glyphs far apart with no space character between them.
                        if (prev is not None and not c.isspace() and parts and not parts[-1].isspace()
                                and bb[0] - prev[2] > 0.25 * max(span["size"], 1)):
                            add(" ", None)
                        add(" " if c.isspace() else c, Char(n, key, bb))
                        prev = bb
            add("\n", None)
        add("\f", None)

    result.text = "".join(parts)
    result.chars = chars
    return result


def boxes(dt: DocumentText, start: int, end: int) -> list[tuple[int, pymupdf.Rect]]:
    """Boxes (page, rect) covering text [start, end): one per line, in reading order."""
    per_line: dict[tuple[int, int, int], pymupdf.Rect] = {}
    order: list[tuple[int, int, int]] = []
    for info in dt.chars[start:end]:
        if info is None:
            continue
        r = pymupdf.Rect(info.bbox)
        if r.is_empty or r.is_infinite:
            continue
        if info.line in per_line:
            per_line[info.line] |= r
        else:
            per_line[info.line] = r
            order.append(info.line)
    return [(k[0], per_line[k]) for k in order]


@dataclass
class Replacement:
    page: int
    rect: pymupdf.Rect
    label: str | None        # None: continuation of a wrapped value, only covered
    short_label: str | None


def _fit(label: str, rect: pymupdf.Rect) -> float | None:
    """Font size at which the label fits in the box, or None."""
    size = min(rect.height * 0.8, 11.0)
    while size >= 3.5:
        if pymupdf.get_text_length(label, fontname="helv", fontsize=size) <= rect.width - 1:
            return size
        size -= 0.5
    return None


def apply(doc: pymupdf.Document, replacements: list[Replacement], style: str = "label",
          stamp: str | None = None) -> list[str]:
    """Redact the boxes, write the labels, scrub metadata. Returns warnings."""
    warnings: list[str] = []
    if style == "black":
        fill, text_color = (0, 0, 0), (1, 1, 1)
    else:
        fill, text_color = (0.88, 0.93, 1.0), (0.05, 0.2, 0.55)

    by_page: dict[int, list[Replacement]] = {}
    for r in replacements:
        by_page.setdefault(r.page, []).append(r)

    for n, items in by_page.items():
        page = doc[n]
        for item in items:
            rect = pymupdf.Rect(item.rect) + (-0.5, -0.2, 0.5, 0.2)
            text, size = None, 11.0
            for candidate in (item.label, item.short_label):
                if candidate:
                    fitted = _fit(candidate, rect)
                    if fitted:
                        text, size = candidate, fitted
                        break
            if item.label and text is None:
                warnings.append(f"page {n + 1}: label '{item.label}' does not fit, box left empty")
            page.add_redact_annot(rect, text=text, fontname="helv", fontsize=size, fill=fill,
                                  text_color=text_color, cross_out=False)
        # Remove text under the boxes, blank image pixels, keep table rules.
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS,
                              graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)

    # Metadata, embedded files, JavaScript, thumbnails, form data can all carry personal data.
    doc.scrub(attached_files=True, embedded_files=True, javascript=True, metadata=True,
              xml_metadata=True, thumbnails=True, reset_responses=True, remove_links=False,
              hidden_text=False, redactions=False, clean_pages=True, reset_fields=False)
    # Annotations (comments, signature widgets) may contain names: drop them.
    for page in doc:
        for annot in list(page.annots() or []):
            page.delete_annot(annot)
        for widget in list(page.widgets() or []):
            page.delete_widget(widget)

    if stamp:
        for page in doc:
            # Bottom-left corner as the reader sees it, also on rotated (landscape) pages.
            r = page.rect
            point = pymupdf.Point(18, r.height - 8) * page.derotation_matrix
            page.insert_text(point, stamp, fontname="helv", fontsize=6, color=(0.35, 0.35, 0.35),
                             rotate=page.rotation)
    return warnings
