<!-- generated from .stewards/manifest.toml — edit the manifest, not this file -->

# Agent Constitution — Kida

Ordinary work: use this root map plus only scoped maps on the target path.
Do not open `.stewards/PROTOCOL.md` or `.stewards/manifest.toml` unless the task is an explicit review/audit or steward-network maintenance.

## Pillars

- Kida is a pure-Python, zero-runtime-dependency template engine for statically validated components on free-threaded Python 3.14t.
- Typed props, named and scoped slots, scoped state, diagnostics, and predictable concurrency are product contracts rather than implementation details.
- Compile-time decisions and static safety win over runtime convenience when the lexer, parser, analyzer, or compiler can decide safely.
- Full, block, streaming, async, HTML, terminal, markdown, and CI-report surfaces preserve shared intent; unexplained surface drift is a regression.
- The sandbox is defense-in-depth, never an isolation boundary, and escaping or trust-boundary changes receive adversarial proof.
- Diagnostics are public behavior: stable codes, source location where possible, and an actionable next step move with tests and docs.

## Search Discipline

- At task start, read the root map before repository discovery; never locate instructions by inventorying every AGENTS.md in the repository.
- Before reading or searching content beneath a path, open the nearest scoped map on that path; add another map only when the investigation crosses into its scope.
- If the request names an exact file, symbol, diagnostic code, template, or failing test, inspect that target before searching elsewhere.
- Search progressively: likely files, then filename or import discovery, then scoped content search; expand repository-wide only when scoped evidence fails or proves a cross-cutting dependency, and state the reason.
- Treat 10 commands or 12 content-exposed files as a strategy checkpoint, never as a hard stopping limit; record the current frontier, remaining uncertainty, and whether to continue the bounded closure or pivot to a narrower reproduction.
- For import, dependency, registration, or call-chain bugs, prove graph closure with a bounded static traversal through ancestor package initializers and repository-local module-level imports; stop at function/class bodies, TYPE_CHECKING blocks, and classified external dependencies.
- For syntax, compiler, analysis, or render bugs, prove semantic pipeline closure for the named construct: token or source form, parser handler, node shape, compiler handler, applicable analysis, runtime helper, and only the render surfaces actually reached.
- Semantic pipeline closure is bounded by references to the named node, handler, diagnostic, or helper; do not inventory whole parser, compiler, or test trees as a substitute for tracing the construct.
- Do not use repository-wide dependency, lockfile, documentation, workflow, or benchmark searches to establish import or semantic closure; broaden only after the bounded graph identifies a cross-surface contract.

## Operating Rules

- `dependencies = []` is a release contract; optional extras and thin contrib adapters are the escape valve, and minimal imports never require frameworks or C extensions.
- Static restrictions such as top-level-only defs/regions, block-scoped set, and unknown call-parameter errors are features; do not loosen them for convenience.
- HTML, terminal, markdown, serialized diagnostics, AMP schemas, report templates, and GitHub Action output move together only when the changed value flow reaches those surfaces.
- Treat `SandboxedEnvironment` as defense-in-depth; a sandbox finding is security-sensitive and never becomes a marketing claim of isolation.
- Public API, CLI, syntax, diagnostic-code, schema, render-surface, and generated-scaffold changes move with focused tests, docs/examples, release collateral, and migration notes when needed.
- New component/runtime features and downstream-observable contract changes classify pilot evidence under `docs/downstream-pilot-policy.md`; use its exact consumer record or `No downstream pilot` shape.
- `ask stewards`, `bugbash`, `review swarm`, and `steward synthesis` are explicit review triggers: open the protocol, consult independent affected maps, preserve dissent, and synthesize with evidence.
- Cross-boundary work includes Steward Notes naming consulted stewards, risks, evidence, collateral, downstream-pilot classification, and unresolved tradeoffs.
- Backlog, roadmap, and prioritization work consults all scoped stewards and preserves raw signals, confidence, dependencies, convergence, minority reports, ranked work, and not-now items.
- Generated output under `site/public/` is not source-of-truth; edit site source/config and build it or record a no-build rationale.
- Commit subjects use Kida's existing `feat:`, `fix:`, `refactor:`, `docs:`, or `release:` style without manually appended PR numbers; keep one concern per PR.
- No silent exception, unexplained type ignore, new S110/S112/noqa escape, per-file suppression growth, speculative knob, snapshot refresh without sensitivity proof, or adjacent refactor unless it is the fix.

## Network

| Steward | Map | Invariants | Automated backing |
| --- | --- | --- | --- |
| action | `action_support/AGENTS.md` | 2 | 100% |
| analysis | `src/kida/analysis/AGENTS.md` | 2 | 100% |
| benchmarks | `benchmarks/AGENTS.md` | 2 | 50% |
| cli | `src/kida/_cli/AGENTS.md` | 2 | 100% |
| compiler | `src/kida/compiler/AGENTS.md` | 3 | 66% |
| contrib | `src/kida/contrib/AGENTS.md` | 1 | 100% |
| docs | `docs/AGENTS.md` | 1 | 0% |
| environment | `src/kida/environment/AGENTS.md` | 2 | 100% |
| examples | `examples/AGENTS.md` | 1 | 100% |
| github | `.github/AGENTS.md` | 3 | 100% |
| markdown | `src/kida/markdown/AGENTS.md` | 1 | 100% |
| nodes | `src/kida/nodes/AGENTS.md` | 1 | 100% |
| plan | `plan/AGENTS.md` | 2 | 0% |
| public | `src/kida/AGENTS.md` | 3 | 100% |
| readme | `src/kida/readme/AGENTS.md` | 1 | 100% |
| root | `AGENTS.md` | 10 | 90% |
| schemas | `schemas/AGENTS.md` | 1 | 100% |
| site | `site/AGENTS.md` | 1 | 100% |
| syntax | `src/kida/parser/AGENTS.md` | 2 | 100% |
| template | `src/kida/template/AGENTS.md` | 2 | 100% |
| templates | `templates/AGENTS.md` | 1 | 100% |
| terminal | `src/kida/terminal/AGENTS.md` | 2 | 100% |
| tests | `tests/AGENTS.md` | 1 | 100% |
| utils | `src/kida/utils/AGENTS.md` | 2 | 100% |

