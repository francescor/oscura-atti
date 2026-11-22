"""Extract the document from a CAdES signature envelope (.p7m).

Digitally signed documents often come as `act.pdf.p7m`: the PDF sits inside a CMS SignedData
structure, binary (DER) or Base64, sometimes nested (`.p7m.p7m`). A redacted copy cannot keep
the signature: the document changes.
"""

from __future__ import annotations

import base64
import binascii

from asn1crypto import cms

_MAX_NESTING = 5


def _decode(data: bytes) -> bytes:
    stripped = data.strip()
    if stripped.startswith(b"-----BEGIN"):
        lines = [ln for ln in stripped.splitlines() if not ln.startswith(b"-----")]
        return base64.b64decode(b"".join(lines))
    if stripped[:1] != b"\x30":  # not DER: maybe bare Base64
        try:
            return base64.b64decode(b"".join(stripped.split()), validate=True)
        except (binascii.Error, ValueError):
            pass
    return data


def _content(der: bytes) -> bytes:
    info = cms.ContentInfo.load(der)
    if info["content_type"].native != "signed_data":
        raise ValueError("CMS envelope without signed data")
    content = info["content"]["encap_content_info"]["content"]
    if content.native is None:
        raise ValueError("detached signature: the envelope does not contain the document")
    return content.native


def is_pdf(data: bytes) -> bool:
    """A PDF header within the first KB (junk before it is tolerated), not inside a DER envelope."""
    head = data[:1024]
    return head.lstrip().startswith(b"%PDF-") or (b"%PDF-" in head and head[:1] not in (b"\x30", b"M", b"-"))


def unwrap(data: bytes) -> tuple[bytes, bool]:
    """Return (pdf_bytes, was_signed). Accepts a PDF or a (possibly nested) .p7m holding a PDF."""
    if is_pdf(data):
        return data, False
    for _ in range(_MAX_NESTING):
        try:
            data = _content(_decode(data))
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"neither a PDF nor a readable .p7m envelope ({e})") from e
        if is_pdf(data):
            return data, True
    raise ValueError("the .p7m envelope does not contain a PDF")
