<!-- generated from .stewards/manifest.toml — edit the manifest, not this file -->

# Steward: markdown

Keep GitHub-oriented markdown escaping and report output readable, safe, and semantically aligned with other surfaces.

Ordinary work: use this map directly with the root map and run only affected checks.
Do not open `.stewards/PROTOCOL.md` or `.stewards/manifest.toml` unless the task is an explicit review/audit or steward-network maintenance.

## Protects

| Invariant | Sev | Backing | Proof / anchor |
| --- | --- | --- | --- |
| Markdown escaping, safe strings, filters, components, and CLI rendering remain fixture-backed and GitHub-readable. | P0 | machine-backed | `uv run pytest tests/markdown -q` (`markdown-suite`) |

## Guardrails

- Markdown is not plain-text escaping and never inherits ANSI- or HTML-only assumptions.
- Tables, details, code blocks, safe strings, and report markers stay fixture-backed.

## Edges

- renders → **templates** (report templates)
- consumes → **schemas** (AMP/report fields)

## Owns

- **code:** `src/kida/markdown/`, `src/kida/environment/markdown.py`
- **tests:** `tests/markdown/`
- **docs:** `site/content/docs/usage/github-action.md`