## Protects (constitution)

| Invariant | Sev | Backing | Proof / anchor |
| --- | --- | --- | --- |
| The installed Kida package remains pure Python with an empty runtime dependency list. | P0 | machine-backed | `uv run pytest tests/stewards -q` (`steward-tools`) |
| Public exports, signatures, ErrorCode values, CLI shape, and release collateral remain classified and synchronized. | P0 | machine-backed | `uv run pytest tests/test_public_api_snapshot.py tests/test_public_api_classification.py tests/test_public_diagnostics.py tests/test_release_contract.py -q` (`public-contract`) |
| Full, block, streaming, and async rendering preserve the tested semantic parity corpus. | P0 | machine-backed | `uv run pytest tests/test_render_mode_plans.py tests/test_render_surface_parity.py tests/test_render_block.py tests/test_render_with_blocks.py tests/test_render_stream.py tests/test_kida_async_rendering.py -q` (`runtime-suite`) |
| Sandbox blocklist, allowlist, resource caps, strict behavior, and escaping boundaries retain adversarial regression proof. | P0 | machine-backed | `uv run pytest tests/test_sandbox_fuzz.py tests/test_markup_security.py tests/test_strict_mode.py -q` (`sandbox-suite`) |
| Shared runtime operations retain synchronized GIL-disabled safety and provenance checks. | P0 | machine-backed | `PYTHON_GIL=0 uv run pytest tests/test_render_surface_parity.py tests/test_sandbox_fuzz.py tests/test_bytecode_cache_concurrency.py tests/test_lru_cache_concurrency.py tests/test_kida_stress_test.py tests/test_randomized_thread_stress.py -q --tb=short` (`safety-suite`) |
| Generated maps fail when stale, uncovered, over budget, evidence-rotted, falsely wired, or pointed at dead command paths. | P1 | machine-backed | `uv run pytest tests/stewards -q` (`steward-tools`) |
| Repository Python remains Ruff-clean without governance-specific suppression growth. | P1 | machine-backed | `make lint` (`lint`) |
| Repository Python formatting remains stable under Ruff. | P1 | machine-backed | `make format-check` (`format`) |
| Kida and Action support remain clean at the repository's default Ty severity. | P1 | machine-backed | `make ty` (`ty`) |
| Downstream-observable contracts receive consumer pilot evidence or an allowed exact no-pilot record. | P1 | manual | docs/downstream-pilot-policy.md · `## Decision Rule` |

## Stop & Ask

- A change alters public API or CLI, Environment or Template behavior, loaders, extensions, sandbox policy, worker tuning, strict defaults, or compatibility tiers.
- A change adds syntax, an AST node, a tag, a top-level filter/test/global, a render surface, a schema version, an Action behavior, a runtime dependency, a C extension, or a new config surface.
- A change touches sandbox semantics, escaping placement, safe-string protocols, trust boundaries, shared mutable state, caches, singletons, ContextVar ownership, or free-threading assumptions.
- A hot-path lexer, parser, compiler, accumulator, cache, worker, or surface-escaping change lacks benchmark evidence or a clear measurement plan.
- Tests and code disagree, a reported bug cannot be reproduced with a minimal template and context, or a public-contract decision is unresolved.
- When public behavior depends on unresolved product choices, identify only the minimum blocking decisions and stop before designing collateral, compatibility behavior, or migration policy.
- An irreversible operation, deletion, release action, external write, or coordinated downstream change is required.

## Done Criteria

- Run `make lint`, `make format-check`, and `make ty`; do not add ignores or suppressions merely to make them pass.
- Run the narrowest relevant pytest targets first and `make test` for broad or release-class changes; combined branch coverage remains at least 83 percent when the stability gate applies.
- Run `make verify-stability` for release-critical, public-contract, sandbox, render-surface, packaging, or concurrency work.
- Parser changes include malformed source and location assertions; diagnostic changes include code, structured format, location, and suggestion proof.
- Render changes compare every reached sync/async/full/block/stream and HTML/terminal/markdown/report surface, recording intentional differences.
- Hot-path changes name benchmark applicability and evidence; concurrency changes explain shared state, locks, caches, ContextVar use, Python build, and GIL status.
- User-facing behavior moves with site docs, examples, templates/scaffolds, schemas, benchmarks or an explicit no-impact reason, and a changelog fragment when required.
- Run `make docs` when published site content, structure, templates, or configuration changes, or record why the build was not applicable.
- Every accepted finding names proof and collateral plus downstream-pilot classification under `docs/downstream-pilot-policy.md`.

---

Explicit review/audit only: [.stewards/PROTOCOL.md](.stewards/PROTOCOL.md). Steward maintenance only: [.stewards/manifest.toml](.stewards/manifest.toml), then `python .stewards/verify.py --coverage`.
