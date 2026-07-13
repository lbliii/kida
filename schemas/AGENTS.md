<!-- generated from .stewards/manifest.toml — edit the manifest, not this file -->

# Steward: schemas

Protect versioned AMP and diagnostic JSON schemas consumed by agents, templates, CLI output, and CI.

Ordinary work: use this map directly with the root map and run only affected checks.
Do not open `.stewards/PROTOCOL.md` or `.stewards/manifest.toml` unless the task is an explicit review/audit or steward-network maintenance.

## Protects

| Invariant | Sev | Backing | Proof / anchor |
| --- | --- | --- | --- |
| AMP and diagnostic v1 payloads validate against versioned schemas with stable enums, required fields, and template routing. | P0 | machine-backed | `uv run pytest tests/templates/test_amp_schema_contracts.py tests/test_check_diagnostic_formats.py -q` (`schema-suite`) |

## Guardrails

- Required fields, enums, severity, confidence, privacy, and fallback behavior remain versioned contracts.
- Breaking shapes create a new version and migration path rather than mutating v1 in place.

## Edges

- rendered-by → **templates** (report templates)
- emitted-by → **cli** (structured diagnostics)

## Owns

- **code:** `schemas/`
- **tests:** `tests/templates/test_amp_schema_contracts.py`, `tests/test_check_diagnostic_formats.py`
- **docs:** `site/content/docs/usage/amp.md`
