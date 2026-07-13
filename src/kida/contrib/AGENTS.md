<!-- generated from .stewards/manifest.toml — edit the manifest, not this file -->

# Steward: contrib

Translate Kida into Django, Flask, Starlette, and future framework lifecycles without making them runtime dependencies.

Ordinary work: use this map directly with the root map and run only affected checks.
Do not open `.stewards/PROTOCOL.md` or `.stewards/manifest.toml` unless the task is an explicit review/audit or steward-network maintenance.

## Protects

| Invariant | Sev | Backing | Proof / anchor |
| --- | --- | --- | --- |
| Django, Flask, and Starlette adapters remain optional, thin, diagnosable, path-safe, and sync/async compatible. | P1 | machine-backed | `uv run pytest tests/contrib tests/test_examples.py -q` (`contrib-suite`) |

## Guardrails

- Framework imports are guarded and adapters remain thin compositions of Environment, loader, and Template contracts.
- Adapters preserve Kida diagnostics, async behavior, escaping, and path safety rather than inventing framework-only semantics.

## Edges

- configures → **environment** (loaders and context)
- calls → **template** (sync and async rendering)

## Owns

- **code:** `src/kida/contrib/`
- **tests:** `tests/contrib/`, `tests/test_examples.py`
- **docs:** `site/content/docs/usage/framework-integration.md`, `site/content/docs/tutorials/`
