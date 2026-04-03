# Kida Strategic Roadmap: Unlocking the Potential

## Context

Kida is architecturally excellent — AST-native compilation, immutable-everything thread safety, multi-surface rendering, modern operators. The vision (Bengal ecosystem, Milo, CI reporting) is ambitious and coherent. But the genius is locked behind three barriers: (1) the compiler doesn't yet exploit what AST-native makes possible, (2) the most differentiated feature (terminal rendering) needs its application layer (Milo) hardened, and (3) the product that's ready to ship (CI reports) has no distribution. This plan sequences work to build compounding leverage across all three.

---

## Phase 1: Compiler Intelligence (Weeks 1-4)

**Goal**: Make kida categorically faster, not incrementally faster. Move the benchmark story from "1.5-2.5x Jinja2" to "5-10x on real templates with static context."

This work is multiplicative — every downstream product (Milo, CI reports, web adapters) gets faster for free.

### 1.1 Constant Folding Through Pure Filters

The partial evaluator (`src/kida/compiler/partial_eval.py`) currently stops at `Filter` node boundaries. A `{{ site.title | upper }}` where `site.title` is static still generates a runtime filter call. Since the purity analyzer already classifies 67 filters as pure, the evaluator can execute them at compile time and replace the entire chain with a `Const` node.

**Deliverable**: Extend `PartialEvaluator` to evaluate `Filter` nodes when the input expression, the filter, and all arguments are resolvable constants.

### 1.2 Dead Branch Elimination with Static Context

When `static_context` provides enough info, entire `{% if %}` branches can be removed at compile time. The partial evaluator can already resolve conditions — it just needs to prune the dead branch from the AST entirely.

**Deliverable**: When an `If` node's test resolves to a constant, replace the `If` with its live branch's body (or nothing). Cascade through `elif` chains.

### 1.3 Component Inlining

Small `{% def %}` components called with all-constant arguments can be inlined at compile time: expand the body with arguments substituted. Eliminates function call overhead and enables further coalescing.

**Deliverable**: Inline `CallBlock` → `Def` when body is small (< 20 AST nodes), all arguments are `Const`, and no `{% slot %}` or `{% yield %}`. Gate behind `Environment(inline_components=True)`.

### 1.4 Free-Threading Benchmarks as Proof

The single-threaded benchmarks undersell kida. The real story is: "Nx faster single-threaded, and it scales linearly with cores under `PYTHON_GIL=0`." No other template engine can make that claim.

**Deliverable**:
- Benchmark suite with/without `static_context` showing optimization delta
- Prominent concurrent benchmark: 1/2/4/8 workers under `PYTHON_GIL=0`
- `kida render --explain` flag showing applied optimizations
- Headline numbers in README

---

## Phase 2: Advance Milo + Tighten the Kida Integration (Weeks 5-10)

**Goal**: Milo v0.1.1 is shipped. This phase hardens the kida-milo integration, proves the free-threading story end-to-end, and builds the showcase apps that make people want both libraries.

### 2.1 Stabilize Kida Terminal API Contract

Document what Milo can rely on: `terminal_env()`, `LiveRenderer`, component filters, color depth detection. Explicit stability guarantee.

### 2.2 Free-Threading Showcase: Concurrent Sagas

Milo's saga system (`Fork`, `Call`, `Delay`) under `PYTHON_GIL=0` — HTTP fetches, file I/O, and rendering on real threads with zero locks. Benchmark saga concurrency GIL=0 vs GIL-enabled. Example: deploy pipeline fetching 5 services concurrently.

### 2.3 Showcase Tutorials

Ship the three tutorials in development: dashboard (concurrent fetches), file browser (keyboard nav), test runner (watch mode). Each demonstrates a different kida + milo strength.

### 2.4 Kida Compiler Optimizations for Terminal Mode

Validate Phase 1 compiler gains against Milo-style terminal templates. Profile `LiveRenderer.update()` with `static_context`. Ensure f-string coalescing works with terminal filter chains.

---

## Phase 3: Distribution and Adoption (Weeks 8-14, overlaps Phase 2)

**Goal**: Get kida and kida-render into hands. Reposition messaging. Create the adoption flywheel.

### 3.1 Decouple Messaging from b-stack

Rewrite README to lead with kida's standalone value. Move ecosystem section to bottom. Lead with: "A Python template engine that compiles to AST, renders anywhere, and runs on free-threaded Python."

### 3.2 GitHub Action Marketplace Listing

Register on Marketplace with screenshots, copy-paste YAML, and search-optimized description.

### 3.3 Dogfood Externally

Add kida-render to 3-5 open source repos. Blog post: "Replace 5 CI actions with one template."

### 3.4 "Kida vs Jinja2" Comparison

Standalone comparison page: side-by-side syntax, feature matrix, benchmark results. Honest about differences, clear about advantages.

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
| Phase 1 | Benchmark with static_context | 5x+ faster than Jinja2 on large templates |
| Phase 1 | Optimization explainer | `kida render --explain` |
| Phase 2 | Milo tutorials | Dashboard, file browser, test runner published |
| Phase 2 | Free-threading proof | Concurrent saga speedup under GIL=0 |
| Phase 3 | Marketplace listing | Listed and discoverable |
| Phase 3 | External dogfooding | 5+ repos using kida-render |
| Phase 3 | README rewrite | Standalone value proposition |
