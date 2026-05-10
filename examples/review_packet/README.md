# Review Packet

A dogfood-style PR review packet rendered from one structured payload into
Markdown and terminal output.

## Run

```bash
cd examples/review_packet
python app.py
python app.py --mode terminal
```

## What It Shows

- one normalized data payload for CI, coverage, changed files, diagnostics, and steward findings
- Markdown output suitable for a GitHub PR comment or step summary
- terminal output from the same data, without adding another schema
- Kida diagnostics treated as review data, not prose
- an example-only large-app analysis packet that combines context contracts,
  component metadata, literal attributes, escape findings, and privacy findings

This example is intentionally repo-local. It proves the workflow before Kida
adds any new public report command or schema.
