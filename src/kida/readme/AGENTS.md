<!-- generated from .stewards/manifest.toml — edit the manifest, not this file -->

# Steward: readme

Keep `kida readme` presets accurate, deterministic, non-destructive, and aligned with current Kida syntax and packaging.

Ordinary work: use this map directly with the root map and run only affected checks.
Do not open `.stewards/PROTOCOL.md` or `.stewards/manifest.toml` unless the task is an explicit review/audit or steward-network maintenance.

## Protects

| Invariant | Sev | Backing | Proof / anchor |
| --- | --- | --- | --- |
| README presets, metadata detection, syntax snippets, dry-run, and overwrite behavior remain deterministic and current. | P1 | machine-backed | `uv run pytest tests/test_readme.py -q` (`readme-suite`) |

## Guardrails

- Generated examples compile and teach current patterns.
- Metadata detection remains local and handles missing/malformed project state; overwrite requires explicit intent.

## Edges

- invoked-by → **cli** (readme command)
- teaches → **examples** (canonical snippets)

## Owns

- **code:** `src/kida/readme/`
- **tests:** `tests/test_readme.py`
- **docs:** `site/content/docs/reference/cli.md`
