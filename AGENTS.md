# Kida Agent Constitution

## North Star
Kida exists to bring a statically validated component model to pure Python templates on free-threaded Python 3.14t. Typed props, named slots, scoped state, error boundaries, render-surface parity, and predictable concurrency are the reason this project exists; changes should strengthen that story or stay out.

For syntax and API reference, read `CLAUDE.md`. This file is the operating constitution for agents.

## Non-Negotiables
- Pure Python runtime. `dependencies = []` is a contract; optional extras are the escape valve.
- Compile-time beats runtime when the compiler, analyzer, or partial evaluator can safely decide.
- Static safety beats dynamic convenience: top-level-only defs/regions, block-scoped `set`, and unknown call-param errors are features.
- Free-threading is real: public APIs must remain safe with `PYTHON_GIL=0`; render state stays local or in `ContextVar`; environment mutation stays copy-on-write.
- HTML, terminal, markdown, and CI-report surfaces move together. Surface drift is a regression.
- The sandbox is defense-in-depth, not an isolation boundary. Never market it as security by itself.
- Diagnostics are product surface: errors need codes, template path or line/col where possible, and a next action.

## Architecture Boundaries
- `src/kida/__init__.py`, `Environment`, `Template`, loaders, filters/tests/globals, `Extension`, sandbox types, and the `kida` CLI are public contracts.
- `lexer.py`, `parser/`, `nodes/`, `compiler/`, and `formatter.py` define syntax semantics. New syntax crosses all of them plus analysis and tests.
- `analysis/` owns static metadata, dependency discovery, purity, type/call validation, a11y, coverage, and pre-render checks.
- `template/`, `render_context.py`, `render_accumulator.py`, caches, and worker utilities own runtime behavior and thread-safety assumptions.
- `terminal/`, `markdown/`, `environment/terminal.py`, `environment/markdown.py`, render-surface filters, `templates/`, and `.github/kida-templates/` own non-HTML output.
- `schemas/amp/v1/` and CI report templates are published data contracts for agent and GitHub Action output.

## Stakes
- Compiler or parser bugs silently miscompile user output; a wrong escape can become XSS in Bengal, Chirp, or another downstream app.
- Render-surface drift breaks CI summaries, PR comments, terminal dashboards, SSH sessions, and docs examples.
- Free-threaded races normalize flaky Python 3.14t behavior for every downstream user.
- Sandbox bypasses can become CVE-class issues if users over-trust the sandbox.
- Bad diagnostics turn bulk template migrations into route-by-route debugging.
- Performance regressions weaken the public benchmark and adoption story.

## Stop And Ask
- Public API or CLI changes, including `__all__`, `Environment(...)`, `Template`, loaders, extensions, sandbox policy, and worker tuning.
- New runtime dependencies, C extensions, build or release pipeline changes, or new config surfaces.
- New AST node, tag, top-level filter/test/global, render surface, schema version, or GitHub Action behavior.
- Sandbox semantic changes, even tightening.
- Shared mutable state, caches, singletons, or concurrency-sensitive changes.
- Test expectations and code behavior disagree.
- A reported bug cannot be reproduced with a minimal template and render context.
- Hot-path changes in `lexer.py`, `parser/`, `compiler/`, `render_accumulator.py`, caches, workers, or render-surface escaping without benchmark evidence.

## Anti-Patterns
- Adding flexibility by loosening static checks.
- Adding speculative knobs to `Environment`, sandbox policy, CLI flags, schemas, or report templates.
- Treating one render surface as the only surface affected.
- Swallowing exceptions, adding `# type: ignore`, or growing per-file lint/type ignores to get green checks.
- Validating deep inside internal code instead of at parser/public API boundaries.
- Adding a tag where `{% def %}`, `{% slot %}`, `{% call %}`, `{% region %}`, or composition already fits.
- Closing sandbox or escaping issues without a regression test.
- Folding adjacent refactors into a focused bug fix.

## Steward System
- Read this root file plus the closest scoped `AGENTS.md` before changing files.
- Root is the constitution and routing guide; scoped files are domain stewards.
- Scoped stewards own local invariants, refusal patterns, diagnostics, docs, tests, fixtures, examples, and checks.
- Cross-boundary work needs `Steward Notes` in the PR description naming consulted stewards, risks, evidence, and unresolved tradeoffs.

Stewards use this operating model:
- **Point of View:** who or what the domain represents.
- **Protect:** invariants, contracts, quality bars, and failure modes.
- **Advocate:** features, fixes, and investments the domain should push for.
- **Serve Peers:** upstream/downstream domains that need clearer contracts, diagnostics, docs, tests, or ergonomics.
- **Do Not:** local anti-patterns.
- **Own:** tests, docs, examples, fixtures, and maintenance checks.

## When To Consult
- Proactively consult stewards for cross-boundary, public-facing, hard-to-reverse, performance-sensitive, concurrency-sensitive, security-sensitive, or contract-affecting work.
- Use the nearest steward for local work.
- Use multiple stewards when ownership lines cross, especially syntax/compiler/analysis/render-surface work.
- Parallelize steward consultation only when questions are independent.
- Keep final synthesis with the implementing agent.

## Ask Stewards
Trigger phrase: **ask stewards**.

For implementation work, consult affected scoped stewards and return a synthesis before editing unless the request explicitly says to proceed. For backlog, roadmap, or prioritization work, consult all scoped stewards and produce a rollup with raw steward signals, confidence, dependencies, risks, convergence, minority reports, ranked backlog, and not-now items.

## Extension Routing
- Custom tags and compiler hooks: `src/kida/extensions.py`, `src/kida/parser/`, `src/kida/compiler/`, `src/kida/nodes/`, plus `examples/extensions/`.
- Filters/tests/globals: `src/kida/environment/filters/`, `src/kida/environment/tests.py`, `src/kida/environment/globals.py`, and `site/content/docs/extending/`.
- Loaders and template resolution: `src/kida/environment/loaders.py`, `src/kida/utils/template_keys.py`, and relative-resolution tests.
- Framework adapters: `src/kida/contrib/`.
- Render surfaces and report templates: `src/kida/terminal/`, `src/kida/markdown/`, `templates/`, `.github/kida-templates/`, and `schemas/amp/v1/`.

## Done Criteria
- `make lint` and `make ty` clean; no new `# type: ignore`, `noqa: S110/S112`, or per-file ignore growth.
- Focused tests cover the interesting path, including malformed source for parser changes, failure paths for sandbox/diagnostics, both sides of flags, and parity corpus updates for render surfaces.
- Hot-path or compiler changes include benchmark evidence or a clear reason benchmarks were not applicable.
- Free-threaded changes explain shared-state, cache, lock, and `ContextVar` reasoning.
- Public API changes include docs under `site/content/docs/`, changelog fragment or release note, and migration notes when breaking.
- New warnings/errors carry `ErrorCode`, location where possible, and a useful suggestion.
- `make verify-stability` for release-critical, public-contract, sandbox, render-surface, or concurrency work.

## Review Notes
- Commit subjects use existing style: `feat:`, `fix:`, `refactor:`, `docs:`, or `release:`; do not add PR numbers manually.
- Keep one concern per PR unless a bundled refactor is the actual fix.
- Put the why in the PR description; let the diff show the what.
- Flag weird tests, dead branches, parser/analysis disagreements, baseline drift, benchmark variance, and downstream compatibility surprises.
