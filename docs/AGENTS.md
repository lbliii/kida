<!-- generated from .stewards/manifest.toml — edit the manifest, not this file -->

# Steward: docs

Preserve internal rationale, audits, investigations, stability gates, and superseded-plan history without presenting aspirations as shipped behavior.

Ordinary work: use this map directly with the root map and run only affected checks.
Do not open `.stewards/PROTOCOL.md` or `.stewards/manifest.toml` unless the task is an explicit review/audit or steward-network maintenance.

## Protects

| Invariant | Sev | Backing | Proof / anchor |
| --- | --- | --- | --- |
| Internal stability guidance accurately describes current commands, coverage, safety, package, release, and benchmark evidence. | P1 | manual | docs/stability-gate.md · `## Local Stability Gate` |

## Guardrails

- Contract docs name evidence, scope, status, unresolved risk, and current source paths.
- User-facing how-to material is routed or linked to the published site.

## Edges

- informs → **site** (published guidance)
- records → **plan** (decisions and closure)

## Owns

- **code:** `docs/`
- **tests:** `tests/test_docs_install_snippets.py`
- **docs:** `docs/`
