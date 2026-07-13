<!-- generated from .stewards/manifest.toml — edit the manifest, not this file -->

# Steward: terminal

Protect terminal rendering, ANSI-aware strings, capability detection, live output, and log-safe degradation.

Ordinary work: use this map directly with the root map and run only affected checks.
Do not open `.stewards/PROTOCOL.md` or `.stewards/manifest.toml` unless the task is an explicit review/audit or steward-network maintenance.

## Protects

| Invariant | Sev | Backing | Proof / anchor |
| --- | --- | --- | --- |
| ANSI-aware width, truncation, wrapping, tables, colors, and Unicode fallback remain correct. | P0 | machine-backed | `uv run pytest tests/terminal tests/test_terminal_colors.py -q` (`terminal-suite`) |
| Terminal environments, TTY capabilities, live rendering, and non-TTY degradation remain stable and thread-safe. | P1 | machine-backed | `uv run pytest tests/terminal tests/test_terminal_colors.py -q` (`terminal-suite`) |

## Guardrails

- Visible width is not Python string length; truncation, wrapping, tables, and alignment remain ANSI-aware.
- NO_COLOR, FORCE_COLOR, TTY/non-TTY, color depth, Unicode fallback, and concurrent live updates remain explicit contracts.

## Edges

- uses → **utils** (ANSI width and safe strings)
- shares → **templates** (report intent)

## Owns

- **code:** `src/kida/terminal/`, `src/kida/environment/terminal.py`
- **tests:** `tests/terminal/`, `tests/test_terminal_colors.py`
- **docs:** `docs/terminal-api-contract.md`, `site/content/docs/usage/terminal-rendering.md`
