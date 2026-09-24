# Critical-Contract Assurance Inventory v1

Status: active evidence baseline; no new gate or tool approved

Tracking: [GitHub issue #250](https://github.com/lbliii/kida/issues/250), child of
[critical-path assurance epic #192](https://github.com/lbliii/kida/issues/192)

Evidence date: 2026-07-09

Measured revision: `f003e3bf1dadc808be6582c684c13f188c367f53`

## Purpose and interpretation

This inventory maps every #192 checklist row to executable evidence and the
remaining proof gap. Coverage identifies unexecuted branches; it does not prove
that assertions reject an incorrect optimization, escape, sandbox decision, or
cache transition. A row is therefore never closed from a percentage or snapshot
alone.

The measured checkout included concurrent documentation, benchmark, example,
and test work in the shared working tree, but no modified production file under
`src/kida/`. This is a current-tree development baseline, not a committed Linux
release baseline. Re-run it after those slices merge before ratcheting any
number.

## Measurement protocol

Environment:

- macOS 26.5.1, arm64;
- CPython 3.14.2 free-threading build;
- GIL disabled (`sys._is_gil_enabled() is False`);
- coverage.py 7.13.5 with branch measurement enabled.

Command:

```bash
.venv/bin/python -m pytest -q --tb=short \
  --cov=kida --cov-branch \
  --cov-report=json:/tmp/kida-250-coverage.json \
  --cov-report=term --timeout=300
```

Result: 4,663 passed, 6 skipped, 31 warnings in 161.71 seconds. There was no
`PytestUnraisableExceptionWarning`; the async warning recorded by the 2026-01
coverage RFC is no longer present.

| Metric | Current result | Meaning |
|---|---:|---|
| Statement coverage | 14,810 / 16,438 = 90.1% | Above 90%, but not the epic's branch target. |
| Branch coverage | 5,081 / 6,336 = 80.2% | The decisive gap for #192's first row. |
| coverage.py combined result | 87.34% | What `--cov-fail-under` evaluates with branch measurement enabled. |
| `pyproject.toml` default floor | 80% | Tool default, not the stability target. |
| `make test-cov` / `make verify-stability` floor | 83% | Active local stability gate. |
| CI coverage report | non-blocking | The report step has `continue-on-error: true` and no 90% threshold. |

The historical RFC's “Implemented” and ≥90% language is therefore not an
accurate statement of the current branch-coverage contract. The authoritative
gate remains the documented 83% local stability floor. Raising it or making the
CI report blocking requires separate approval.

## Current critical-domain branch data

Groups aggregate only the named source files. They make the numerator explicit
rather than averaging percentages.

| Contract | Source scope | Lines | Branches | Owner | Consequence of a wrong branch |
|---|---|---:|---:|---|---|
| Escaping | `utils/html.py`, `utils/markdown_escape.py`, `utils/terminal_escape.py`, `filters/_html_security.py` | 325/366 (88.8%) | 94/112 (83.9%) | Utility + render surfaces | Unsafe or corrupted output across HTML, Markdown, terminal, and reports. |
| Sandbox policy | `sandbox.py` | 101/154 (65.6%) | 24/52 (46.2%) | Runtime/security | Policy allow/deny, callable, import, and optional-access paths may drift without regression proof. |
| Template resolution | `environment/loaders.py`, `utils/template_keys.py` | 160/170 (94.1%) | 48/62 (77.4%) | Environment + utility | Wrong template, traversal escape, or misleading resolution diagnostics. |
| Cache contracts | `bytecode_cache.py`, `utils/lru_cache.py`, `template/cached_blocks.py` | 382/440 (86.8%) | 103/124 (83.1%) | Runtime + utility | Stale code, incomplete publication, wrong invalidation, or incorrect eviction. |
| Component validation | `analysis/analyzer.py` | 314/343 (91.5%) | 165/202 (81.7%) | Static analysis | Known bad component calls may escape check time or good calls may be rejected. |
| Diagnostic selection/rendering | `diagnostics.py`, `_diagnostic_adapters.py`, `_diagnostic_renderers.py` | 395/413 (95.6%) | 133/160 (83.1%) | Static analysis + runtime | Wrong code, location, severity, suggestion, or machine representation. |
| Render helpers | `template/render_helpers.py` | 231/276 (83.7%) | 58/100 (58.0%) | Template runtime | Include/extends/import/cache behavior may diverge by sync, stream, or async mode. |
| Terminal live lifecycle | `terminal/live.py` | 87/136 (64.0%) | 13/36 (36.1%) | Terminal | Cursor/signal cleanup or background refresh may leak or corrupt output. |
| Worker decisions | `utils/workers.py` | 65/97 (67.0%) | 21/38 (55.3%) | Utility | Bad environment detection or worker count advice under unsupported conditions. |
| Public composition helpers | `composition.py` | 0/25 (0.0%) | 0/8 (0.0%) | Runtime | Framework validation helpers can regress while nearby `Template` methods stay green. |

### Sandbox follow-up evidence (2026-07-17)

Issue [#304](https://github.com/lbliii/kida/issues/304) added hostile behavioral
proof for callable allowlists, trusted environment globals, Kida-compiled local
and imported functions, optional calls, mutating methods, exact dicts, dict
subclasses, mapping-protocol fallbacks, import-policy namespace behavior, and
cumulative output limits across full, block, sync-stream, and async-stream
surfaces.

The focused command below now covers 172/172 sandbox statements and 56/56
branches (100%), up from the issue's recorded 59.7% combined focused baseline:

```bash
uv run pytest \
  tests/test_sandbox_fuzz.py \
  tests/unit/test_sandbox.py \
  tests/test_sandbox_callable_policy.py \
  tests/test_sandbox_policy_branches.py \
  --cov=kida.sandbox --cov-branch --cov-report=term-missing -q
```

This closes the sandbox row's named local proof gap; it does not change the
inventory's historical full-suite totals or close the other #192 contract rows.

## #192 checklist reconciliation

### 1. Raise overall branch coverage to a justified 90%+

Status: **open**.

Evidence: the full-suite command above is the exact executable baseline. It
proves 90.1% statements, 80.2% branches, and 87.34% combined coverage. The
active local threshold is defined by [`Makefile`](../../Makefile) `test-cov`;
branch measurement and the lower default are defined in
[`pyproject.toml`](../../pyproject.toml).

Gap: 1,255 branches remain unexecuted. The next work must target the consequence
table above, not add low-risk tests merely to increase the aggregate. No
threshold change is authorized.

Owner: Test Corpus Steward, with each source-domain steward.

### 2. Reach 95%+ for the six named critical contracts

Status: **open; existing behavioral evidence is partial**.

Representative exact test nodes:

- escaping: `tests/test_markup_security.py::TestNULByteHandling::test_nul_in_attribute`
  and `tests/test_markup_security.py::TestMarkupOperations::test_add_escapes_plain_string`;
- sandbox: `tests/test_sandbox_fuzz.py::TestBlocklistHonored::test_any_blocked_hop_raises_security_error`,
  `tests/test_sandbox_fuzz.py::TestAllowlistClosed::test_chain_outside_allowlist_raises`,
  and `tests/unit/test_sandbox.py::TestSandboxedRange::test_range_exceeds_limit`;
- resolution: `tests/test_relative_template_resolution.py::test_relative_escape_rejected`
  and `tests/test_template_aliases.py::test_unknown_alias_rejected_with_hint`;
- caches: `tests/test_bytecode_cache_concurrency.py::TestBytecodeCacheConcurrency::test_concurrent_misses_clear_and_source_hash_invalidation`
  and `tests/test_lru_cache_concurrency.py::TestLRUCacheConcurrency::test_concurrent_misses_clear_and_eviction`;
- component validation: `tests/test_validate_call_types.py::TestValidateCallTypesCLI::test_imported_alias_signature_and_type_validation`
  and `tests/test_validate_call_types.py::TestValidateCallTypesCLI::test_dynamic_import_skips_component_validation`;
- diagnostics: `tests/test_diagnostics_contract.py::test_every_error_code_is_documented`,
  `tests/test_diagnostics_contract.py::test_undefined_error_structured_diagnostic_for_framework_views`,
  and `tests/test_analysis_error_codes.py::test_analysis_code_categories_are_stable`.

Gap: no named group reaches 95% branch coverage. Sandbox callable allowlists,
optional attribute resolution, mapping-subclass fallbacks, and `allow_import`
are the highest-consequence uncovered paths. Resolution, caches, validation,
and diagnostics also need failure assertions for their recorded missing
branches; percentage alone cannot close them.

Owners: Utility, Environment, Template Runtime, Static Analysis, and Tests.

### 3. Cover every documented public helper and retained top-level export

Status: **open**.

Evidence:

- `tests/test_public_api_snapshot.py::test_public_api_snapshot` detects public
  signature drift;
- `tests/test_public_api_classification.py::test_every_top_level_export_has_exactly_one_classification`
  detects classification drift;
- `tests/test_render_with_blocks.py::TestRenderWithBlocks::test_unknown_block_raises_structured_error`
  covers the `Template` composition method, not the public helpers in
  `kida.composition`.

Gap: snapshots/classification are not behavior proof. `src/kida/composition.py`
has 0/8 covered branches, including `validate_block_exists()`,
`validate_template_block()`, `get_structure()`, and
`block_role_for_framework()`. A per-export behavior inventory is also still
needed after the public documentation work settles which names are retained.

Owners: Kida Runtime, Internal Docs, and Tests.

### 4. Add bounded mutation testing in the seven selected domains

Status: **not started; gated**.

Evidence: repository search finds no mutation runner, configuration, score, or
surviving-mutant triage. The older render-surface plan explicitly deferred
mutation testing. Ordinary coverage is not a substitute.

Gap: define bounded pilots for signature/diagnostic selection,
escaping/sandbox, resolution/cache, and purity/partial evaluation. Installing a
tool, adding configuration, or scheduling it is a stop-and-ask change.

Owners: Tests plus the Analysis, Utility, Runtime, and Compiler stewards.

### 5. Add differential tests across optimization, caches, render modes, and surfaces

Status: **partial**.

Existing exact evidence:

- full/sync-stream/async-stream parity:
  `tests/test_render_surface_parity.py::TestFullRenderParity::test_full_parity[05.all.block.d0]`;
- block/async-block parity:
  `tests/test_render_surface_parity.py::TestBlockRenderParity::test_block_parity[25.all.block_plus_region.d2]`;
- property-based block parity:
  `tests/test_render_surface_parity.py::test_let_block_fragment_render_parity`;
- surface-accounting guard:
  `tests/test_render_surface_parity.py::TestRenderSurfaceMeta::test_every_render_method_is_classified`;
- source compile versus bytecode hit:
  `tests/test_kida_bytecode_cache.py::TestBytecodeCacheIntegration::test_environment_with_bytecode_cache`;
- partial-evaluation values through bytecode:
  `tests/test_partial_eval.py::TestNonConstantSafeTypes::test_bytecode_cache_round_trip`.

Gap: there is no general optimized-versus-unoptimized oracle or supported
test-only seam, and source/bytecode equality covers only narrow fixtures.
`render_async` and `render_with_blocks` are classified exceptions rather than
members of the same-equality corpus; each still needs its own declared contract.

Owners: Compiler, Template Runtime, Render Surfaces, and Tests.

### 6. Add parser/formatter AST-equivalence property tests

Status: **partial**.

Existing exact evidence:

- `tests/test_kida_property_parser.py::TestParserProperties::test_parse_tokenize_never_crashes`;
- `tests/test_kida_property_parser.py::TestParserProperties::test_parser_fuzz_no_unhandled`;
- `tests/unit/test_formatter.py::test_nested_indentation`;
- `tests/unit/test_formatter.py::test_block_tag_ws_strip_both`.

Gap: formatter examples do not prove
`parse(source) == parse(format(source))`. The child must define semantic AST
normalization that ignores locations and formatting-only source differences,
then generate only parser-valid inputs. This is property proof, not a formatter
coverage task; formatter branch coverage is already 96.2%.

Owners: Parser/Syntax and Tests.

### 7. Expand malformed/hostile-source fuzzing with stable code and location

Status: **partial**.

Existing exact evidence:

- `tests/test_kida_property_parser.py::TestParserProperties::test_parser_raises_only_expected_errors`
  proves no unexpected exception type;
- `tests/test_sandbox_fuzz.py::TestDefaultVsSandbox::test_sandbox_blocks_what_default_allows[subclasses-chain]`
  is a fixed hostile differential case;
- `tests/test_sandbox_fuzz.py::TestMaxOutputSizeEnforced::test_output_size_respects_policy`
  checks a bounded policy failure.

Gap: parser properties suppress or accept `LexerError`, `ParseError`, and
`TemplateSyntaxError` without asserting a stable code, template path, line,
column, or next action. `LexerError` also remains the inventoried producer
without a stable code. A structured hostile-source oracle is required; merely
raising only expected classes is insufficient.

Owners: Parser/Syntax, Runtime/Security, Diagnostics, and Tests.

### 8. Add repeated no-GIL race scenarios for the named shared operations

Status: **reconciled as complete by
[closed free-threading epic #158](https://github.com/lbliii/kida/issues/158)
evidence; do not duplicate**.

Exact evidence:

- shared templates and introspection:
  `tests/test_kida_stress_test.py::TestMixedRenderConcurrency::test_shared_template_render_block_stream_and_introspection`;
- cache misses/invalidation:
  `tests/test_kida_stress_test.py::TestSharedEnvironmentStress::test_concurrent_template_misses_clear_and_eviction`,
  `tests/test_bytecode_cache_concurrency.py::TestBytecodeCacheConcurrency::test_concurrent_misses_clear_and_source_hash_invalidation`,
  and `tests/test_lru_cache_concurrency.py::TestLRUCacheConcurrency::test_concurrent_misses_clear_and_eviction`;
- registry copy-on-write:
  `tests/test_kida_stress_test.py::TestSharedEnvironmentStress::test_concurrent_registry_registration_publishes_complete_snapshots`;
- coverage instrumentation:
  `tests/test_kida_stress_test.py::TestCoverageCollectorConcurrency::test_repeated_start_stop_while_other_threads_render`;
- live output and workers:
  `tests/test_kida_stress_test.py::TestTerminalAndWorkerConcurrency::test_shared_live_renderer_and_spinner_updates_are_atomic`
  and `tests/test_kida_stress_test.py::TestTerminalAndWorkerConcurrency::test_worker_selection_is_stable_across_threads`;
- randomized barrier-synchronized repetition:
  `tests/test_randomized_thread_stress.py::test_randomized_supported_operations[seed-0]`.

Workflow evidence is in [`.github/workflows/tests.yml`](../../.github/workflows/tests.yml):
one required PR seed, 25 weekly/manual seeds, and a scheduled debug-runtime
protocol, all with `PYTHON_GIL=0`. The contract and reproduction command live in
the [stability gate](../stability-gate.md).

Remaining low branch coverage in `terminal/live.py` and `utils/workers.py` is a
separate lifecycle/environment-path gap, not evidence that #158's race matrix
must be rebuilt.

Owners: Runtime, Terminal, Utility, and Tests.

### 9. Schedule expensive mutation/fuzz/stress while keeping bounded PR smoke

Status: **partial; mutation portion gated**.

Evidence: `.github/workflows/tests.yml` schedules the full suite, full
benchmarks, 25-seed no-GIL stress, and debug-runtime stress. The PR lane keeps
one randomized seed and focused concurrency suites. Parser and sandbox
Hypothesis tests currently run in the ordinary suite rather than a separately
expanded scheduled profile.

Gap: mutation does not exist, and there is no larger scheduled fuzz profile
with a recorded seed/example budget and artifact. Any workflow/tool change is
stop-and-ask.

Owner: GitHub Workflow and Tests.

### 10. Commission an independent security/concurrency review

Status: **blocked by the epic's own ordering, not started**.

Evidence: there is no review artifact or accepted-finding ledger. The task says
to commission the review only after internal gates are green; rows 1–7 and 9
remain open or partial.

Gap: first close or explicitly disposition the internal proof gaps. External
coordination and accepted-finding tracking require a separate decision.

Owner: Project governance with Runtime/Security and Concurrency stewards.

## Consequence-ranked uncovered work

1. **Sandbox policy failure branches** — callable/type allowlists,
   preserve-`None` attribute paths, dict subclasses, and `allow_import` at 46.2%
   branch coverage. Required proof is hostile input plus exact `K-SEC-*` code,
   location where available, and suggestion.
2. **Public composition and render-helper parity** — public composition is
   entirely uncovered, while include/extends/import/cache helpers are 58.0%
   branch-covered across sync/stream/async paths. Required proof is focused
   behavioral and error-attribution parity, not snapshots.
3. **Template resolution and cache transitions** — resolution is 77.4% and
   cache modules 83.1% branch-covered. Prioritize traversal rejection,
   alias/relative failure context, corrupt/incompatible cache records, and
   invalidation/eviction transitions.
4. **Component and diagnostic decision branches** — both are above 80% but
   below the 95% critical-contract target. Target known false-positive and
   false-negative choices with stable codes/locations.
5. **Terminal lifecycle and worker environment fallbacks** — the no-GIL race
   contract is proven, but TTY signal/atexit/auto-refresh cleanup and uncommon
   environment/CPU-detection branches remain weakly exercised.

## Proposed atomic children

These are deduplicated proof slices, not authorization to change CI or public
behavior.

1. **Public composition helper behavior** — cover all four
   `kida.composition` helpers, inheritance, missing/syntax failure, preserved
   AST absence, and role classification.
2. **Sandbox policy branch corpus** — exercise callable allowlists,
   `allow_import`, dict-subclass/optional lookup, mutating-method policy, and
   exact failure diagnostics.
3. **Render-helper mode differential corpus** — compare include, extends,
   import, ignore-missing, error attribution, and fragment cache behavior
   across applicable sync/stream/async modes.
4. **Optimizer parity test seam** — design a test-only optimized/unoptimized
   compilation seam, then compare output, errors, warnings, and source
   locations on a bounded corpus. Compiler changes need benchmark evidence.
5. **Parser-format-parser semantic property** — define AST normalization and a
   parser-valid Hypothesis strategy; prove idempotence and semantic equivalence.
6. **Structured hostile-source oracle** — assert stable error class/code/path/
   line/column/suggestion for malformed lexer/parser and sandbox inputs.
7. **Source/bytecode cache differential expansion** — cover inheritance,
   imports, static context, preserved AST, warnings, corruption fallback, and
   every render mode that supports the fixture.
8. **Live renderer lifecycle proof** — TTY cursor restoration, signals, atexit,
   transient cleanup, and start/stop auto-refresh without sleep-based
   correctness assertions.
9. **Per-export behavior matrix** — after retention decisions settle, map every
   root export to a focused behavior test or an explicit metadata-only reason.
10. **Four bounded mutation pilots** — signature/diagnostics;
    escaping/sandbox; resolution/cache; purity/partial evaluation. Tool choice,
    dependency/configuration, thresholds, and scheduling remain stop-and-ask.

## Explicitly not changed by this inventory

- No coverage threshold, workflow, dependency, mutation/fuzz tool, exclusion,
  tolerance, or snapshot changed.
- No #192 checkbox is edited from this document.
- No line-coverage percentage is treated as behavioral closure.
- No additional no-GIL child duplicates the completed #158 matrix.
- No external review is commissioned before the internal evidence is ready.

## Post-#329 snapshot — 2026-09-24

Status: current full-suite evidence for the first clean `main` containing #328 / PR #329.

Measured revision: `0cf8763d18d5cdfb4964792b2b7640876c96ce30` (PR #329 merged at
2026-09-24 15:56 UTC).

This is a separate snapshot. The July 9 revision, command, results, and
denominators above remain unchanged. The code, test corpus, and interpreter
build differ, so the old and new totals are not presented as a coverage trend.

### Measurement protocol

Environment:

- macOS 26.6.2, arm64;
- CPython 3.14.2 free-threading build (`3.14.2+freethreaded`; build stamp
  `main`, Jan 27 2026 23:31:54, Clang 21.1.4);
- `PYTHON_GIL=0`; verified `sys._is_gil_enabled() is False`;
- coverage.py 7.13.5.

Exact full-suite command:

```bash
PYTHON_GIL=0 .venv/bin/python -m pytest -q --tb=short --cov=kida --cov-branch --cov-report=json:/private/tmp/kida-330-full-suite-coverage.json --cov-report=term --cov-fail-under=83 --timeout=300
```

The configured pytest scope is `tests/` and `examples/` (`testpaths` in
[`pyproject.toml`](../../pyproject.toml)). Result: 4,888 passed, 6 skipped,
141 warnings in 68.44 seconds. The raw full-suite report used for the totals
below is `/private/tmp/kida-330-full-suite-coverage.json`.

| Metric | Covered / total | Missed | Coverage |
|---|---:|---:|---:|
| Statements | 16,290 / 17,985 | 1,695 | 90.6% |
| Branches | 5,590 / 6,906 | 1,316 | 80.9% |
| Combined statements + branches | 21,880 / 24,891 | 3,011 | 87.9% |

Combined coverage is coverage.py's count of covered statements plus covered
branches over all statements plus branches. The existing `make verify-stability`
command passed on this measured code revision, including lint, format, type,
the test-cov gate, safety suites, and package smoke. Its existing 83% floor is
unchanged; these percentages are evidence, not a new threshold.

### Current critical-contract group coverage

Every numerator and denominator in this table is aggregated from the same raw
full-suite report above. Statement and branch misses are shown explicitly.
Combined percentages are descriptive and are not group closure criteria.

| Contract | Source scope | Statements covered / missed / total | Branches covered / missed / total | Combined |
|---|---|---:|---:|---:|
| Escaping | `utils/html.py`, `utils/markdown_escape.py`, `utils/terminal_escape.py`, `environment/filters/_html_security.py` | 325 / 41 / 366 (88.8%) | 94 / 18 / 112 (83.9%) | 87.7% |
| Sandbox policy | `sandbox.py` | 176 / 0 / 176 (100.0%) | 56 / 0 / 56 (100.0%) | 100.0% |
| Template resolution | `environment/loaders.py`, `utils/template_keys.py` | 160 / 10 / 170 (94.1%) | 48 / 14 / 62 (77.4%) | 89.7% |
| Cache contracts | `bytecode_cache.py`, `utils/lru_cache.py`, `template/cached_blocks.py` | 420 / 119 / 539 (77.9%) | 113 / 43 / 156 (72.4%) | 76.7% |
| Component validation | `analysis/analyzer.py` | 316 / 27 / 343 (92.1%) | 167 / 35 / 202 (82.7%) | 88.6% |
| Diagnostic selection/rendering | `diagnostics.py`, `_diagnostic_adapters.py`, `_diagnostic_renderers.py` | 397 / 16 / 413 (96.1%) | 137 / 23 / 160 (85.6%) | 93.2% |
| Render helpers | `template/render_helpers.py` | 231 / 45 / 276 (83.7%) | 58 / 42 / 100 (58.0%) | 76.9% |
| Terminal live lifecycle | `terminal/live.py` | 87 / 49 / 136 (64.0%) | 13 / 23 / 36 (36.1%) | 58.1% |
| Worker decisions | `utils/workers.py` | 65 / 32 / 97 (67.0%) | 21 / 17 / 38 (55.3%) | 63.7% |
| Public composition helpers | `composition.py` | 25 / 0 / 25 (100.0%) | 8 / 0 / 8 (100.0%) | 100.0% |

### Completed evidence and scope boundaries

- [#158](https://github.com/lbliii/kida/issues/158) is closed. Its repeated
  no-GIL race matrix covers shared-template rendering/introspection, cache
  misses and invalidation, copy-on-write registration, coverage instrumentation,
  live output/workers, and randomized repetitions. This proves the named
  concurrency contract; it does not close the separately measured lifecycle
  branches in `terminal/live.py` or `utils/workers.py`.
- [#257](https://github.com/lbliii/kida/issues/257) is closed. It adds direct
  behavioral proof for all four `kida.composition` helpers; the current
  full-suite group is 25/25 statements and 8/8 branches. This closes that helper
  slice, not the broader per-export behavior inventory in checklist item 3.
- [#274](https://github.com/lbliii/kida/issues/274) is closed. Its bounded
  source-versus-bytecode-cache corpus covers the listed inheritance, import,
  static-context, preserved-AST, warning, corrupt/incompatible-record, and
  supported render-mode cases. The current cache-group coverage is reported
  above. This does not supply a general optimized-versus-unoptimized oracle or
  prove every fixture across every render surface.
- [#304](https://github.com/lbliii/kida/issues/304) is closed. Its focused
  sandbox run recorded 172/172 statements and 56/56 branches at that evidence
  point. The current full-suite report has a 176-statement denominator and
  56/56 branches for the same source file. Keep these focused and full-suite
  scopes distinct; the current full-suite result is the table above.
- [#328](https://github.com/lbliii/kida/issues/328) is closed by
  [PR #329](https://github.com/lbliii/kida/pull/329). The property
  `tests/test_kida_property_formatter.py::TestFormatterProperties::test_parse_format_parse_preserves_ast`
  proves AST equality for its bounded trim-controlled, parser-valid generator,
  excluding only source positions. It does not claim equivalence for arbitrary
  whitespace-bearing templates or prove render-output preservation.

### #192 checklist reconciliation at this snapshot

| Item | Post-#329 disposition | Current evidence and remaining gap |
|---|---|---|
| 1. Raise overall branch coverage to a justified 90%+ | **Open** | The full-suite report measures 5,590/6,906 branches (80.9%), with 1,316 missed. `make verify-stability` passes the unchanged 83% floor; neither result closes the 90% branch target. |
| 2. Reach 95%+ for six critical contracts | **Open; sandbox slice closed** | Only sandbox policy reaches 95% branch coverage (56/56). Escaping, resolution, caches, component validation, and diagnostics remain below 95%; use the group table above. |
| 3. Cover every documented helper and retained top-level export | **Open; composition slice closed** | #257 proves the four composition helpers and the full-suite report measures 8/8 branches there. A behavior inventory for every retained top-level export remains open. |
| 4. Add bounded mutation testing | **Not started; gated** | No mutation run or score is recorded in the current #192 evidence. Tooling, dependency, thresholds, and scheduling remain separate decisions. |
| 5. Add differential tests across optimization, caches, render modes, and surfaces | **Partial; #274 slice closed** | Source/cache differential cases are complete within #274's declared fixture and mode matrix. A general optimization oracle and broader render-surface corpus remain gaps; the separate #305 streaming behavior is still gated on owner authorization and the Chirp pilot. |
| 6. Add parser/formatter AST-equivalence property tests | **Bounded target complete** | #328 closes the generated trim-controlled subset with exact AST-field preservation. Broader whitespace-bearing input is intentionally outside that proof; no universal formatter claim is made. |
| 7. Expand malformed/hostile-source fuzzing with stable code and location | **Partial** | #328 left existing malformed-source properties unchanged. They still do not establish stable code, path, line, column, and next action for every lexer/parser failure. |
| 8. Add repeated no-GIL race scenarios | **Complete for the named matrix** | Closed #158 supplies the repeated race and scheduled stress evidence. The current full suite also ran with GIL disabled; the low lifecycle/environment branch counts are distinct gaps, not a reason to duplicate the race matrix. |
| 9. Schedule expensive mutation/fuzz/stress while keeping bounded PR smoke | **Partial** | #158 supplies scheduled repeated no-GIL stress. Mutation proof and a separately expanded scheduled fuzz profile remain unproven; no workflow or tooling change is included here. |
| 10. Commission an independent security/concurrency review | **Not started; gated by order** | The inventory's own prerequisite requires internal proof gaps to close or be dispositioned first. Items 1–5, 7, and 9 remain open or partial, so no review is commissioned by this refresh. |

### Re-ranked candidates from this report

The following order is by missed branch proportion in the measured groups,
not by a claim that every uncovered branch is a defect:

| Measured rank | Contract | Branches covered / missed / total | Branch coverage |
|---:|---|---:|---:|
| 1 | Terminal live lifecycle | 13 / 23 / 36 | 36.1% |
| 2 | Worker decisions | 21 / 17 / 38 | 55.3% |
| 3 | Render helpers | 58 / 42 / 100 | 58.0% |
| 4 | Cache contracts | 113 / 43 / 156 | 72.4% |
| 5 | Template resolution | 48 / 14 / 62 | 77.4% |
| 6 | Component validation | 167 / 35 / 202 | 82.7% |
| 7 | Escaping | 94 / 18 / 112 | 83.9% |
| 8 | Diagnostic selection/rendering | 137 / 23 / 160 | 85.6% |

Candidate for the next bounded research slice: map `terminal/live.py`'s
uncovered lifecycle branches to the intended cursor, signal, cleanup, and
refresh contracts before proposing tests. Confidence is **medium** that this is
a substantial proof gap because it is the lowest measured group; confidence in
behavioral risk is **low until those branches are traced**. The terminal
steward's branch-to-contract mapping is the dependency. Coverage alone does not
justify a runtime, API, threshold, or workflow change.

Downstream pilot classification:

No downstream pilot: documentation or planning changed without changing normative behavior;
replacement proof: the provenance-complete full-suite coverage report at
`/private/tmp/kida-330-full-suite-coverage.json` and `make verify-stability`;
affected contracts: the internal assurance inventory.

### #335 LiveRenderer lifecycle map (current-main inspection)

Inspected source SHA: `e27e09bd6a56e4a8e25d017c70a5423c1a23ea1b`. The
`13/36` branch result (36.1%, 23 missed) above belongs to #330's coverage run
on code SHA `0cf8763d18d5cdfb4964792b2b7640876c96ce30`; it is not a new
measurement of this source SHA. Comparing `src/kida/terminal/live.py` at those
revisions shows no source drift. Branch misses identify unproved paths, not
runtime defects.

| Lifecycle promise and source | Contract/documentation | Existing test evidence | Gap and deterministic next proof |
|---|---|---|---|
| Cursor hide/show and normal exit: `src/kida/terminal/live.py:211-215,227-235` | `docs/terminal-api-contract.md:65-70`; `site/content/docs/usage/terminal-rendering.md:463-468` | `tests/terminal/test_live.py::TestLiveRenderer::test_non_tty_fallback` uses `StringIO`; it does not enter the TTY branch. | No TTY cursor lifecycle proof. Use a fake TTY stream and direct enter/exit; assert hide on enter and show on exit without timing. |
| Ctrl+C and atexit restoration: `src/kida/terminal/live.py:217-244,324-339` | `docs/terminal-api-contract.md:65-75`; `site/content/docs/usage/terminal-rendering.md:463-468` | No focused test captures signal or atexit registration. | Capture registrations with monkeypatched `signal`/`atexit`; invoke callbacks directly and assert cursor-show, prior-handler restoration, and unregister on exit. Do not send a process signal. |
| Transient output cleanup: `src/kida/terminal/live.py:227-234,308-314` | Constructor option in `site/content/docs/usage/terminal-rendering.md:470-478`; `transient` is also in the stable API signature at `docs/terminal-api-contract.md:51-57`. | `tests/terminal/test_live.py::TestLiveRenderer::test_transient_mode` covers only non-TTY `StringIO`, where cleanup is skipped. | No TTY cleanup proof. Render multiple lines to a fake TTY, exit transient mode, and assert each prior line is erased before cursor-show. |
| TTY redraw, resize, and size-query fallback: `src/kida/terminal/live.py:246-275,308-322` | `docs/terminal-api-contract.md:67-72`; `site/content/docs/usage/terminal-rendering.md:463-468` | `test_context_accumulates`, `test_update_holds_lock_through_render`, and `tests/test_randomized_thread_stress.py::test_randomized_supported_operations` use non-TTY `StringIO`; the stress case calls `update()`, not the auto loop. | No TTY overwrite, stale-line clearing, resize, or `OSError`/`ValueError` query-failure proof. With a fake TTY and monkeypatched `os.get_terminal_size`, make direct updates and assert redraw/width behavior and that a size-query error does not prevent rendering. |
| Auto-refresh start/stop and teardown: `src/kida/terminal/live.py:227-229,276-305,330-333` | `docs/terminal-api-contract.md:60-75`; `site/content/docs/usage/terminal-rendering.md:479-490` | No focused `start_auto()`/`stop_auto()` test. The randomized stress case covers concurrent manual updates only. | Use `threading.Event` gates around a fake render to coordinate start and stop without sleeps. A controlled current-main probe reproduced a render writing after context exit when `stop_auto()`'s two-second join timed out; see the owner-decision note below before choosing an assertion. |
| Documented non-TTY fallback: `src/kida/terminal/live.py:194-200,271-274,316-322` | `docs/terminal-api-contract.md:65-69`; `site/content/docs/usage/terminal-rendering.md:514-516,683-690` | `test_non_tty_fallback`, `test_context_accumulates`, and `test_transient_mode` use `StringIO`; the randomized stress case also uses `StringIO`. | Basic append behavior is directly exercised, but tests only check included text, not the exact blank-line separator or absence of cursor escapes. Assert the exact two-render log output and no cursor controls using `StringIO`; no sleeps or platform dependency. |

#### Reproduced teardown observation and follow-up boundary

At the inspected source SHA, a no-source-change probe used a fake template whose
`render()` waited on an event. After `start_auto()` entered that render,
`stop_auto()` returned after its two-second join timeout with the worker still
alive. Context exit completed with no output; releasing the render then wrote
`late-render\n` to the stream after exit. The event gates establish ordering and
the probe uses no sleeps. This confirms the late-write behavior. Whether the
bounded join is intended to permit that write or violates the lifecycle
contract remains an owner decision; resolve that before setting a regression
expectation or changing runtime behavior.

The smallest deterministic test-only candidate is a fake-TTY lifecycle slice
for cursor, transient cleanup, redraw, and resize/error handling, plus direct
StringIO assertions for the documented non-TTY output. Signal and atexit
callbacks can be tested by capturing their registrations. The auto-refresh
teardown assertion stays gated on the owner decision above; coordinate it with
events rather than sleeps.

**Steward notes.** Consulted stewards: root, terminal, docs, site, and tests.
Risk: confusing the measured branch gap or observed timeout behavior with an
already-decided public contract. Evidence: #330's coverage snapshot, current
main source and contract paths in the matrix, focused/stress tests, and the
controlled no-change teardown probe. Collateral: this internal inventory only;
no runtime, test, or published-site files changed, so a site build is not
applicable. Unresolved tradeoff: whether shutdown must prevent a render from
writing after context exit or may return after the existing bounded join. The
downstream behavior classification for any eventual runtime change remains
unresolved until the owner chooses that contract.

Downstream pilot classification:

No downstream pilot: no downstream-observable contract changed;
replacement proof: current-main source-to-contract/test matrix and deterministic test proposal;
affected contracts: none.
