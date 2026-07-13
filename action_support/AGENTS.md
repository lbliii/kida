<!-- generated from .stewards/manifest.toml — edit the manifest, not this file -->

# Steward: action

Keep typed GitHub Action support code, release-note collection, provenance, and report data contracts deterministic and diagnosable.

Ordinary work: use this map directly with the root map and run only affected checks.
Do not open `.stewards/PROTOCOL.md` or `.stewards/manifest.toml` unless the task is an explicit review/audit or steward-network maintenance.

## Protects

| Invariant | Sev | Backing | Proof / anchor |
| --- | --- | --- | --- |
| Release-note collection preserves markers, issues, dependencies, commits, placeholders, pagination, and actionable failure context. | P0 | machine-backed | `uv run pytest tests/action tests/templates/test_github_report_contracts.py -q` (`action-suite`) |
| Action support validates its typed report payload before templates consume it. | P0 | machine-backed | `uv run pytest tests/action tests/templates/test_github_report_contracts.py -q` (`action-suite`) |

## Guardrails

- GitHub data collection is read-only, paginated, range-validated, and checked against the report contract before rendering.
- Malformed responses, missing refs, and divergent ranges fail with actionable context rather than partial reports.

## Edges

- executed-by → **github** (workflow/action runtime)
- feeds → **templates** (release-note report data)

## Owns

- **code:** `action_support/`, `action.yml`
- **tests:** `tests/action/`
- **docs:** `site/content/docs/usage/github-action.md`
