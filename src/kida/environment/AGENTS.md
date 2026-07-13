<!-- generated from .stewards/manifest.toml — edit the manifest, not this file -->

# Steward: environment

Keep loaders, Environment configuration, registries, built-ins, extension hooks, and autoescape setup stable and thread-safe.

Ordinary work: use this map directly with the root map and run only affected checks.
Do not open `.stewards/PROTOCOL.md` or `.stewards/manifest.toml` unless the task is an explicit review/audit or steward-network maintenance.

## Protects

| Invariant | Sev | Backing | Proof / anchor |
| --- | --- | --- | --- |
| Environment filters, tests, globals, extensions, and mode factories preserve copy-on-write isolation and defaults. | P0 | machine-backed | `uv run pytest tests/test_kida_environment.py tests/test_relative_template_resolution.py tests/test_template_aliases.py tests/test_kida_filters.py -q` (`environment-suite`) |
| Loaders preserve aliases and relative resolution while rejecting traversal and explaining missing templates. | P0 | machine-backed | `uv run pytest tests/test_kida_environment.py tests/test_relative_template_resolution.py tests/test_template_aliases.py tests/test_kida_filters.py -q` (`environment-suite`) |

## Guardrails

- Filters, tests, and globals use copy-on-write registration rather than shared in-place mutation.
- File and package resolution reject traversal and preserve aliases, relative lookup, and actionable TemplateNotFoundError suggestions.
- Optional integrations stay absent from minimal imports.

## Edges

- uses → **utils** (template keys and escaping)
- adapted-by → **contrib** (framework setup)

## Owns

- **code:** `src/kida/environment/`, `src/kida/extensions.py`
- **tests:** `tests/test_kida_environment.py`, `tests/test_relative_template_resolution.py`, `tests/test_template_aliases.py`
- **docs:** `site/content/docs/reference/configuration.md`, `site/content/docs/extending/`
