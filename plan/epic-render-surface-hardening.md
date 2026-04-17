# Epic: Render Surface Hardening — Parity Tests, Scaffold, Sandbox Fuzz

**Status**: Draft
**Created**: 2026-04-17
**Priority**: P1 (quality — prevents a recurring class of async/sync drift bugs and strengthens the sandbox story for the 1.0 security review)
**Affects**: `src/kida/template/core.py`, `src/kida/sandbox.py`, `tests/`

---

## Problem Statement

Kida exposes six render surfaces that must behave consistently:

| Method                        | Path       | Preamble setup                               |
| ----------------------------- | ---------- | -------------------------------------------- |
| `render`                      | full       | inline (compiled top-level body)             |
| `render_stream`               | full       | inline                                       |
| `render_stream_async`         | full       | inline                                       |
| `render_block`                | fragment   | **explicit** `_run_globals_setup_chain`      |
| `render_with_blocks`          | fragment   | **explicit** `_run_globals_setup_chain`      |
| `render_block_stream_async`   | fragment   | **missing** until `#101` — silent drift      |

Until 2026-04-17, `render_block_stream_async` never called `_run_globals_setup_chain`. Every template that used a top-level `{% region %}`, `{% def %}`, `{% let %}`, or `{% from … import … %}` and was rendered via the async block stream raised `KeyError` on the region callable — a contract break that was invisible to 3883 unit tests.

The bug stayed green because each render method is tested against its own curated templates. No test drives *the same template* through every surface and asserts equivalent output. When a new method (async stream + async block stream) was added for `rfc-async-rendering`, there was no structural forcing function to ensure it honored the same preamble contract as its sync siblings.

### Evidence

| Finding                                                                 | Consequence                                                                                                  | Does this plan fix it?                |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------- |
| Four fragment-render methods each re-implement context + setup by hand  | Any new fragment method must remember to call `_run_globals_setup_chain`; forgetting is a silent runtime bug | Yes (Sprint 2 scaffold extraction)    |
| No test drives the same template through `render` / `_stream` / `_async`| Async-path regressions invisible until a consumer hits the exact combination                                 | Yes (Sprint 1 parity matrix)          |
| Sandbox test suite (~320 lines) covers representative escape vectors    | Novel dunder / method chains are not exercised; confidence is "worked examples" not "generative"             | Yes (Sprint 3 hypothesis fuzz)        |
| `SECURITY.md` commits to sandbox behavior; property evidence thin       | Enterprise reviewers will ask "how do you know"; current answer is "we wrote tests we thought of"            | Yes (Sprint 3 supplies the evidence)  |
| `hypothesis` already a dev dep; used in `test_partial_eval`, not core   | The tool is on the shelf; the sandbox and render-surface invariants never get its benefit                    | Yes (Sprints 1 and 3 put it to work)  |

---

## Invariants

1. **Output parity across render surfaces** — for any sync-compatible trusted template `T`, block `b`, and context `C`:
   `render_block(b, C) == "".join(render_block_stream(b, C)) == "".join(await render_block_stream_async(b, C))`. Verified per release via a template corpus covering: top-level preamble (let/def/region/import), inheritance chains, regions inside blocks, fragment blocks, and the `{% globals %}` block.

2. **Structural preamble contract** — every fragment-render method must route through a single code path that binds `declared_definitions` on the `RenderContext` and invokes `_run_globals_setup_chain` on the chain cache. A lint/test gate asserts no fragment-render method bypasses the helper.

3. **Sandbox invariants hold under generative input** — a hypothesis-generated expression corpus produces no escapes of the documented `_BLOCKED_ATTRS` / `_UNSAFE_TYPES` sets. Any new attribute name or type reachable via attribute-chain → call graph is either on the allowlist or raises `SecurityError`.

---

## Sprint Overview

| Sprint | Name                               | Duration | Ships independently? |
| ------ | ---------------------------------- | -------- | -------------------- |
| 0      | Design (corpus, scaffold, fuzz)    | 1 day    | n/a — paper only     |
| 1      | Render-surface parity matrix       | 2 days   | **Yes**              |
| 2      | Fragment-render scaffold           | 2 days   | **Yes**              |
| 3      | Hypothesis-driven sandbox fuzz     | 2 days   | **Yes**              |

