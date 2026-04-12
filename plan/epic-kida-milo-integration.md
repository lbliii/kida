# Epic: Kida × Milo Integration — Prove the Stack End-to-End

**Status**: Draft
**Created**: 2026-04-12
**Target**: v0.5.0
**Estimated Effort**: 20–30h
**Dependencies**: Milo 0.2.1+ (shipped 2026-04-12), Kida v0.4.1+
**Source**: `docs/strategic-roadmap.md` (closed), Milo 0.2.1 release analysis, codebase audit

---

## Why This Matters

Kida's compiler intelligence (Phase 1) is complete. Milo 0.2.1 ships the full saga system (`Fork`, `Call`, `Delay`, `Race`, `All`, `Retry`), Elm-architecture state management (`Store`, `Reducer`), multi-screen flows (`Flow`, `>>` operator), interactive forms, and `KeyReader` input — all on `ThreadPoolExecutor`, free-threading ready. The integration surface between the two libraries has never been exercised under real concurrent load, and the showcase content that proves the stack doesn't exist yet.

1. **No concurrent saga benchmark exists** — Kida's `benchmarks/test_benchmark_concurrent.py` tests multi-threaded *rendering* but not the Milo pattern: saga dispatches action → reducer produces new state → template re-renders. This is the hot path in every Milo app and the #1 claim we need to prove ("linear scaling with cores under `PYTHON_GIL=0`").
2. **No Milo-pattern tutorial in Kida docs** — 7 tutorials exist (`site/content/docs/tutorials/`) covering Flask, Django, Starlette, Jinja2 migration, custom filters, and agent integration. Zero cover terminal rendering patterns, `LiveRenderer` usage, or `static_context` optimization — the things that make Kida different from every other template engine.
3. **`docs/milo-vision.md` says "design phase"** — Milo 0.2.1 ships `App`, `Store`, `Flow`, `form()`, `pipeline`, MCP server mode, and `milo dev` hot reload. The vision doc is dangerously stale and misleads anyone reading it.
4. **Marketplace action not published** — `action.yml`, branding, 21+ templates, and `docs/marketplace-listing.md` are all ready. The only remaining step is creating the GitHub release with "Publish to Marketplace" checked.
5. **Zero external dogfooding** — No PRs submitted to external repos. The adoption flywheel hasn't started.

### Evidence

| Layer/Source | Key Finding | Proposal Impact |
|-------------|-------------|-----------------|
| `benchmarks/test_benchmark_concurrent.py` | Tests multi-threaded `render()` with `ThreadPoolExecutor` but no saga→reducer→render cycle | FIXES — Sprint 1 adds Milo-pattern benchmarks |
| `benchmarks/test_benchmark_terminal.py:64-89` | `STATIC_CTX` dict demonstrates Milo-style static context but no saga interaction | FIXES — Sprint 1 benchmarks saga dispatch + render |
| `site/content/docs/tutorials/` (7 files) | Flask, Django, Starlette, Jinja2, filters, agent — no terminal/LiveRenderer tutorial | FIXES — Sprint 2 adds terminal rendering tutorial |
| `docs/milo-vision.md:289` | "Milo is in design phase" — false as of Milo 0.2.1 | FIXES — Sprint 2 updates vision doc |
| `docs/marketplace-listing.md:13-21` | All prerequisites met, listing steps documented | FIXES — Sprint 3 publishes to Marketplace |
| `examples/terminal_*` (11 dirs) | Rich terminal examples but none use Milo's `App`/`Store`/saga pattern | FIXES — Sprint 1 adds a Milo-integrated example |

### Invariants

These must remain true throughout or we stop and reassess:

1. **Kida test suite stays green**: No changes to Kida's rendering/compilation break existing tests. `uv run pytest` passes at every sprint boundary.
2. **Milo stays a dev dependency only**: Milo is not added to Kida's runtime dependencies. Benchmark and example code imports Milo but Kida itself does not.
3. **Benchmarks are reproducible**: Every benchmark added can run on both Darwin and Linux CI with `PYTHON_GIL=0` and produce stable results (< 10% variance across 3 runs).

---

## Target Architecture

**Before** (current):
```
Kida benchmarks  →  test concurrent rendering (no saga pattern)
Kida tutorials   →  web frameworks + migration (no terminal/LiveRenderer)
milo-vision.md   →  "design phase" (stale)
Marketplace      →  action.yml ready, not published
External repos   →  0 using kida-render
```

**After**:
```
Kida benchmarks  →  saga→reducer→render cycle under PYTHON_GIL=0 (1/2/4/8 workers)
Kida tutorials   →  terminal rendering + static_context optimization tutorial
milo-vision.md   →  reflects Milo 0.2.1 capabilities accurately
Marketplace      →  published and discoverable
External repos   →  3+ PRs submitted with kida-render
```

