<!-- generated from .stewards/manifest.toml — edit the manifest, not this file -->

# Steward: nodes

Keep Kida AST shapes explicit, immutable in practice, source-attributed, and shared consistently by parser, compiler, formatter, and analysis.

Ordinary work: use this map directly with the root map and run only affected checks.
Do not open `.stewards/PROTOCOL.md` or `.stewards/manifest.toml` unless the task is an explicit review/audit or steward-network maintenance.

## Protects

| Invariant | Sev | Backing | Proof / anchor |
| --- | --- | --- | --- |
| AST node shapes remain constructible by the parser and consumable by compiler dispatch with source metadata intact. | P0 | machine-backed | `uv run pytest tests/test_kida_lexer_comprehensive.py tests/test_kida_parser_edge_cases.py tests/test_kida_modern_syntax.py tests/test_definition_toplevel_check.py tests/test_explicit_closer_documentation.py -q` (`syntax-suite`) |

## Guardrails

- New fields preserve source coordinates and have a parser, compiler, formatter, analysis, and test story.
- New node kinds are public language design and require stop-and-ask review.

## Edges

- built-by → **syntax** (parser handlers)
- compiled-by → **compiler** (statement and expression dispatch)

## Owns

- **code:** `src/kida/nodes/`
- **tests:** `tests/test_kida_parser_edge_cases.py`, `tests/test_compiler_expr_dispatch.py`
- **docs:** `site/content/docs/advanced/compiler.md`