Each of Sprints 1–3 delivers value if the others are never started.

---

## Sprint 0 — Design on Paper

Solve the three highest-leverage problems before any code lands.

### Tasks

1. **Corpus selection for parity matrix.** Enumerate the template permutations that must round-trip identically across render surfaces. Candidate dimensions: top-level preamble (none / let / def / region / import / all), inheritance depth (0 / 1 / 2), block type (`block` / `fragment` / `region`), nested blocks, `{% globals %}` present. Pick a cartesian subset that covers the known risky combinations without ballooning wall time. Target: ≤ 40 templates, ≤ 2 s total runtime.

2. **Scaffold signature for fragment renders.** Decide whether to (a) extract a new `_fragment_scaffold` context manager mirroring `_render_scaffold`, or (b) extend `_render_scaffold` with a `fragment: bool` flag. Trade-off: (a) is clearer at call sites, (b) reuses the error-enhancement path. Write 15 lines of pseudo-code for each option, pick one, record in the decision log.

3. **Sandbox fuzz strategy.** Choose the hypothesis strategy shape: generate attribute chains of length 1–4 drawn from a pool (safe names + Python stdlib dunders + blocklist names) and assert either success-with-allowed-value or `SecurityError`. Decide whether to fuzz against the default `Environment` baseline too, to assert the *difference* between default and sandboxed behavior is non-empty. Record pool contents and chain-length distribution.

### Acceptance

- One-page design note at `plan/design-render-surface-hardening.md` covering the three decisions above.
- Reviewed by whoever ships Sprint 1 before Sprint 1 starts.

---

## Sprint 1 — Render-Surface Parity Matrix

Ship a table-driven test file that drives every surface against a shared corpus.

### Tasks

1. Create `tests/test_render_surface_parity.py`. One `pytest.mark.parametrize` over the Sprint-0 corpus, one test per `(template, block_name, context)` tuple.
2. For each tuple, render through `render` (if no block required), `render_block`, `render_stream`, `render_block_stream`, `render_stream_async`, `render_block_stream_async` — assert `"".join(chunks) == full_render` pairwise.
3. Add a small hypothesis-based property test (`@given(st.from_regex(...))`) that generates trivial templates with one `{% let %}` + `{% block %}` and confirms `render_block` ≡ joined `render_block_stream_async`.
4. Mark the parity file with `@pytest.mark.asyncio` where needed; no new deps.

### Acceptance

- `rg "def render_" src/kida/template/core.py | wc -l` equals the number of surfaces exercised in `tests/test_render_surface_parity.py` (asserted in a meta-test).
- Full suite passes; parity tests run in < 3 s.
- Running `git revert <the render_block_stream_async fix commit>` must turn the new parity tests red — documented in a commented regression note at the top of the file.

---

## Sprint 2 — Fragment-Render Scaffold

Extract the shared fragment-render setup so forgetting it becomes a compile error, not a runtime `KeyError`.

### Tasks

1. Introduce `_fragment_scaffold` (the shape chosen in Sprint 0) that encapsulates: build context, open `render_context` / `async_render_context`, set `declared_definitions`, run `_run_globals_setup_chain`, yield `(ctx, render_ctx, effective)`.
2. Migrate `render_block`, `render_with_blocks`, `render_block_stream`, `render_block_stream_async` to use it. Delete the open-coded duplication.
3. Add a gate: a meta-test that imports `kida.template.core`, walks `Template`'s method dict, and asserts every method matching `render_.*block.*|render_with_blocks` has `_fragment_scaffold` in its source (via `inspect.getsource`). New fragment methods that skip the helper fail CI.
4. Run `uv run pytest -q` and confirm no behavior change — full suite green.

### Acceptance

- `rg "_run_globals_setup_chain" src/kida/template/core.py` returns exactly one call site (inside `_fragment_scaffold`).
- `uv run ty check src/` passes.
- Benchmarks for `render_block` within ±2 % of pre-Sprint baseline (spot-check one representative benchmark from `benchmarks/`).