---

## Sprint Structure

| Sprint | Focus | Effort | Risk | Ships Independently? |
|--------|-------|--------|------|---------------------|
| 0 | Design: benchmark protocol + tutorial outline ✅ | 3–4h | Low | Yes (RFC only) |
| 1 | Concurrent saga benchmark + Milo example ✅ | 6–8h | Medium | Yes |
| 2 | Terminal tutorial + update stale docs ✅ | 5–7h | Low | Yes |
| 3 | Marketplace publish + external dogfooding | 6–10h | Medium | Yes |

---

## Sprint 0: Design & Validate ✅

**Goal**: Define the benchmark protocol and tutorial structure before writing code.

### Task 0.1 — Benchmark Protocol Design ✅

Delivered: `plan/rfc-saga-benchmarks.md`
- Frozen `DashboardState`/`Service` dataclasses
- Saga pattern: `Fork` 5 concurrent `Call` effects with 10ms simulated fetch via `Delay`
- Three-tier measurement: render-only / dispatch-only / full-cycle
- Worker scaling: 1/2/4/8 via `threading.Barrier` + `ThreadPoolExecutor`
- Three optimization tiers: baseline / static_context / static_context + inlining

### Task 0.2 — Tutorial Outline ✅

Delivered: `plan/rfc-terminal-tutorial-outline.md`
- 8 sections, ~2,650 words, 12 code examples
- Progression: basic render → colors → components → LiveRenderer → static_context → streaming → complete example
- Placement: `site/content/docs/tutorials/terminal-rendering.md` (weight 25)
- All conventions documented (frontmatter, callouts, code block language tags)

### Task 0.3 — Milo Vision Doc Assessment ✅

Delivered: `plan/rfc-milo-vision-diff.md`
- 13 accurate sections (keep), 3 wrong/stale (rewrite), 4 incomplete (expand), 17 missing features
- Module table gap: doc shows 6 modules, 0.2.1 has 40+ — proposed 23-row replacement table
- Recommendation: full rewrite, not patch (document structure assumes "three things" but 0.2.1 has 10+)
- Acceptance criteria defined for Sprint 2 rewrite

---

## Sprint 1: Concurrent Saga Benchmark + Milo Example ✅

**Goal**: Prove that Kida rendering scales linearly with cores when driven by Milo's saga system under `PYTHON_GIL=0`.

### Task 1.1 — Saga Benchmark ✅

Delivered: `benchmarks/test_benchmark_saga.py` — 10 tests across 4 benchmark groups:
- `saga:render-only` — isolates Kida rendering (no saga overhead)
- `saga:full-cycle` — single-threaded saga→reducer→render
- `saga:scaling` — 1/2/4/8 workers with `threading.Barrier` + `ThreadPoolExecutor`
- `saga:optimization` — baseline vs static_context vs inlining

**Scaling results (free-threaded Python 3.14t):**
- 1 worker: 79ms baseline
- 2 workers: 41ms (1.9x)
- 4 workers: 23ms (3.5x)
- 8 workers: 15ms (5.3x)

Near-linear scaling confirmed. Added `milo-cli>=0.2.1` to dev dependencies in `pyproject.toml`.

### Task 1.2 — Milo-Integrated Terminal Example ✅

Delivered: `examples/terminal_saga_dashboard/`
- `run.py` — `Store` + `LiveRenderer` + saga fetches with `All`/`Call`/`Put`
- `templates/dashboard.txt` — terminal template with `static_context` optimization
- `README.md` — usage instructions and architecture explanation
- Verified: `python examples/terminal_saga_dashboard/run.py` renders live dashboard

---

## Sprint 2: Terminal Tutorial + Stale Doc Cleanup ✅

**Goal**: Publish the terminal rendering tutorial and update stale Milo documentation.

### Task 2.1 — Terminal Rendering Tutorial ✅

Delivered: `site/content/docs/tutorials/terminal-rendering.md`
- 8 sections: first render, colors/degradation, layout/components, LiveRenderer, static_context, streaming, complete example, next steps
- ~2,800 words, 12 code examples
- Added tutorial card to `site/content/docs/tutorials/_index.md` (weight 25, icon terminal)

### Task 2.2 — Update Milo Vision Doc ✅

Delivered: Full rewrite of `docs/milo-vision.md`
- Removed all "design phase" references (verified: `rg 'design phase'` returns 0 hits)
- Expanded module table from 6 to 23 modules covering saga, pipeline, MCP, gateway, flow, plugins, middleware, etc.
- Added MCP server mode (`--mcp`), AI discovery (`--llms-txt`), gateway documentation
- Expanded architecture diagram from 3 boxes to 9 (App/Flow/Screen, Store/Sagas/Reducers, Pipeline, Input, Form, MCP, Plugins, Middleware, Dev)
- Added saga effect table (16 effects), composable reducer decorators, input handling, pipeline orchestration
- Updated status section to reflect v0.2.1 shipped capabilities
- Added complete code examples for CLI definition, forms, saga deploy pipeline, MCP server, multi-screen flows

