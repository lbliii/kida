<!-- generated from .stewards/manifest.toml — edit the manifest, not this file -->

# Steward: syntax

Represent template authors and every analyzer/compiler stage that trusts the parsed AST.

Ordinary work: use this map directly with the root map and run only affected checks.
Do not open `.stewards/PROTOCOL.md` or `.stewards/manifest.toml` unless the task is an explicit review/audit or steward-network maintenance.

## Protects

| Invariant | Sev | Backing | Proof / anchor |
| --- | --- | --- | --- |
| Unified endings, scoping, defs, regions, calls, slots, yield, expressions, and migration traps retain parser coverage. | P0 | machine-backed | `uv run pytest tests/test_kida_lexer_comprehensive.py tests/test_kida_parser_edge_cases.py tests/test_kida_modern_syntax.py tests/test_definition_toplevel_check.py tests/test_explicit_closer_documentation.py -q` (`syntax-suite`) |
| Malformed source fails early with the correct location and actionable syntax error. | P0 | machine-backed | `uv run pytest tests/test_kida_lexer_comprehensive.py tests/test_kida_parser_edge_cases.py tests/test_kida_modern_syntax.py tests/test_definition_toplevel_check.py tests/test_explicit_closer_documentation.py -q` (`syntax-suite`) |

## Guardrails

- Unified end, block-scoped set, top-level defs/regions, call/slot/yield composition, and exact source locations remain deliberate language rules.
- A syntax change crosses lexer, parser, nodes, compiler, formatter, analysis, malformed-source tests, and docs before it is complete.

## Edges

- produces → **nodes** (immutable AST shapes)
- consumed-by → **compiler** (code generation)
- consumed-by → **analysis** (static checks)

## Owns

- **code:** `src/kida/lexer.py`, `src/kida/parser/`, `src/kida/formatter.py`
- **tests:** `tests/test_kida_lexer_comprehensive.py`, `tests/test_kida_parser_edge_cases.py`, `tests/test_kida_modern_syntax.py`
- **docs:** `CLAUDE.md`, `site/content/docs/syntax/`

## Do Not

- Add a tag without full semantic pipeline closure.
- Move a parse-time error to runtime for convenience.
