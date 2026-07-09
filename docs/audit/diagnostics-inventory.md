# Diagnostic Contracts Inventory

Status: complete; model, surfaces, programmatic API, safe edits, and extension protocol are implemented

Scope: exceptions, compiler warnings, parser and lexer failures, static-analysis
findings, `kida check`, renderers, framework adapters, and machine-facing output

Tracking: [GitHub issue #193](https://github.com/lbliii/kida/issues/193)

Evidence date: 2026-07-08

## Purpose

Kida has stable error codes, structured exception data, immutable analysis
findings, and human-oriented diagnostic renderers. Those capabilities currently
belong to separate producer families. This inventory records the facts each
family already exposes, where they are consumed, and the gaps a unified
diagnostic service must preserve or close.

This document does not select a new default severity policy. That remains a
separate stop-and-ask decision under the root constitution. The approved CLI
and Python slices add output selection, a versioned serialization schema, and a
public programmatic model without changing check enablement, severity, or exit
policy.

Implementation status: the canonical public model now lives in
[`src/kida/diagnostics.py`](../../src/kida/diagnostics.py), with compatibility
adapters in
[`src/kida/_diagnostic_adapters.py`](../../src/kida/_diagnostic_adapters.py).
The model is immutable, registry-free, public through `kida.diagnostics`, and
intentionally absent from the root `kida.__all__`. It defines severity and
confidence facts, 1-based-line/
0-based-column half-open spans, related locations, exact safe edits, snippets,
and a pure callable conversion protocol. The first adapter consumes the existing
`TemplateDiagnostic` returned by `UndefinedError.to_diagnostic()` without
changing that documented payload or its renderers.

The private adapter layer accepts every inventoried producer family that owns a
stable code: parser and runtime exceptions, compiler `TemplateWarning` records,
component call/type findings, privacy findings, context-contract issues,
escape-audit findings, accessibility issues, template-declaration type issues,
and fragile-path issues. Conversion is opt-in and does not alter producer return
types or import the adapter into parser, compiler, analyzer, render, or CLI
execution paths. `LexerError` remains the only inventoried family without an
attached stable code; its taxonomy and hot-path integration require separate
review.

`kida check` now converts those producers at one collection boundary, preserves
the existing text surface, and can emit diagnostics JSON v1 or SARIF 2.1.0.
`diagnose_directory()` exposes that collection without CLI policy;
`diagnose_source()` handles unsaved buffers without entering template or
bytecode caches; and `diagnostic_from_exception()` gives framework adapters a
safe conversion path. Strict unified closers now carry exact, snapshot-backed
safe edits, and `apply_safe_edits()` rejects stale or overlapping edits before
application. Namespaced `Extension.diagnose()` hooks receive immutable source,
AST, and visible component metadata only for caller-supplied source diagnosis.
Core validation rejects namespace/category/confidence/location/edit violations,
and isolates each hook failure as a partial `K-RUN-007` finding.

## Current Topology

| Producer | Current record or exception | Code/category | Severity | Location | Suggestions and context | Current consumers |
|---|---|---|---|---|---|---|
| Lexer | `LexerError` | No `ErrorCode` field | Implicit error | `lineno`, zero-based `col_offset`; source retained | Optional suggestion and rendered source caret | Parser/environment exception path and `str(exc)` |
| Parser | `ParseError` / `TemplateSyntaxError` | `ErrorCode`, normally `K-PAR-*` or `K-TPL-002` | Implicit error | line, zero-based column, filename/name, optional source | Optional suggestion; parser formats its own source display | Environment callers, `kida check`, compact exception text |
| Runtime | `TemplateError` hierarchy | `ErrorCode`, including `K-RUN-*`, `K-TPL-*`, and `K-SEC-*` | Implicit error | Attributes vary by subtype; syntax errors use `name`/`filename`, runtime errors use `template_name`, undefined errors use `template` | Some subtypes carry source snippets, expression, values, suggestion, template stack, and component stack | Programmatic callers, framework adapters, compact terminal/log text |
| Undefined runtime access | `UndefinedError` -> internal `TemplateDiagnostic` | `ErrorCode`, normally `K-RUN-001` | Implicit error | `DiagnosticLocation(template, line, column, filename)` | Immutable snippet, ordered hints, docs URL, related template/component frames, string metadata | Compact exception renderer plus HTML fragment/page and Markdown renderers |
| Compiler warnings | `TemplateWarning` | `ErrorCode`, currently `K-WARN-*` | Implicit warning | `template_name`, line only | Optional suggestion | `Template.warnings`, `format_message()` |
| Python warnings | `KidaWarning` subclasses and direct `warnings.warn()` calls | Warning class or plain `UserWarning`; generally no stable code | Python warning category | Python call site via `stacklevel`; not a template range | Message only in most cases | Python warnings filters and host logging |
| Component call validation | `CallValidation` | CLI assigns `K-CMP-001` | Treated as a failing problem | line and zero-based column on the record; CLI prints line only | Unknown, missing, and duplicate parameter tuples | `kida check --validate-calls`, programmatic `BlockAnalyzer` callers |
| Component literal types | `TypeMismatch` | CLI assigns `K-CMP-002` | Treated as a failing problem | line and zero-based column on the record; CLI prints line only | Definition, parameter, expected type, actual type/value | `kida check --validate-calls`, programmatic `BlockAnalyzer` callers |
| Accessibility | `A11yIssue` | Computed `K-A11Y-001` through `K-A11Y-004` from its literal rule | String `warning` or `error` | line and zero-based column; template path supplied by caller | Message only | `kida check --a11y`, direct analyzer callers |
| Template declaration types | `TypeIssue` | Computed `K-TYP-001` through `K-TYP-003` from its literal rule | String `warning` or `error` | line and zero-based column; template path supplied by caller | Message may contain a correction | `kida check --typed`, direct analyzer callers |
| Fragile paths | `FragilePathIssue` | Computed `K-PATH-001`; CLI retains `lint/fragile-path` text | String, currently `warning` | line and zero-based column; caller name supplied separately | Statement, target, concrete replacement path | `kida check --lint-fragile-paths`, direct analyzer callers |
| Privacy | `PrivacyFinding` | Registered `K-PRI-001` through `K-PRI-005` string field | Literal `error` or `warning` | optional template, line, zero-based column, and data path | Kind and optional suggestion | `kida.analysis` programmatic API and published analysis docs |
| Context contracts | `ContextContractIssue` | Registered `K-CTX-001` or `K-CTX-002` string field | Literal `error` or `warning` | optional template, line, zero-based column, and context path | Optional suggestion | `kida.analysis` programmatic API and published analysis docs |
| Escaping audit | `EscapeAuditFinding` | Registered `K-ESC-001` through `K-ESC-005` string field | Literal `info` or `warning` | optional template, line, and zero-based column | Kind, expression, optional suggestion | `kida.analysis` programmatic API and published analysis docs |

Primary evidence:

- [`src/kida/exceptions.py`](../../src/kida/exceptions.py) owns `ErrorCode`,
  `TemplateWarning`, `SourceSnippet`, the exception hierarchy, and the current
  internal `TemplateDiagnostic` family.
- [`src/kida/lexer.py`](../../src/kida/lexer.py) and
  [`src/kida/parser/errors.py`](../../src/kida/parser/errors.py) own the lexer and
  parser-specific location and rendering behavior.
- [`src/kida/analysis/`](../../src/kida/analysis/) owns the immutable finding and
  component-validation records.
- [`src/kida/cli.py`](../../src/kida/cli.py) currently adapts several of those
  records directly into `kida check` text.

## Stable Pieces To Preserve

### Error codes and documentation

`ErrorCode` is a public enum exported from `kida`. Its current `K-LEX`, `K-PAR`,
`K-RUN`, `K-TPL`, `K-SEC`, `K-CMP`, and `K-WARN` values are snapshot-tested and
each value is required to have a published errors-document anchor. The enum also
derives a category and documentation URL.

The existing `K-PRI`, `K-CTX`, and `K-ESC` values are now registered in
`ErrorCode` without renumbering. Accessibility, template-declaration type, and
fragile-path records expose computed `K-A11Y`, `K-TYP`, and `K-PATH` codes while
preserving their constructor fields. Every registered value participates in the
same public API snapshot and documentation-anchor test.

### Immutable structured exception data

`SourceSnippet`, `DiagnosticLocation`, `DiagnosticFrame`, and
`TemplateDiagnostic` are frozen, slotted dataclasses. `TemplateDiagnostic`
already represents plain surface-neutral data:

- code, title, message, and kind;
- one template location;
- optional source snippet;
- ordered hints, a suggestion, and documentation URL;
- template and component frames; and
- string key/value metadata.

It also renders escaped HTML fragments/pages and Markdown. The types are not in
`kida.__all__`, and only `UndefinedError` currently exposes `to_diagnostic()`.
Other exception subtypes continue to render directly from their own attributes.
That makes this an implementation seed, not yet the single diagnostic contract
described by issue #193.

### Existing exception hierarchy

Applications can catch `TemplateError` broadly or its public subtypes
specifically. A unification should adapt those exceptions into diagnostics, not
replace the hierarchy. `format_compact()` is also documented public behavior,
although the exact fields and visual structure differ across subtypes.

### Analyzer records

All inventoried analysis findings and component-validation results are frozen,
slotted dataclasses. Their direct programmatic use is documented for several
analysis APIs. Convergence can therefore be additive: convert records at the
collection boundary while preserving the records returned by existing analyzer
functions.

## Consumer And Surface Matrix

| Surface | Input today | Output today | Structured parity |
|---|---|---|---|
| Python exceptions | Exception subtype attributes | `str(exc)` and `format_compact()` | Partial; attribute names and available facts vary |
| Framework debug pages | Propagated Kida exception | Flask, Django, and Starlette adapters do not wrap or normalize the exception | Hosts can call public `diagnostic_from_exception()` without parsing text |
| HTML diagnostics | `UndefinedError.to_diagnostic()` | Escaped fragment or standalone page | Undefined errors only |
| Markdown diagnostics | `UndefinedError.to_diagnostic()` | GitHub-flavored Markdown | Undefined errors only |
| `kida check` | Exceptions plus analysis/component records converted at a private boundary | Compatible stderr text, diagnostics JSON v1, or SARIF 2.1.0 | Shared facts, deterministic ordering/de-duplication, exit status, and partial-scan state across all three surfaces |
| Other CLI commands | Command-specific values | Some commands have command-specific JSON | Not a diagnostics contract |
| SARIF utility | External SARIF report data | Template/report context dictionary | Input parser only; it does not emit Kida findings |
| CI report templates | Parsed report contexts and render data | HTML, terminal, Markdown, or CI summaries | Separate report schema; not fed by `kida check` diagnostics |
| Editor/LSP/codemod | Public `diagnose_source()` / `diagnose_directory()` | Immutable `DiagnosticReport` | Shared paths, ranges, related locations, confidence, suggestions, and optional exact edits; edit generation remains conservative and separate |

Framework evidence is in [`src/kida/contrib/`](../../src/kida/contrib/): the
Flask, Django, and Starlette integrations render through a Kida `Template` and
allow Kida failures to propagate. This preserves exception identity, and hosts
can now convert supported Kida exceptions through one public function.

The external SARIF parsing path is
[`src/kida/utils/sarif.py`](../../src/kida/utils/sarif.py). Its existence must
not be mistaken for a SARIF diagnostics output path.

## Contract Gaps

1. **Lexer instances do not carry their registered taxonomy.** Public
   `ErrorCode` owns `K-LEX-001` through `K-LEX-004`, but `LexerError` has no code
   field and several lexical failures do not fit those four categories. The
   programmatic boundary therefore uses generic `K-TPL-002` until a separately
   reviewed lexer taxonomy is complete.
2. **Location vocabulary and completeness drift.** Producers use `name`,
   `filename`, `template`, or `template_name`; records use `lineno` and
   `col_offset`; renderers use `line` and `column`. Columns are zero-based where
   documented, but most CLI lines omit them. End positions are absent.
3. **Severity is not one contract.** Exceptions and `TemplateWarning` imply
   severity by type, analyzer records store strings, and `kida check` counts all
   enabled findings as failures regardless of the record's severity value.
4. **Rich producer context is uneven.** The canonical model can carry safe
   edits, related locations, confidence, runtime-only/unknown state, snippets,
   and docs URLs, but many producer families do not supply those facts. Strict
   unified closers are the first public safe-edit producer; ambiguous type,
   path, component, and migration suggestions remain advisory.
5. **The public service covers the current check families, not every analyzer.**
   Directory and unsaved-source collection expose the CLI checks, while privacy,
   context, escape, compiler-warning, and future migration orchestration remain
   direct producer APIs until separately integrated.
6. **Ordering and de-duplication are shared collection policy.** `kida check`,
   `diagnose_directory()`, and `diagnose_source()` order by phase, path, range,
   code, and message and remove exact `(code, path, range, message)` duplicates.
7. **Python warnings are a separate channel.** Many filter/global/environment
   warnings are normal `warnings.warn()` emissions without stable codes or
   template locations. Compiler `TemplateWarning` records should not be assumed
   to cover them.
8. **Serialization remains a CLI contract.** Python callers receive immutable
   records rather than JSON/SARIF dictionaries. This keeps the programmatic API
   policy-neutral while the versioned machine schemas remain owned by
   `kida check`.

## Convergence Boundaries

The following classification preserves existing contracts while reducing
parallel interpretation.

### Convert at a collection boundary

- `CallValidation` and `TypeMismatch`;
- `A11yIssue`, `TypeIssue`, and `FragilePathIssue`;
- `PrivacyFinding`, `ContextContractIssue`, and `EscapeAuditFinding`; and
- `TemplateWarning`.

Their producer APIs should continue returning their existing records. A
collector can translate those facts into an internal common diagnostic without
making every analyzer depend on a CLI or serialization layer.

### Adapt without replacing

- Preserve the public `TemplateError` hierarchy and add internal conversion for
  its subtypes.
- Preserve `format_compact()` while making human renderers consume the same
  normalized facts where compatibility permits.
- Preserve framework exception propagation; expose normalized data only through
  a separately approved programmatic contract.

### Keep outside the diagnostic model

- Coverage and profiling counters;
- template metadata that is not a finding;
- parsed third-party report contents; and
- raw Python traceback frames.

Those may be attached or linked by a consumer, but treating them as diagnostics
would blur findings with evidence or execution telemetry.

## Proposed Dependency Order

This is sequencing guidance, not approval to implement the contracts.

1. **Complete:** define an internal immutable diagnostic, span,
   related-location, and optional safe-edit model.
2. **Complete:** add lossless converters for existing exceptions and analysis
   records, then prove deterministic cross-family ordering and de-duplication.
3. **Complete:** make the current human `kida check` output consume normalized
   records without changing default policy or exit behavior.
4. **Complete:** separately approve and add machine-readable CLI modes and
   schema snapshots.
5. **Complete:** separately approve a public programmatic API for editors,
   adapters, and codemods.
6. **Complete:** emit only proven safe edits and reject stale, incomplete, or
   overlapping applications.
7. **Complete:** add extension hooks after defining ownership, namespacing,
   immutable context, current-source validation, and failure isolation.

Issue #147 depends on the collection and rendering seams described here; issue
#194 depends on stable diagnostic attribution. Public editor and codemod work
should wait for the model, range, and safe-edit contracts.

## Stop-And-Ask Decisions

| Decision | Why approval is required |
|---|---|
| Default severities and which findings fail `kida check` | Changes CLI policy and exit behavior |
| New `kida check` flags or output selection | Public CLI change |
| JSON or SARIF field names and versioning | New published schema commitment |
| Changing diagnostic types or collection functions | Public API compatibility change; the module remains intentionally absent from root `kida.__all__` |
| Expanding safe-edit applicability | Automatic source changes require exact spans, snapshot verification, and proof that the replacement is unambiguous |
| Extension diagnostic protocol | **Complete:** public `ExtensionDiagnosticContext`, `K-{NAMESPACE}-{NNN}` ownership, core validation, built-in ordering/de-duplication, and per-hook `K-RUN-007` isolation |
| Framework-specific debug behavior | Public adapter behavior and possible information exposure |

## Required Proof For Follow-up Work

| Follow-up | Required proof | Collateral |
|---|---|---|
| Canonical model/converters | Unit tests for model invariants and each converted producer family, including missing-location cases, source ranges, immutability, and fact preservation | Update this inventory and public API docs when the model changes |
| CLI collection/refactor | Existing human snapshots unchanged, deterministic ordering/de-duplication, partial-load failures, and current exit status preserved | CLI docs only if visible behavior changes |
| JSON/SARIF output | Schema snapshots, escaping/redaction tests, malformed/partial input behavior, and SARIF validator coverage | CLI reference, examples, changelog, and schema/version policy |
| Programmatic API | **Complete:** public API snapshot, typing checks, concurrent shared-read proof, CLI parity, unsaved-source and framework-exception tests | API docs, README example, changelog; no migration note because no older general API was replaced |
| Safe edits | **Complete:** exact source-span tests, stale-source rejection, overlapping-edit behavior, multi-edit application, and advisory-only negative proof | API/CLI docs, README example, changelog; JSON v1 shape unchanged |
| Extension diagnostics | **Complete:** namespace registration rejection, public API snapshot, local/imported `DefMetadata`, immutable context, ordering/de-duplication, safe-edit validation, peer continuation, and concurrent shared-environment proof | Extension guide, API reference, runnable example, changelog; no CLI/schema/render change |

## Existing Proof

- [`tests/test_diagnostics_contract.py`](../../tests/test_diagnostics_contract.py)
  checks error documentation anchors, structured undefined data, escaping,
  Markdown/HTML rendering, and compact output.
- [`tests/test_public_api_snapshot.py`](../../tests/test_public_api_snapshot.py)
  snapshots the public `ErrorCode` values and exported API.
- [`tests/test_public_diagnostics.py`](../../tests/test_public_diagnostics.py)
  snapshots the module API and proves unsaved-source, cross-template,
  directory/CLI parity, exception conversion, concurrent shared-read use, and
  safe-edit applicability enforcement.
- CLI tests under [`tests/`](../../tests/) assert current `kida check` messages,
  counts, and exit behavior for enabled analyzers.
- Published error and analyzer contracts live under
  [`site/content/docs/usage/error-handling.md`](../../site/content/docs/usage/error-handling.md)
  and [`site/content/docs/advanced/`](../../site/content/docs/advanced/).

No collateral for examples, scaffolds, or templates: this API consumes source
and existing analyzer facts without changing template syntax or generated
output. Follow-up changes must update the relevant collateral identified above.
