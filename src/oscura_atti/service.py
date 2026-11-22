"""Entry point shared by the command line and the MCP server: accepts PDF or .p7m bytes."""

from __future__ import annotations

from . import engine, p7m
from .config import Config


def analyse(data: bytes, conf: Config | None = None, add: list[str] | None = None,
            keep: list[str] | None = None, include_values: bool = True) -> dict:
    pdf, signed = p7m.unwrap(data)
    report = engine.analyse(pdf, conf, add, keep, include_values)
    report["signed_p7m"] = signed
    return report


def redact(data: bytes, conf: Config | None = None, add: list[str] | None = None,
           keep: list[str] | None = None, include_values: bool = False,
           verify_ocr: bool = True, include_text: bool = False) -> tuple[bytes, dict]:
    pdf, signed = p7m.unwrap(data)
    output, report = engine.redact(pdf, conf, add, keep, include_values, verify_ocr, include_text)
    report["signed_p7m"] = signed
    if report.get("unchanged"):
        return data, report          # the original as received, signature included
    if signed:
        report["warnings"].append("the original was digitally signed: the redacted copy is not")
    return output, report


def redact_file(data: bytes, filename: str, conf: Config | None = None, add: list[str] | None = None,
                keep: list[str] | None = None, include_values: bool = False,
                include_text: bool = False) -> tuple[bytes, dict]:
    """Like `redact`, for any supported format (see convert.py): the output is a PDF, or the original
    file itself when there is nothing to redact."""
    from .convert import to_pdf
    pdf, converted_from = to_pdf(data, filename)
    output, report = redact(pdf, conf, add, keep, include_values, include_text=include_text)
    report["converted_from"] = converted_from
    if report.get("unchanged") and converted_from:
        return data, report          # nothing to redact: keep the original office file / image
    return output, report
