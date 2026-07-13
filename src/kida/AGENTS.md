<!-- generated from .stewards/manifest.toml — edit the manifest, not this file -->

# Steward: public

Represent downstream frameworks and application authors importing Kida under Python 3.14t.

Ordinary work: use this map directly with the root map and run only affected checks.
Do not open `.stewards/PROTOCOL.md` or `.stewards/manifest.toml` unless the task is an explicit review/audit or steward-network maintenance.

## Protects

| Invariant | Sev | Backing | Proof / anchor |
| --- | --- | --- | --- |
| Every top-level export is classified exactly once and public signatures remain snapshotted. | P0 | machine-backed | `uv run pytest tests/test_public_api_snapshot.py tests/test_public_api_classification.py tests/test_public_diagnostics.py tests/test_release_contract.py -q` (`public-contract`) |
| Strict undefined, safe-string, autoescape, and sandbox public behavior stays explicit and tested. | P0 | machine-backed | `uv run pytest tests/test_sandbox_fuzz.py tests/test_markup_security.py tests/test_strict_mode.py -q` (`sandbox-suite`) |
| The built wheel imports, renders, exposes CLI metadata, and enforces sandbox denial without undeclared dependencies. | P1 | machine-backed | `uv run python scripts/package_smoke.py` (`package-smoke`) |

## Guardrails

- Public exports, signatures, ErrorCode values, strict defaults, loaders, sandbox types, and worker APIs change intentionally and together.
- Compiled templates are immutable; render buffers are local; environment registries are copy-on-write; shared caches are lock-guarded.
- SandboxedEnvironment reduces capability but does not isolate adversarial code; suspected escapes follow the private reporting protocol in SECURITY.md before public disclosure.

## Edges

- configured-by → **environment** (loaders and registries)
- executed-by → **template** (render APIs)

## Owns

- **code:** `src/kida/*.py`
- **tests:** `tests/test_public_api_snapshot.py`, `tests/test_markup_security.py`, `tests/test_kida_stress_test.py`
- **docs:** `README.md`, `CLAUDE.md`, `SECURITY.md`, `site/content/docs/reference/api.md`

## Do Not

- Add module-level mutable state without an immutability, lock, or ContextVar story.
- Describe the sandbox as complete isolation.
