<!-- generated from .stewards/manifest.toml — edit the manifest, not this file -->

# Steward: examples

Keep runnable examples canonical, focused, tested, dependency-isolated, and safe to copy into real applications.

Ordinary work: use this map directly with the root map and run only affected checks.
Do not open `.stewards/PROTOCOL.md` or `.stewards/manifest.toml` unless the task is an explicit review/audit or steward-network maintenance.

## Protects

| Invariant | Sev | Backing | Proof / anchor |
| --- | --- | --- | --- |
| Runnable examples remain listed, importable, dependency-isolated, and aligned with preferred Kida usage. | P1 | machine-backed | `uv run pytest tests/test_examples.py -q` (`examples-suite`) |

## Guardrails

- Examples teach Kida patterns rather than legacy shortcuts and call out block-scoped set, no super, and slot-in-call migration traps.
- Terminal, markdown, framework, and CI examples remain aligned with their surface contracts.

## Edges

- supplies → **site** (runnable tutorial source)
- exercises → **contrib** (framework adapters)

## Owns

- **code:** `examples/`
- **tests:** `tests/test_examples.py`
- **docs:** `examples/README.md`, `site/content/docs/tutorials/`
