<!-- generated from .stewards/manifest.toml — edit the manifest, not this file -->

# Steward: compiler

Protect Python-AST code generation, escaping placement, source mapping, and semantics-preserving optimization.

Ordinary work: use this map directly with the root map and run only affected checks.
Do not open `.stewards/PROTOCOL.md` or `.stewards/manifest.toml` unless the task is an explicit review/audit or steward-network maintenance.

## Protects

| Invariant | Sev | Backing | Proof / anchor |
| --- | --- | --- | --- |
| Generated Python AST preserves output, escaping placement, block semantics, and source-attributed errors. | P0 | machine-backed | `uv run pytest tests/test_kida_compile_validation.py tests/test_compiler_analysis_phases.py tests/test_partial_eval.py tests/test_block_recompile.py tests/test_fstring_coalescing.py -q` (`compiler-suite`) |
| Partial evaluation folds only deterministic pure work and preserves behavior when optimization does not apply. | P0 | machine-backed | `uv run pytest tests/test_kida_compile_validation.py tests/test_compiler_analysis_phases.py tests/test_partial_eval.py tests/test_block_recompile.py tests/test_fstring_coalescing.py -q` (`compiler-suite`) |
| Nested slot callbacks remain normal callable scopes when an outer block body is transformed from append operations to stream yields. | P0 | none | — |

## Guardrails

- Only pure deterministic expressions fold at compile time.
- Full, block, streaming, async, inherited, and non-HTML paths cannot silently receive different codegen semantics.
- Hot-path edits carry output proof and benchmark evidence or a bounded no-benchmark reason.

## Edges

- consumes → **nodes** (AST shapes)
- consults → **analysis** (purity and call metadata)
- emits → **template** (runtime render functions)

## Owns

- **code:** `src/kida/compiler/`
- **tests:** `tests/test_kida_compile_validation.py`, `tests/test_partial_eval.py`, `tests/test_block_recompile.py`
- **docs:** `site/content/docs/advanced/compiler.md`

## Advocate

- Add a nested call/yield case to the render-surface parity corpus before changing sync-to-stream callback handling.

## Do Not

- Fold time, randomness, I/O, mutation, or unknown-purity calls.
- Hide source-map or output regressions behind snapshot churn.