---

## Sprint 3 — Hypothesis-Driven Sandbox Fuzz

Turn `SECURITY.md`'s sandbox claims into generative evidence.

### Tasks

1. Create `tests/test_sandbox_fuzz.py`. Hypothesis strategy: attribute chains (`obj.a.b.c`) and method calls drawn from a curated name pool (safe names + `_BLOCKED_ATTRS` + Python stdlib dunders + random valid identifiers).
2. Property 1 — *blocklist is honored*: for any chain whose first blocked-attribute hit is at position `i`, rendering must raise `SecurityError` before reaching position `i+1`. Assert on the exception, not output.
3. Property 2 — *allowlist mode is closed*: with `SandboxPolicy(allowed_attributes=frozenset({"name"}))`, any attribute access outside that set raises; including safe collection methods when the policy intentionally omits them.
4. Property 3 — *default vs sandbox differ*: a small corpus of expressions that succeed under default `Environment` must fail under `SandboxedEnvironment`. Guards against accidental regressions that weaken the sandbox.
5. Property 4 — *max_range / max_output_size enforced*: hypothesis-generated loop counts above the limit raise `SecurityError`; below the limit render normally.
6. Cap hypothesis examples per property at 200 to keep CI wall-time under 5 s.

### Acceptance

- New file runs in < 5 s on CI.
- Hypothesis examples count reflected in `pyproject.toml` if tuned; otherwise defaults used.
- Add a `SECURITY.md` footnote: "Sandbox invariants verified by property tests in `tests/test_sandbox_fuzz.py`."

---

## Risk Register

| Risk                                                                    | Impact | Likelihood | Mitigation                                                                                                           |
| ----------------------------------------------------------------------- | ------ | ---------- | -------------------------------------------------------------------------------------------------------------------- |
| Parity corpus explodes wall time                                        | Medium | Medium     | Sprint 0 caps the corpus size; parity file time-budgeted < 3 s; run as part of `uv run pytest tests/` not benchmarks |
| Scaffold refactor breaks a subtle code path (error enhancement, RenderCapture) | High | Medium | Sprint 2 pre-condition: green parity tests from Sprint 1. Migrate one method, run full suite, then the next.         |
| Hypothesis finds a genuine sandbox escape                               | High   | Low        | That is the point. Handle as a security fix: private advisory per `SECURITY.md`, not a public issue                  |
| Hypothesis is flaky in CI (seeded timeouts, `deadline` issues)          | Medium | Medium     | Use `@settings(deadline=None, max_examples=200)`; explicit seed via `@seed(0)` for reproducibility                   |
| Scaffold gate meta-test (source inspection) gives false positives       | Low    | Low        | If `inspect.getsource` proves brittle, replace with an AST walk of the method's body; keep the *intent* of the gate  |

---

## Success Metrics

| Metric                                                              | Current | After Sprint 1   | After Sprint 2   | After Sprint 3   |
| ------------------------------------------------------------------- | ------- | ---------------- | ---------------- | ---------------- |
| Fragment-render methods with explicit `_run_globals_setup_chain`    | 4 / 4   | 4 / 4            | 1 (via scaffold) | 1                |
| Render-surface parity tests                                         | 0       | ≥ 40 permutations| ≥ 40             | ≥ 40             |
| Sandbox property tests (hypothesis)                                 | 0       | 0                | 0                | ≥ 4              |
| Total new test runtime                                              | n/a     | < 3 s            | < 3 s            | < 8 s            |
| `SECURITY.md` sandbox claims backed by property tests               | No      | No               | No               | **Yes**          |

---

## Deferred / Out of Scope

- **Mutation testing** (e.g. `mutmut`) — high-signal but large wall-time; revisit post-1.0 if fuzz coverage is still insufficient.
- **Differential testing against Jinja2** — useful for migration confidence but not an invariant of Kida itself; separate RFC if pursued.
- **Free-threaded concurrency parity tests** — `render()` is documented thread-safe; proving it under 3.14t load is a separate benchmark concern, tracked elsewhere.
