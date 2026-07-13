<!-- generated from .stewards/manifest.toml — edit the manifest, not this file -->

# Steward: utils

Keep safe strings, escaping, terminal width, template keys, report parsers, caches, CSP helpers, and worker decisions boring and deterministic.

Ordinary work: use this map directly with the root map and run only affected checks.
Do not open `.stewards/PROTOCOL.md` or `.stewards/manifest.toml` unless the task is an explicit review/audit or steward-network maintenance.

## Protects

| Invariant | Sev | Backing | Proof / anchor |
| --- | --- | --- | --- |
| Surface-specific safe strings, escaping, template keys, aliases, and traversal checks retain focused proof. | P0 | machine-backed | `uv run pytest tests/test_markup_security.py tests/test_template_keys.py tests/test_lru_cache_concurrency.py tests/test_workers.py tests/test_junit_xml.py tests/test_lcov.py tests/test_sarif.py -q` (`utils-suite`) |
| LRU caches, worker decisions, and JUnit/LCOV/SARIF parsers remain synchronized, deterministic, and malformed-input aware. | P1 | machine-backed | `uv run pytest tests/test_markup_security.py tests/test_template_keys.py tests/test_lru_cache_concurrency.py tests/test_workers.py tests/test_junit_xml.py tests/test_lcov.py tests/test_sarif.py -q` (`utils-suite`) |

## Guardrails

- Markup, Styled, and Marked preserve surface-specific trust protocols.
- Path resolution is structured and traversal-safe; caches and worker helpers carry lock and GIL reasoning.
- Malformed JUnit, LCOV, and SARIF input fails with actionable context.

## Edges

- serves → **environment** (loaders and registries)
- serves → **terminal** (width and capability helpers)
- serves → **markdown** (safe strings)

## Owns

- **code:** `src/kida/utils/`
- **tests:** `tests/test_markup_security.py`, `tests/test_template_keys.py`, `tests/test_workers.py`
- **docs:** `site/content/docs/usage/escaping.md`, `site/content/docs/advanced/workers.md`
