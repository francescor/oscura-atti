#!/usr/bin/env python3
"""Build the README images and demo video from an INVENTED act (oscura_atti.synthetic).

    python tools/make_media.py            # writes docs/media/*.png, demo.gif, demo.mp4

Never feed real documents to this script: everything it writes is committed to the repository.
Needs Pillow (`pip install pillow`) and, for the MP4, ffmpeg.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont

from oscura_atti import engine, synthetic
from oscura_atti.config import Config
from oscura_atti.pdf import boxes

OUT = Path(__file__).resolve().parent.parent / "docs" / "media"
DPI = 110
SCALE = DPI / 72
SEED, KIND = 7, "contribution"

COLOURS = {  # one colour per entity type (colour-blind friendly palette)
    "PERSON": (0, 114, 178), "TAX_CODE": (213, 94, 0), "IBAN": (0, 158, 115), "ADDRESS": (204, 121, 167),
    "BIRTH": (230, 159, 0), "PHONE": (86, 180, 233), "EMAIL": (120, 94, 240), "VAT_NUMBER": (150, 150, 150),
}
NAMES = {"PERSON": "person", "TAX_CODE": "tax code", "IBAN": "IBAN", "ADDRESS": "address", "BIRTH": "birth data",
         "PHONE": "phone", "EMAIL": "e-mail"}


def font(size: int, mono: bool = False, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (["/usr/share/fonts/google-noto-vf/NotoSansMono[wght].ttf", "DejaVuSansMono.ttf"] if mono else
                  ["/usr/share/fonts/google-noto/NotoSans-Bold.ttf" if bold else "/usr/share/fonts/google-noto/NotoSans-Regular.ttf",
                   "/usr/share/fonts/liberation-sans-fonts/LiberationSans-Regular.ttf", "DejaVuSans.ttf"])
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render(pdf: bytes, page: int = 0, clip_height: float = 0.62) -> Image.Image:
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    p = doc[page]
    clip = pymupdf.Rect(0, 20, p.rect.width, p.rect.height * clip_height)
    pix = p.get_pixmap(dpi=DPI, clip=clip)
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB"), clip


def highlight(img: Image.Image, clip: pymupdf.Rect, pdf: bytes, types: set[str] | None = None) -> Image.Image:
    """Draw a coloured frame around every value that will be redacted."""
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    analysis, dt = engine.analyse_document(doc, Config())
    out = img.copy()
    draw = ImageDraw.Draw(out, "RGBA")
    for e in analysis.entities:
        if e.action != "redact" or (types is not None and e.type not in types):
            continue
        colour = COLOURS.get(e.type, (90, 90, 90))
        for m in e.mentions:
            for page, r in boxes(dt, m.start, m.end):
                if page != 0:
                    continue
                x0, y0 = (r.x0 - clip.x0) * SCALE, (r.y0 - clip.y0) * SCALE
                x1, y1 = (r.x1 - clip.x0) * SCALE, (r.y1 - clip.y0) * SCALE
                draw.rectangle([x0 - 2, y0 - 1, x1 + 2, y1 + 1], fill=colour + (45,), outline=colour + (255,), width=2)
    return out


def caption(img: Image.Image, text: str, sub: str = "") -> Image.Image:
    bar = 64 if sub else 44
    out = Image.new("RGB", (img.width, img.height + bar), "white")
    out.paste(img, (0, bar))
    d = ImageDraw.Draw(out)
    d.rectangle([0, 0, img.width, bar], fill=(24, 32, 48))
    d.text((16, 9), text, font=font(20, bold=True), fill="white")
    if sub:
        d.text((16, 36), sub, font=font(14), fill=(190, 200, 215))
    return out


def legend(img: Image.Image) -> Image.Image:
    out = Image.new("RGB", (img.width, img.height + 40), "white")
    out.paste(img, (0, 0))
    d = ImageDraw.Draw(out)
    x = 16
    for t, name in NAMES.items():
        c = COLOURS[t]
        d.rectangle([x, img.height + 12, x + 18, img.height + 28], fill=c)
        d.text((x + 24, img.height + 10), name, font=font(15), fill=(40, 40, 40))
        x += 30 + int(d.textlength(name, font=font(15))) + 18
    return out


def side_by_side(a: Image.Image, b: Image.Image, gap: int = 16) -> Image.Image:
    out = Image.new("RGB", (a.width + b.width + gap, max(a.height, b.height)), (225, 229, 235))
    out.paste(a, (0, 0))
    out.paste(b, (a.width + gap, 0))
    return out


def terminal(lines: list[tuple[str, tuple[int, int, int]]], width: int, height: int) -> Image.Image:
    img = Image.new("RGB", (width, height), (22, 27, 34))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, width, 30], fill=(45, 51, 59))
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([14 + i * 22, 9, 26 + i * 22, 21], fill=c)
    y = 46
    f = font(17, mono=True)
    for text, colour in lines:
        d.text((20, y), text, font=f, fill=colour)
        y += 26
    return img


def fit(img: Image.Image, width: int, height: int) -> Image.Image:
    img = img.copy()
    img.thumbnail((width, height))
    out = Image.new("RGB", (width, height), "white")
    out.paste(img, ((width - img.width) // 2, (height - img.height) // 2))
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    doc = synthetic.generate(SEED, kind=KIND, layout="normal")
    redacted, report = engine.redact(doc.pdf, Config())

    original, clip = render(doc.pdf)
    marked = highlight(original, clip, doc.pdf)
    result, _ = render(redacted)

    caption(side_by_side(caption(original, "Before", "invented act - all names and codes are fictitious"),
                         caption(result, "After: oscura-atti redact", "same person = same label, text stays readable")),
            "oscura-atti").save(OUT / "before_after.png", optimize=True)
    legend(caption(marked, "What it finds", "codes are checked (check digits), people are grouped across forms")
           ).save(OUT / "detection.png", optimize=True)

    # Scanned version: OCR, pixels wiped under the labels
    scan = synthetic.as_scan(doc.pdf, dpi=150)
    scan_red, _ = engine.redact(scan, Config())
    s0, _ = render(scan)
    s1, _ = render(scan_red)
    side_by_side(caption(s0, "Scanned page (image only)", "invented act"),
                 caption(s1, "After: OCR + redaction", "pixels under each label are wiped")).save(OUT / "scan.png", optimize=True)

    # Demo animation: command -> detection by type -> redacted copy -> report
    W, H = 1000, 720
    frames: list[tuple[Image.Image, int]] = []
    cmd = [("$ oscura-atti redact delibera.pdf delibera.redacted.pdf", (126, 231, 135))]
    frames.append((terminal(cmd, W, H), 1600))
    frames.append((fit(caption(original, "1. The original act", "invented data"), W, H), 1800))
    shown: set[str] = set()
    for t in ["PERSON", "TAX_CODE", "BIRTH", "ADDRESS", "PHONE", "EMAIL", "IBAN"]:
        shown.add(t)
        frames.append((fit(legend(caption(highlight(original, clip, doc.pdf, set(shown)),
                                           f"2. Finding personal data: {NAMES[t]}")), W, H), 700))
    frames.append((fit(caption(result, "3. The redacted copy", "Persona 1, Persona 2, Codice fiscale 1 ..."), W, H), 3200))
    red = [e for e in report["entities"] if e["action"] == "redact"]
    rep_lines = [("$ oscura-atti redact delibera.pdf delibera.redacted.pdf", (126, 231, 135)), ("{", (201, 209, 217))]
    for e in red[:9]:
        rep_lines.append((f'  "{e["label"]}": {e["type"]}, {e["mentions"]} mention(s)', (201, 209, 217)))
    rep_lines += [("  ...", (139, 148, 158)), (f'  "outcome": "{report["outcome"]}", "leaks": {len(report["leaks"])}', (121, 192, 255)),
                  ("}", (201, 209, 217)), ("", (0, 0, 0)), ("# the report never contains the original values", (139, 148, 158))]
    frames.append((terminal(rep_lines, W, H), 3500))

    frames[0][0].save(OUT / "demo.gif", save_all=True, append_images=[f for f, _ in frames[1:]],
                      duration=[d for _, d in frames], loop=0, optimize=True)
    if shutil.which("ffmpeg"):
        with tempfile.TemporaryDirectory() as tmp:
            listing = []
            for i, (img, ms) in enumerate(frames):
                path = Path(tmp) / f"f{i:03d}.png"
                img.save(path)
                listing.append(f"file '{path}'\nduration {ms / 1000}")
            listing.append(f"file '{Path(tmp) / f'f{len(frames) - 1:03d}.png'}'")
            (Path(tmp) / "list.txt").write_text("\n".join(listing))
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(Path(tmp) / "list.txt"),
                            "-vf", "fps=25,format=yuv420p", "-movflags", "+faststart", str(OUT / "demo.mp4")], check=True)
    for f in sorted(OUT.iterdir()):
        print(f"{f.name}: {f.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