---

## Sprint 3: Marketplace + External Dogfooding

**Goal**: Get kida-render into hands. Publish the action to Marketplace and submit PRs to external repos.

### Task 3.1 — Publish GitHub Action to Marketplace

Follow `docs/marketplace-listing.md`:
- Create GitHub release with "Publish this action to the GitHub Marketplace" checked
- Category: Code quality
- Verify listing is searchable

**Acceptance**: Action appears at `github.com/marketplace/actions/kida-report` (or equivalent URL).

### Task 3.2 — Identify External Dogfooding Targets

Find 3–5 open-source Python repos that:
- Use GitHub Actions CI
- Run pytest with JUnit XML or coverage output
- Currently use generic CI reporting (or none)
- Have responsive maintainers (recent activity, open to PRs)

**Acceptance**: List of 3–5 repos with rationale, current CI setup, and proposed kida-render integration.

### Task 3.3 — Submit External PRs

For each target repo:
- Fork, add kida-render step to CI workflow
- Include screenshot of rendered PR comment
- Write clear PR description explaining what kida-render does

**Files**: External PRs (links tracked in this epic)
**Acceptance**: 3+ PRs submitted. Track URLs below as they're created.

**PR Tracker**:
- [ ] Repo 1: (TBD)
- [ ] Repo 2: (TBD)
- [ ] Repo 3: (TBD)

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Milo 0.2.1 saga API changes before we benchmark | Low | Medium | Pin `milo-cli==0.2.1` in benchmark requirements. Sprint 0 validates API stability. |
| Saga benchmark shows non-linear scaling | Medium | High | Sprint 0 designs isolation methodology. If GIL contention found, profile with `py-spy` and report findings — the data is still valuable. |
| External repos reject kida-render PRs | Medium | Low | Submit to 5 repos expecting 3 accepts. Focus on repos with no existing CI reporting (lower bar). |
| Terminal tutorial code examples break on different terminal emulators | Low | Medium | Test on iTerm2, Terminal.app, and CI (headless). Use `NO_COLOR` mode as baseline. |

---

## Success Metrics

| Metric | Current | After Sprint 1 | After Sprint 3 |
|--------|---------|----------------|----------------|
| Saga benchmarks | 0 | 1 suite, 4 worker configs | 1 suite with CI results |
| Terminal tutorials | 0 | 0 | 1 published |
| Milo vision doc accuracy | ~30% (stale) | ~30% | 100% (updated) |
| Marketplace listing | Not published | Not published | Published |
| External repos using kida-render | 0 | 0 | 3+ PRs submitted |

---

## Relationship to Existing Work

- **`docs/strategic-roadmap.md`** — supersedes remaining Phase 2 (items 2.2, 2.3, 2.4) and Phase 3 (items 3.1 partial, 3.3) items. Roadmap now closed.
- **`plan/epic-partial-eval-enhancement.md`** — complete. Phase 1 compiler gains are the foundation for Sprint 1's `static_context` benchmarks.
- **`plan/epic-tstring-dogfooding.md`** — complete. No dependency.
- **`docs/terminal-api-contract.md`** — Sprint 1 benchmarks exercise the stable API documented there.
- **Milo 0.2.1** (external) — Sprint 1 depends on `milo.state.Store`, `milo.app.App`, and saga primitives (`Fork`, `Call`, `Delay`, `Put`).

---

## Changelog

| Date | Change | Reason |
|------|--------|--------|
| 2026-04-12 | Initial draft. | Roadmap closed; Milo 0.2.1 unblocked Phase 2/3 items. |
| 2026-04-12 | Sprint 0 complete. Delivered 3 RFCs: `rfc-saga-benchmarks.md`, `rfc-terminal-tutorial-outline.md`, `rfc-milo-vision-diff.md`. | All design tasks validated — ready for Sprint 1 implementation. |
| 2026-04-12 | Sprint 1 complete. Saga benchmarks show 5.3x scaling at 8 workers. Example dashboard works end-to-end. `milo-cli>=0.2.1` added to dev deps. | Near-linear scaling proved under free-threading. |
| 2026-04-12 | Sprint 2 complete. Terminal rendering tutorial (8 sections, 12 examples) and full milo-vision.md rewrite (23-module table, saga/MCP/flow docs). Tutorial card added to index. | Documentation now matches Milo 0.2.1 reality. |
