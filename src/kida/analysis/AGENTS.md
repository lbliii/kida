<!-- generated from .stewards/manifest.toml — edit the manifest, not this file -->

# Steward: analysis

Catch dependency, type, call, purity, privacy, a11y, coverage, and fragile-path mistakes before rendering.

Ordinary work: use this map directly with the root map and run only affected checks.
Do not open `.stewards/PROTOCOL.md` or `.stewards/manifest.toml` unless the task is an explicit review/audit or steward-network maintenance.

## Protects

| Invariant | Sev | Backing | Proof / anchor |
| --- | --- | --- | --- |
| Static findings preserve stable codes, source facts, structured formats, and actionable suggestions. | P0 | machine-backed | `uv run pytest tests/analysis tests/test_analysis_error_codes.py tests/test_validate_call_types.py tests/test_check_diagnostic_formats.py -q` (`analysis-suite`) |
| Call, type, purity, context, privacy, a11y, and path analysis remains conservative and agrees with executable semantics. | P1 | machine-backed | `uv run pytest tests/analysis tests/test_analysis_error_codes.py tests/test_validate_call_types.py tests/test_check_diagnostic_formats.py -q` (`analysis-suite`) |

## Guardrails

- Diagnostics include stable codes, template/source location, structured facts, and a next action.
- Analysis never accepts a construct the parser/compiler rejects and never marks unknown side effects pure.

## Edges

- reads → **syntax** (source-attributed AST)
- reported-by → **cli** (text, JSON, and SARIF)

## Owns

- **code:** `src/kida/analysis/`, `src/kida/diagnostics.py`, `src/kida/_diagnostic_adapters.py`
- **tests:** `tests/analysis/`, `tests/test_analysis_error_codes.py`, `tests/test_validate_call_types.py`
- **docs:** `site/content/docs/advanced/analysis.md`, `site/content/docs/advanced/type-checking.md`
