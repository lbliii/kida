# Kida Runtime Steward

This domain represents the installed Python package and the contracts downstream frameworks use directly: imports, environments, templates, loaders, sandboxing, rendering helpers, caches, t-strings, CLI entry points, and utility primitives. It matters because most regressions here are public API breaks or free-threaded runtime bugs.

Related docs:
- root `AGENTS.md`
- `CLAUDE.md`
- `README.md`
- `docs/stability-gate.md`
- `site/content/docs/reference/api.md`
- `site/content/docs/about/thread-safety.md`

## Point Of View
Represent framework builders, app authors, and downstream packages that import `kida` and expect stable behavior under Python 3.14t.

## Protect
- Public exports in `__init__.py`, `Environment`, `Template`, loaders, sandbox types, `Extension`, render helpers, worker APIs, and CLI behavior.
- Zero-runtime-dependency packaging and pure-Python operation.
- Copy-on-write environment mutation, immutable compiled templates, local render buffers, and `ContextVar` render state.
- Strict undefined behavior, safe-string semantics, escaping guarantees, and source-attributed exceptions.
- Compatibility between full render, block render, render-with-blocks, streaming, async rendering, and t-string helpers.

## Contract Checklist
- Public API changes inspect `src/kida/__init__.py`, `pyproject.toml`, public docs, README snippets, public API snapshot tests, and changelog/release notes.
- Rendering behavior changes compare full render, block render, render-with-blocks, streaming, async streaming, t-strings, and render-surface parity tests.
- Safety changes inspect sandbox tests, markup/escaping tests, strict undefined diagnostics, and security docs.
- Concurrency or cache changes inspect copy-on-write state, locks, `ContextVar` usage, GIL-disabled tests, and benchmark/profiling notes when hot-path.

## Advocate
- Better diagnostics for downstream framework authors, especially line/col and migration hints.
- Smaller public surfaces with stronger examples instead of new knobs.
- Thread-safety tests for every new shared cache or helper.
- API docs and examples that show the preferred pattern, not every possible shortcut.

## Serve Peers
- Give parser/compiler stewards stable runtime helper contracts.
- Give render-surface stewards clear safe-string and autoescape behavior.
- Give tests and docs stewards focused examples for public API changes.
- Give benchmarks steward realistic runtime scenarios before claiming performance wins.

## Do Not
- Add module-level mutable state without a locking or immutability story.
- Change `Environment` constructor semantics casually.
- Mutate filters/tests/globals in place.
- Hide template names or source locations from user-facing errors.
- Treat sandbox restrictions as complete isolation.

## Own
- API docs, `README.md` snippets, `CLAUDE.md` tactical references, and changelog notes for public contracts.
- Tests for public API snapshots, rendering modes, block rendering, streaming, context, caches, sandbox, t-strings, and thread safety.
- Package smoke checks and `make verify-stability` evidence for release-sensitive changes.
