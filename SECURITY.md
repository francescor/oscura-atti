# Security policy

`oscura-atti` exists to stop personal data from being republished, so a value that stays readable in a
redacted copy is treated as a security issue, not as an ordinary bug.

## Supported versions

Only the latest release receives fixes. Please check that the problem is still there with it
(`pip install -U oscura-atti` or `ghcr.io/francescor/oscura-atti:latest`).

## How to report

Use GitHub's **private vulnerability reporting**:
<https://github.com/francescor/oscura-atti/security/advisories/new>. Reports in English or Italian
are both welcome.

**Never attach a real document, and never paste real names, tax codes or other values from one** —
not even in a private report. Instead:

1. reproduce the problem with an invented text (`oscura-atti sample` gives you a starting document,
   or write the sentence yourself with made-up names and codes);
2. if you cannot reproduce it, describe the *pattern*: the layout, the words around the value, the
   kind of value, whether the page is scanned, the `outcome` and the `rules` in the report.

You will get an answer within 7 days. Fixes come with an invented regression test and are credited in
the changelog unless you prefer otherwise.

## What counts

Report privately:

- a redacted value that can still be extracted from the output (text layer, image, metadata,
  annotations, attachments), especially if the report says `leaks: []`;
- a class of values that is systematically missed and would be published (for example a document
  layout where every name slips through);
- the MCP server or the library reading or writing files outside `OSCURA_ATTI_DIR`;
- anything that makes the tool store or send documents or the value-to-label mapping.

Open a normal issue instead (with an invented example) for the **known limits** described in the
README: names with no contextual cue, handwriting, values split by hyphenation, over-redaction of
public names.

The MCP server has no authentication of its own by design: exposing it to a network without a proxy
that authenticates is a deployment choice, not a vulnerability (see `deploy/swarm-stack.yml`).
