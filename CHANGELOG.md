# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). The release workflow publishes the
section of each version as the notes of its GitHub release.

## [Unreleased]

## [0.1.1] - 2026-11-28

### Added
- Python package on PyPI: `pip install oscura-atti`, or `uvx oscura-atti mcp` without installing it.
  Published with Trusted Publishing and PEP 740 attestations.
- Entry in the official MCP Registry (`io.github.francescor/oscura-atti`) with both the PyPI package
  and the container image, updated automatically on every release.
- Container image for `linux/arm64` too (Apple Silicon, ARM servers).
- Release images signed with cosign (keyless), with SBOM and build provenance; how to verify them is in
  the README.
- `SECURITY.md`, `CONTRIBUTING.md`, `CITATION.cff`, issue forms that refuse real documents, a
  pull-request checklist.
- Tests on Python 3.11, 3.12, 3.13 and 3.14; a CI check that the version is the same everywhere;
  OpenSSF Scorecard; Dependabot for Python, GitHub Actions and the Docker base image.

### Fixed
- Python 3.11: `oscura-atti sample` and the benchmark failed with a `SyntaxError`, because the
  generator of invented documents used an f-string syntax that exists only from Python 3.12.
  Redaction itself was not affected. Found by the new test matrix.

### Changed
- The MCP SDK is now a core dependency, so `uvx oscura-atti mcp` works out of the box. The `mcp`
  extra is kept as an empty alias: `pip install "oscura-atti[mcp]"` still works.
- README: says up front that redaction is local and rule-based and that it is an MCP server;
  Claude Code setup with `OSCURA_ATTI_DIR`.
- GitHub Actions pinned to commit SHAs; the image workflow is now `publish.yml`.

## [0.1.0] - 2026-11-28

First public release: redaction of personal data in PDF, signed `.p7m`, office documents, images and
text with consistent labels; OCR for scanned pages; verification of the output; `review` outcome
for documents that need a human decision; CLI, Python library, MCP server (stdio and Streamable
HTTP) and container image.

[Unreleased]: https://github.com/francescor/oscura-atti/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/francescor/oscura-atti/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/francescor/oscura-atti/releases/tag/v0.1.0
