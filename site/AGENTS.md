<!-- generated from .stewards/manifest.toml — edit the manifest, not this file -->

# Steward: site

Keep published installation, syntax, API, migration, troubleshooting, release, and integration guidance aligned with tested Kida behavior.

Ordinary work: use this map directly with the root map and run only affected checks.
Do not open `.stewards/PROTOCOL.md` or `.stewards/manifest.toml` unless the task is an explicit review/audit or steward-network maintenance.

## Protects

| Invariant | Sev | Backing | Proof / anchor |
| --- | --- | --- | --- |
| Published install, migration, syntax, framework, and free-threading guidance matches tested package and language behavior. | P1 | machine-backed | `uv run pytest tests/test_docs_install_snippets.py tests/test_explicit_closer_documentation.py -q` (`docs-contract`) |

## Guardrails

- Reference docs distinguish stable contracts from advanced/internal hooks.
- Generated site output is never edited as source and performance claims cite benchmark platform and command.

## Edges

- teaches-through → **examples** (runnable snippets)
- documents → **public** (API and runtime)

## Owns

- **code:** `site/config/`, `site/content/`
- **tests:** `tests/test_docs_install_snippets.py`, `tests/test_explicit_closer_documentation.py`
- **docs:** `site/content/docs/`, `site/content/releases/`
