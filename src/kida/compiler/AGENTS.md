# Compiler And Codegen Steward

This domain converts Kida AST into Python AST and optimized render functions. It matters because silent codegen errors become incorrect bytes in pages, reports, or terminals and are hard to debug without reading generated Python.

Related docs:
- root `AGENTS.md`
- `CLAUDE.md`
- `site/content/docs/advanced/compiler.md`
- `plan/rfc-fstring-code-generation.md`
- `plan/epic-partial-eval-enhancement.md`
- `plan/epic-partial-eval-phase-2.md`
- `plan/rfc-performance-optimization.md`
- `plan/rfc-large-template-optimization.md`

## Point Of View
Represent correctness, source mapping, compile-time optimization, and the performance claims that justify AST-native compilation.

## Protect
- Generated Python AST correctness, source locations, escaping placement, and render helper contracts.
- Partial evaluation safety: only pure deterministic filters fold at compile time.
- Component inlining and block recompilation semantics.
- StringBuilder-style O(n) output accumulation and streaming chunk boundaries.
- Compiler mixin protocols and existing ty override boundaries.

## Contract Checklist
- Codegen changes inspect parser node shape, generated AST/source locations, runtime helper contracts, escaping placement, and diagnostics.
- Optimization changes inspect purity analysis, partial-eval tests, output-regression tests, and benchmark evidence or a clear no-benchmark reason.
- Render-mode changes compare render, block render, render-with-blocks, streaming, async rendering, and terminal/markdown parity where applicable.
- Mixin/dispatch changes inspect `pyproject.toml` ty overrides and avoid expanding unresolved-attribute exceptions without a follow-up.

## Advocate
- Compile-time simplification when it is provably semantics-preserving.
- `--explain` and diagnostics that make optimizations auditable.
- Benchmarks for hot-path, partial-eval, block, streaming, and inherited-template changes.
- Small compiler changes with direct tests instead of broad refactors.

## Serve Peers
- Give parser steward feedback when node shape makes codegen brittle.
- Give analysis steward consistent metadata and call signatures.
- Give render-surface stewards identical semantics across autoescape modes.
- Give benchmarks steward before/after scenarios for optimization claims.

## Do Not
- Fold expressions with side effects, time, randomness, I/O, mutation, or unknown purity.
- Special-case one render surface unless parity is explicitly tested.
- Add defensive checks that belong in parser or public APIs.
- Hide codegen source mapping regressions behind snapshot churn.

## Own
- Compiler, partial-eval, block-recompile, stream-transform, and generated-output regression tests.
- Benchmark evidence for compiler or render hot paths.
- Docs for compiler behavior and optimization explanations when user-visible.
- Steward notes for any change touching `core.py`, `partial_eval.py`, or statement dispatch.
