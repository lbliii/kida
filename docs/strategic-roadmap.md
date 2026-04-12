# Kida Strategic Roadmap: Unlocking the Potential

**Status**: CLOSED — superseded by `plan/epic-kida-milo-integration.md`

## Context

Kida is architecturally excellent — AST-native compilation, immutable-everything thread safety, multi-surface rendering, modern operators. The vision (Bengal ecosystem, Milo, CI reporting) is ambitious and coherent. But the genius is locked behind three barriers: (1) the compiler doesn't yet exploit what AST-native makes possible, (2) the most differentiated feature (terminal rendering) needs its application layer (Milo) hardened, and (3) the product that's ready to ship (CI reports) has no distribution. This plan sequences work to build compounding leverage across all three.

---

## Phase 1: Compiler Intelligence ✅ COMPLETE

**Goal**: Make kida categorically faster, not incrementally faster. Move the benchmark story from "1.5-2.5x Jinja2" to "5-10x on real templates with static context."

This work is multiplicative — every downstream product (Milo, CI reports, web adapters) gets faster for free.

### 1.1 Constant Folding Through Pure Filters ✅

Implemented in `partial_eval.py` (lines 621–711, 1888–1906). The `_try_eval_filter()` method checks filter purity, resolves value/args/kwargs at compile time, and replaces the chain with a `Const` node. 67 pure filters available.

### 1.2 Dead Branch Elimination with Static Context ✅

Implemented in `partial_eval.py` (lines 1179–1254). `_transform_if()` evaluates the test expression; when constant, it selects the winning branch and inlines its body, or removes the `If` entirely when all branches are false. Also handles `elif` cascades (lines 270–316).

### 1.3 Component Inlining ✅

Implemented in `partial_eval.py` (lines 1637–1745). `_try_inline_call()` inlines `CallBlock` → `Def` when body < 20 AST nodes, all args are constant, and no slots/yields. Gated behind `Environment(inline_components=True)`.

### 1.4 Free-Threading Benchmarks as Proof ✅

All deliverables shipped:
- `benchmarks/test_benchmark_concurrent.py` — multi-worker rendering under `PYTHON_GIL=0`
- `kida render --explain` flag implemented in `cli.py` (lines 330–395, 552–622)
- `_Py_mod_gil = 0` declared in `__init__.py` (PEP 703)
- Headline numbers in README

---

## Phase 2: Advance Milo + Tighten the Kida Integration — PARTIAL

**Goal**: Milo v0.1.1 is shipped. This phase hardens the kida-milo integration, proves the free-threading story end-to-end, and builds the showcase apps that make people want both libraries.

### 2.1 Stabilize Kida Terminal API Contract ✅

Formal API stability doc published at `docs/terminal-api-contract.md` (v0.3.0+). Documents `terminal_env()`, `LiveRenderer`, `Spinner`, component filters, color depth detection with thread-safety guarantees.

### 2.2 Free-Threading Showcase: Concurrent Sagas — UNBLOCKED (Milo 0.2.1 shipped)

Milo 0.2.1 (released 2026-04-12) ships full saga system: `Fork`, `Call`, `Delay`, `Put`, `Select`, `Race`, `All`, `Retry`, `Take`/`TakeEvery`/`TakeLatest`, `Timeout`, `TryCall`, `Batch`, `Sequence`, `Debounce`. Runs on `ThreadPoolExecutor`. Kida-side work can now proceed.

### 2.3 Showcase Tutorials — PARTIAL

Kida-side examples exist (`examples/terminal_dashboard/`, `terminal_deploy/`, `terminal_monitor/`). Framework integration tutorials published (Flask, Django, Starlette). Milo 0.2.1 now ships `App`, `Store`, `Flow`, `form()`, `KeyReader` — file browser and test runner tutorials are unblocked.

### 2.4 Kida Compiler Optimizations for Terminal Mode — PARTIAL

`benchmarks/test_benchmark_terminal.py` validates Phase 1 optimizations against terminal templates. `--explain` flag works for all modes. No terminal-specific compiler paths needed — general optimizations apply uniformly.

---

## Phase 3: Distribution and Adoption — PARTIAL

**Goal**: Get kida and kida-render into hands. Reposition messaging. Create the adoption flywheel.

### 3.1 Decouple Messaging from b-stack — PARTIAL

README leads with standalone value: "A template engine that compiles to Python AST, renders to HTML/terminal/markdown, and scales across cores on free-threaded Python." Bengal ecosystem positioned at bottom. Could be further tightened.

### 3.2 GitHub Action Marketplace Listing ✅

`action.yml` complete with branding, 21+ built-in templates, PR comment deduplication. Self-dogfooded in `.github/workflows/tests.yml`. Marketplace listing guide at `docs/marketplace-listing.md`.

### 3.3 Dogfood Externally — NOT STARTED

No external adoption tracked yet. Requires identifying 3-5 target repos and submitting PRs.

### 3.4 "Kida vs Jinja2" Comparison ✅

Published at `site/content/docs/about/comparison.md`. Side-by-side syntax, feature matrix, honest limitations section. Migration guide at `site/content/docs/get-started/coming-from-jinja2.md`.

---

## What NOT to Do

- **Backport to Python 3.12/3.13** — Non-negotiable. 3.14t is the foundation. Every design decision exists because of free-threading.
- **Paid tier / SaaS** — Premature. Need 1000+ repos on the free action first.
- **C extension for escaping** — Performance comes from compiler intelligence. Pure Python is a selling point.
- **New rendering surfaces** — HTML, terminal, markdown are enough.
- **Framework adapter expansion** — Flask, Starlette, Django cover 95%.
- **Template gallery site** — Build when there are community templates to host.

---

## Success Criteria

| Phase | Metric | Target |
|-------|--------|--------|
| Phase 1 | Benchmark with static_context | 5x+ faster than Jinja2 on large templates | ✅ Shipped |
| Phase 1 | Optimization explainer | `kida render --explain` | ✅ Shipped |
| Phase 2 | Milo tutorials | Dashboard, file browser, test runner published | Partial — Kida examples done, Milo items now unblocked (0.2.1) |
| Phase 2 | Free-threading proof | Concurrent saga speedup under GIL=0 | Unblocked — Milo 0.2.1 ships sagas |
| Phase 3 | Marketplace listing | Listed and discoverable | ✅ Ready to publish |
| Phase 3 | External dogfooding | 5+ repos using kida-render | Not started |
| Phase 3 | README rewrite | Standalone value proposition | ✅ Done |

---

## Changelog

| Date | Change | Reason |
|------|--------|--------|
| 2026-04-12 | Marked Phase 1 complete (all 4 items shipped). Updated Phase 2/3 with per-item status. Added status column to success criteria. | Roadmap was stale — Phase 1 delivered across epics (partial-eval-enhancement, partial-eval-phase-2, tstring-dogfooding) but roadmap not updated. |
| 2026-04-12 | Closed roadmap. Milo 0.2.1 ships full saga system + App/Store/Flow/form — Phase 2 items 2.2 and 2.3 are unblocked. Remaining work moved to `plan/epic-kida-milo-integration.md`. | All Phase 1 complete, Phase 2/3 remaining items better tracked as a focused epic. |
