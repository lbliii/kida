<!-- generated from .stewards/manifest.toml — edit the manifest, not this file -->

# Steward: cli

Keep the kida command facade, lazy dispatch, exit policy, and text/JSON/SARIF output stable and scriptable.

Ordinary work: use this map directly with the root map and run only affected checks.
Do not open `.stewards/PROTOCOL.md` or `.stewards/manifest.toml` unless the task is an explicit review/audit or steward-network maintenance.

## Protects

| Invariant | Sev | Backing | Proof / anchor |
| --- | --- | --- | --- |
| CLI subcommands, flags, lazy command modules, and exit behavior remain intentional. | P1 | machine-backed | `uv run pytest tests/test_cli.py tests/test_cli_command_modules.py tests/test_cli_components.py tests/test_check_diagnostic_formats.py -q` (`cli-contract`) |
| Text, JSON, and SARIF diagnostics preserve equivalent codes, facts, coordinates, ordering, and safe edits. | P0 | machine-backed | `uv run pytest tests/test_cli.py tests/test_cli_command_modules.py tests/test_cli_components.py tests/test_check_diagnostic_formats.py -q` (`cli-contract`) |

## Guardrails

- Commands own their flags and handlers without eager-loading unrelated command modules.
- Machine output preserves codes, fields, coordinates, sorting, and stdout/stderr boundaries.

## Edges

- presents → **analysis** (static diagnostics)
- dispatches → **readme** (README scaffolding)

## Owns

- **code:** `src/kida/_cli/`, `src/kida/cli.py`, `src/kida/__main__.py`
- **tests:** `tests/test_cli.py`, `tests/test_cli_command_modules.py`, `tests/test_check_diagnostic_formats.py`
- **docs:** `site/content/docs/reference/cli.md`
