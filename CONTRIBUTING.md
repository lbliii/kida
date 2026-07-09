# Contributing to Kida

Kida is a pure-Python template engine built around static validation, predictable
rendering, and free-threaded Python 3.14t. Contributions should preserve those
contracts and keep changes focused.

## Development setup

Kida requires Python 3.14 or newer. The Makefile and free-threading checks use
the free-threaded `3.14t` build by default. Install
[`uv`](https://docs.astral.sh/uv/), then create and populate the development
environment:

```bash
make setup
make install
```

`make setup` creates `.venv` with `PYTHON_VERSION=3.14t` by default, and
`make install` syncs the locked development dependencies. To use an existing
environment instead, run:

```bash
uv sync --group dev --frozen
```

The package itself must remain dependency-free: `dependencies = []` in
`pyproject.toml` is a public contract. Optional integrations and performance
helpers belong in optional extras or development groups, not the runtime
dependency list.

## Before changing code

Read these repository guides before starting:

- `AGENTS.md` for project-wide contracts, risk boundaries, and completion
  criteria.
- The closest scoped `AGENTS.md` for the files you will change.
- `CLAUDE.md` for syntax, APIs, project structure, and common semantic traps.

Stop and discuss the approach before changing a public API or CLI, syntax or AST
shape, runtime dependencies, sandbox policy, shared mutable state, concurrency
behavior, or worker tuning. Also stop before adding a render surface or schema
version, or changing GitHub Action behavior. Hot-path changes in the lexer,
parser, compiler, render accumulator, caches, workers, or render-surface
escaping also need benchmark evidence before they change.

Keep one concern per contribution. Do not bundle adjacent refactors into a
focused fix, loosen static checks for convenience, or add suppressions such as
`# type: ignore`, `noqa: S110`, or `noqa: S112` to make checks pass.

## Issues

Bug reports should include:

- the Kida version;
- the Python version and whether the build is free-threaded;
- a minimal template and render context that reproduce the problem; and
- the complete error message or diagnostic.

Use the repository's existing hierarchy for planned work: **Saga** is a
cross-cutting strategic thread, **Epic** is a major initiative with a task
checklist, and **Task** is a concrete work item. Link the relevant issue from
the pull request when one exists.

## Implementing a change

Prefer decisions at compile or analysis time when they can be made safely.
Static restrictions such as top-level-only definitions and regions,
block-scoped `set`, and unknown call-parameter errors are intentional.

Preserve all affected contracts together:

- HTML, terminal, Markdown, and CI-report surfaces must stay in parity.
- Syntax changes cross the lexer, parser, nodes, compiler, formatter, analysis,
  malformed-source tests, and user-facing docs.
- New warnings and errors need an `ErrorCode`, source location where possible,
  a useful next action, and failure-path tests.
- User-facing behavior changes update published docs under
  `site/content/docs/`, relevant examples or scaffolds, and tests in the same
  pull request.
- Public API changes also need a changelog fragment or release note, plus
  migration guidance when breaking. Towncrier fragments live in `changelog.d/`
  and use the configured `added`, `changed`, `deprecated`, `removed`, `fixed`,
  or `security` categories.

The sandbox is defense in depth, not an isolation boundary. Sandbox and escaping
fixes require regression tests and must not be described as providing complete
security isolation.

## Free-threading expectations

Public APIs must remain safe with `PYTHON_GIL=0`. Keep render state local or in
`ContextVar`, and keep environment mutation copy-on-write. Avoid shared mutable
state, caches, and singletons unless their synchronization and ownership are
explicitly reviewed.

Concurrency-sensitive changes should explain shared state, cache behavior,
locks, and `ContextVar` use in the pull request. Test them on free-threaded
Python with the GIL disabled; do not rely on sleeps or timing assumptions where
synchronization can prove correctness.

## Tests and checks

Run the smallest focused test while developing, then the checks that match the
change:

| Command | Purpose |
| --- | --- |
| `make test` | Full test suite across `tests/` and `examples/` |
| `make test-cov` | Full suite with the repository coverage gate |
| `make lint` | Repository-wide Ruff lint |
| `make format-check` | Verify Ruff formatting |
| `make ty` | Type-check `src/kida/` and `action_support/` |
| `make test-thread` | Free-threaded stress tests under `PYTHON_GIL=0` |
| `make test-safety` | Focused render, sandbox, cache, and concurrency safety tests |
| `make package-smoke` | Build and smoke-test installed artifacts |
| `make docs` | Build the Bengal documentation site |
| `make verify-stability` | Full stability gate for high-risk or release-critical changes |

Focused tests must cover the interesting behavior and its failure path. Parser
changes include malformed source; diagnostics and sandbox changes include
actionable failures; flags cover both values; render-surface changes update the
parity corpus. Hot-path changes include before/after benchmark evidence, or a
clear explanation of why a benchmark does not apply. See
`docs/stability-gate.md` for the release and benchmark protocols.

Run `make verify-stability` for release-critical, public-contract, sandbox,
render-surface, or concurrency work. It combines lint, format, type, coverage,
GIL-disabled safety, and package-smoke checks.

## Pull requests

Pull requests should explain why the change is needed, identify affected
contracts and risks, and report the exact proof run locally. Let the diff show
the implementation details. Call out unusual tests, benchmark or baseline
changes, free-threading assumptions, suppressions, steward disagreement,
deferred work, and downstream compatibility risks.

Cross-boundary changes include a **Steward Notes** section naming the consulted
stewards, risks, evidence, and unresolved tradeoffs. Multi-surface contract
changes also include a parity matrix covering the applicable API/CLI,
programmatic, protocol, schema/type, docs, example, and test surfaces. Every
accepted steward finding needs test, docs, example, or benchmark proof, or an
explicit no-impact reason.

Use the repository's existing commit subject style: `feat:`, `fix:`,
`refactor:`, `docs:`, or `release:`. Do not add pull request numbers manually.
