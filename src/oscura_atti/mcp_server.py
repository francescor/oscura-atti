"""MCP server: the same operations as the command line, as tools.

PDFs travel as Base64 in requests and responses. If OSCURA_ATTI_DIR is set, tools also accept
file paths inside that folder (handy with stdio on the same machine); never outside it.
The server stores nothing: neither the PDFs nor the mapping between values and labels.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

import anyio
from mcp.server.mcpserver import MCPServer

from . import __version__, service
from .config import Config

INSTRUCTIONS = """Redacts personal data in public-sector documents (PDF, also signed .p7m) so they can be
republished, e.g. after the legal publication period on an official notice board has ended.
Values are not blacked out but replaced by consistent labels: the same person is always "Person 1"
(or "Persona 1" in Italian), another one "Person 2", and likewise for tax codes, IBANs, addresses,
birth data, e-mails and phone numbers. Recommended flow: 1) `analyse_pdf` and show the operator the
entity list, especially entries with review=true or action=flag and any sensitive_terms; 2) collect
corrections (names to redact anyway in `add`, public names to keep in `keep`); 3) `redact_pdf` with
the same corrections. An outcome of "review" means the document must NOT be published without a
human check."""

mcp = MCPServer(name="oscura-atti", version=__version__, instructions=INSTRUCTIONS)


def _allowed_path(path: str) -> Path:
    root = os.environ.get("OSCURA_ATTI_DIR")
    if not root:
        raise ValueError("file paths are disabled: set OSCURA_ATTI_DIR or send pdf_base64")
    root_p = Path(root).resolve()
    p = (root_p / path).resolve()
    if not p.is_relative_to(root_p):
        raise ValueError("path outside the allowed folder")
    return p


def _read(pdf_base64: str | None, path: str | None) -> bytes:
    if bool(pdf_base64) == bool(path):
        raise ValueError("give exactly one of pdf_base64 and path")
    if pdf_base64:
        return base64.b64decode(pdf_base64)
    return _allowed_path(path).read_bytes()


def _config(config: dict | None) -> Config:
    return Config.from_dict(config) if config else Config()


@mcp.tool()
async def analyse_pdf(pdf_base64: str | None = None, path: str | None = None, config: dict | None = None,
                      add: list[str] | None = None, keep: list[str] | None = None,
                      filename: str | None = None) -> dict:
    """List the personal data found in a document (PDF, .p7m, office file, image: give `filename`
    for non-PDF input so the format is known), grouped by entity with the label each will
    get, without changing the document. `config`: language, packs, public_persons, public_domains,
    public_values, policy, style, ocr (see README). `add`: text to redact anyway; `keep`: text to
    leave readable. The report contains the values found: it is meant for the operator."""
    data = _read(pdf_base64, path)
    name = filename or path or "document.pdf"

    def run_analysis() -> dict:
        from .convert import to_pdf
        pdf, converted_from = to_pdf(data, name)
        report = service.analyse(pdf, _config(config), add, keep, True)
        report["converted_from"] = converted_from
        return report

    return await anyio.to_thread.run_sync(run_analysis)


@mcp.tool()
async def redact_pdf(pdf_base64: str | None = None, path: str | None = None, output_path: str | None = None,
                     config: dict | None = None, add: list[str] | None = None,
                     keep: list[str] | None = None, filename: str | None = None) -> dict:
    """Write the redacted copy: every value is replaced by its label (Person 1, Tax code 1...),
    metadata, embedded files and annotations removed, a "redacted copy" footer on every page.
    Non-PDF input (office documents, images: give `filename`) is converted; the output is always a PDF.
    Returns the PDF as Base64 (or writes it to `output_path` when paths are enabled) and the report,
    without the original values. Publish only with outcome "ok" or after a human check."""
    data = _read(pdf_base64, path)
    name = filename or path or "document.pdf"
    output, report = await anyio.to_thread.run_sync(
        lambda: service.redact_file(data, name, _config(config), add, keep, False))
    if output_path:
        _allowed_path(output_path).write_bytes(output)
        return {"output_path": output_path, "report": report}
    return {"pdf_base64": base64.b64encode(output).decode("ascii"), "report": report}


def run(http: bool = False, host: str = "127.0.0.1", port: int = 8000) -> None:
    if http:
        mcp.run("streamable-http", host=host, port=port)
    else:
        mcp.run("stdio")
