<!-- generated from .stewards/manifest.toml — edit the manifest, not this file -->

# Steward: tests

Keep executable evidence focused on user paths, escaped bugs, deterministic concurrency, stable diagnostics, and realistic fixtures.

Ordinary work: use this map directly with the root map and run only affected checks.
Do not open `.stewards/PROTOCOL.md` or `.stewards/manifest.toml` unless the task is an explicit review/audit or steward-network maintenance.

## Protects

| Invariant | Sev | Backing | Proof / anchor |
| --- | --- | --- | --- |
| The full test corpus and focused safety suites remain executable through repository-supported commands. | P1 | machine-backed | `make test` (`full-tests`) |

## Guardrails

- Change tests only after deciding whether code or expectation is authoritative.
- Safety and concurrency regressions use adversarial or synchronized proof rather than sleeps, tolerance growth, or snapshot churn.

## Edges

- proves → **root** (repository contracts)
- sanity-checks → **benchmarks** (outputs before timing)

## Owns

- **code:** `tests/`
- **tests:** `tests/`
- **docs:** `docs/stability-gate.md`

## Do Not

- Add sleeps for concurrency correctness.
- Broaden tolerances or update snapshots without explaining sensitivity.
