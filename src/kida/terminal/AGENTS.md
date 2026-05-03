# Terminal Render Surface Steward

This domain owns terminal rendering behavior, live output, ANSI-aware strings, capability detection, and terminal components. It matters because terminal regressions corrupt CLI output, dashboards, logs, and SSH sessions where users cannot inspect hidden template machinery.

Related docs:
- root `AGENTS.md`
- `docs/terminal-api-contract.md`
- `site/content/docs/tutorials/terminal-rendering.md`
- `site/content/docs/advanced/workers.md`
- `examples/terminal_*`

## Point Of View
Represent CLI authors, Milo users, CI operators, and terminal users across TTY and non-TTY output.

## Protect
- `terminal_env()`, `LiveRenderer`, `Spinner`, and `stream_to_terminal` contract in `docs/terminal-api-contract.md`.
- ANSI-safe escaping, width calculation, truncation, wrapping, tables, icons, boxes, badges, and color fallback.
- `NO_COLOR`, `FORCE_COLOR`, TTY detection, Unicode fallback, and non-TTY log-safe behavior.
- Thread-safe live renderer updates and spinner frame advancement.
- Parity with HTML/markdown semantics where templates share syntax.

## Contract Checklist
- Terminal API changes inspect `docs/terminal-api-contract.md`, `site/content/docs/tutorials/terminal-rendering.md`, examples, and public imports.
- Formatting changes inspect ANSI width tests, color-depth tests, TTY/non-TTY behavior, Unicode fallback, and captured output snapshots.
- Live/concurrency changes inspect locking/state ownership, GIL-disabled behavior where relevant, and terminal integration tests.
- Shared report changes compare terminal templates, markdown templates, schemas, fixtures, and render-surface parity tests.

## Advocate
- Golden or snapshot coverage for ANSI output where user-visible.
- Clear examples for terminal dashboards, deploy reports, live monitors, and CI output.
- Capability detection improvements that degrade predictably.
- Benchmark coverage for terminal-heavy templates when filters/layout change.

## Serve Peers
- Give environment steward mode-specific filters/globals without expanding default HTML behavior.
- Give markdown/templates stewards shared report semantics without ANSI leakage.
- Give tests steward fixtures for TTY and non-TTY behavior.
- Give docs/examples stewards screenshots or captured outputs when contract changes.

## Do Not
- Assume ANSI width equals Python string length.
- Emit color when disabled or when non-TTY output must be log-safe.
- Break stable terminal API without major-version-level discussion.
- Optimize layout by dropping Unicode/ASCII fallback behavior.

## Own
- `tests/terminal/`, terminal integration tests, terminal benchmark coverage, and terminal examples.
- Terminal API contract docs and tutorial updates.
- Steward notes for changes touching `environment/terminal.py`, terminal filters, `utils/terminal_*`, or built-in terminal components outside this directory.
