"""Command line.

  oscura-atti analyse act.pdf [--config org.json] [--add "Name Surname"] [--keep "..."]
  oscura-atti redact act.pdf act_redacted.pdf [--report report.json]
  oscura-atti batch input_dir output_dir [--config org.json] [--jobs 4]
  oscura-atti sample sample.pdf          # an INVENTED act to try the tool on
  oscura-atti mcp [--http] [--host 127.0.0.1] [--port 8000]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import service
from .config import Config


def _config(args) -> Config:
    conf = Config.from_file(args.config) if args.config else Config()
    if args.no_ocr:
        conf.ocr = False
    if args.style:
        conf.style = args.style
    if args.language:
        conf.language = args.language
    if args.packs:
        conf.packs = args.packs.split(",")
    return conf


def _options(p: argparse.ArgumentParser) -> None:
    p.add_argument("--config", help="JSON configuration file for the organisation")
    p.add_argument("--add", action="append", default=[], help="text to redact anyway (repeatable)")
    p.add_argument("--keep", action="append", default=[], help="text to leave readable (repeatable)")
    p.add_argument("--no-ocr", action="store_true", help="do not OCR scanned pages")
    p.add_argument("--style", choices=["label", "black"])
    p.add_argument("--language", help="label language: it, en, es, fr, de")
    p.add_argument("--packs", help="comma-separated recognizer packs, e.g. common,it")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="oscura-atti", description="Redact personal data in PDF documents "
                                 "with consistent labels (Person 1, Person 2...).")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("analyse", aliases=["analyze"], help="list the personal data found, change nothing")
    p.add_argument("pdf")
    p.add_argument("--no-values", action="store_true", help="do not print the values found")
    _options(p)

    p = sub.add_parser("redact", help="write the redacted copy (PDF, .p7m, images, office documents)")
    p.add_argument("pdf")
    p.add_argument("output")
    p.add_argument("--report", help="where to write the JSON report (default: stdout)")
    p.add_argument("--with-values", action="store_true", help="include the redacted values in the report")
    _options(p)

    p = sub.add_parser("batch", help="redact every PDF/.p7m of a folder into another folder")
    p.add_argument("input_dir")
    p.add_argument("output_dir")
    p.add_argument("--jobs", type=int, default=1)
    p.add_argument("--learn-public", action="store_true",
                   help="first pass: officials kept for their role in 2+ documents stay readable everywhere")
    _options(p)

    p = sub.add_parser("sample", help="write an invented sample act (no real personal data)")
    p.add_argument("output")
    p.add_argument("--scanned", action="store_true", help="as a scanned (image-only) PDF")

    p = sub.add_parser("mcp", help="start the MCP server")
    p.add_argument("--http", action="store_true", help="Streamable HTTP instead of stdio")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)

    args = ap.parse_args(argv)

    if args.command == "mcp":
        from .mcp_server import run
        run(http=args.http, host=args.host, port=args.port)
        return 0

    if args.command == "sample":
        from . import synthetic
        doc = synthetic.generate(seed=1)
        data = synthetic.as_scan(doc.pdf) if args.scanned else doc.pdf
        Path(args.output).write_bytes(data)
        return 0

    if args.command == "batch":
        from .batch import run_batch
        return run_batch(Path(args.input_dir), Path(args.output_dir), _config(args), args.jobs, args.learn_public)

    data = Path(args.pdf).read_bytes()
    if args.command in ("analyse", "analyze"):
        report = service.analyse(data, _config(args), args.add, args.keep, not args.no_values)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    output, report = service.redact_file(data, args.pdf, _config(args), args.add, args.keep, args.with_values)
    Path(args.output).write_bytes(output)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0 if report["outcome"] == "ok" else 2


if __name__ == "__main__":
    sys.exit(main())
