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
