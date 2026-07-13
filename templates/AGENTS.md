<!-- generated from .stewards/manifest.toml — edit the manifest, not this file -->

# Steward: templates

Keep built-in pytest, coverage, ruff, ty, SARIF, release, and AMP reports readable, schema-backed, and safe for untrusted tool output.

Ordinary work: use this map directly with the root map and run only affected checks.
Do not open `.stewards/PROTOCOL.md` or `.stewards/manifest.toml` unless the task is an explicit review/audit or steward-network maintenance.

## Protects

| Invariant | Sev | Backing | Proof / anchor |
| --- | --- | --- | --- |
| Built-in report templates, declared fields, fixtures, snapshots, copied Action templates, readability, and dedupe markers remain aligned. | P0 | machine-backed | `uv run pytest tests/templates -q` (`templates-suite`) |

## Guardrails

- Template fields exist in schemas and realistic fixtures.
- Source templates, copied GitHub templates, snapshots, dedupe markers, and docs move together when report structure changes.

## Edges

- consumes → **schemas** (report shapes)
- escaped-by → **markdown** (GitHub output)

## Owns

- **code:** `templates/`, `.github/kida-templates/`
- **tests:** `tests/templates/`
- **docs:** `docs/kida-render-product.md`, `site/content/docs/usage/github-action.md`
