# Top-Level Public API Classification

Status: complete classification baseline; no export or stability policy changed

Scope: every name in the working tree's literal `kida.__all__` on 2026-07-09

Tracking: [GitHub issue #195](https://github.com/lbliii/kida/issues/195)

Evidence: [`src/kida/__init__.py`](../../src/kida/__init__.py),
[`tests/test_public_api_snapshot.py`](../../tests/test_public_api_snapshot.py),
the published [API reference](../../site/content/docs/reference/api.md), and the
[maintainability scorecard](maintainability-scorecard.md)

## Purpose

Kida's root namespace mixes the everyday rendering contract with advanced
integration primitives, build-time instrumentation, and a few convenience
exports whose long-term placement has not been decided. This inventory assigns
each current top-level export to exactly one disposition before 1.0. It is a
classification of the existing contract, not approval to remove, rename, or
change any export.

The categories mean:

- **stable core**: the normal application and framework-author path; preserve
  at the root through 1.0 barring a separately approved breaking change.
- **stable advanced**: a deliberate but specialized extension, analysis,
  sandbox, context, metadata, or diagnostic contract; preserve and document for
  callers that need it.
- **tooling/observability**: a deliberate build, capture, profiling, manifest,
  coverage, or worker-planning contract. It remains public, but is not required
  for ordinary rendering.
- **deprecated**: an export with a supported replacement and removal path.
  There are no exports in this category at this baseline.
- **internal-before-1.0**: a root-level convenience or implementation type that
  needs an explicit retain, relocate, deprecate, or remove decision before 1.0.
  This label does not remove the name from today's public snapshot.

## Classification

| Export | Category | Rationale |
|---|---|---|
| `AnalysisConfig` | stable advanced | Configures opt-in static analysis rather than ordinary rendering. |
| `AsyncLoopContext` | stable advanced | Documents the observable `loop` contract for async iterables. |
| `BlockMetadata` | stable advanced | Framework introspection consumes this immutable block contract. |
| `BlockModifierMetadata` | stable advanced | Frameworks consume typed literal block declarations and their source locations. |
| `ChoiceLoader` | stable core | Loader composition is a documented application setup path. |
| `CoercionWarning` | stable advanced | Callers can filter a specific documented compatibility warning. |
| `ComponentWarning` | stable advanced | Component users need a specific Python warning filter category. |
| `CoverageCollector` | tooling/observability | Collects template execution coverage for analysis and CI tooling. |
| `CoverageResult` | tooling/observability | Carries the immutable result of template coverage collection. |
| `DefMetadata` | stable advanced | Frameworks inspect component signatures and slots through this contract. |
| `DefParamInfo` | stable advanced | Describes component parameters inside the public metadata model. |
| `DictLoader` | stable core | In-memory templates are a documented setup and testing path. |
| `Environment` | stable core | This is the primary configuration, compilation, and loading entrypoint. |
| `ErrorCode` | stable core | Stable codes let applications handle diagnostics without parsing text. |
| `Extension` | stable advanced | Custom syntax and diagnostic extensions subclass this public base. |
| `FileSystemLoader` | stable core | Filesystem template loading is the primary production loader path. |
| `Fragment` | tooling/observability | Represents a captured render fragment for manifests and diff tooling. |
| `FreezeCache` | tooling/observability | Supports incremental build reuse from render-capture facts. |
| `FreezeCacheStats` | tooling/observability | Exposes freeze-cache effectiveness to build tooling. |
| `FunctionLoader` | stable core | Enables documented custom source resolution without a loader class. |
| `KidaWarning` | stable advanced | Provides the common warning category for host warning policy. |
| `LoopContext` | stable advanced | Documents the observable `loop` value made available to templates. |
| `ManifestDiff` | tooling/observability | Carries build-oriented differences between render manifests. |
| `Markup` | stable core | Safe-string semantics are central to the escaping contract. |
| `MigrationWarning` | stable advanced | Callers can filter the documented Jinja2 migration warning family. |
| `PackageLoader` | stable core | Loading templates from Python packages is a documented deployment path. |
| `PrecedenceWarning` | stable advanced | Callers can filter the documented expression-precedence warning. |
| `PrefixLoader` | stable core | Namespaced loader routing is a documented loader composition path. |
| `RenderAccumulator` | tooling/observability | Stores opt-in per-render profiling measurements. |
| `RenderCapture` | tooling/observability | Captures blocks, context, and fragment facts for build tooling. |
| `RenderContext` | stable advanced | Framework integrations use scoped per-render metadata and depth state. |
| `RenderManifest` | tooling/observability | Aggregates captured render facts for incremental and search builds. |
| `RenderedTemplate` | stable advanced | Provides the documented stream wrapper for rendered template output. |
| `SandboxPolicy` | stable advanced | Configures the documented defense-in-depth sandbox boundary. |
| `SandboxedEnvironment` | stable advanced | Provides the opt-in sandboxed rendering environment. |
| `SearchEntry` | tooling/observability | Defines the search-index record emitted from render captures. |
| `SearchManifestBuilder` | tooling/observability | Builds search records from a render manifest. |
| `SecurityError` | stable advanced | Lets sandbox callers distinguish policy violations from other failures. |
| `SourceSnippet` | stable advanced | Carries structured source context for application error presentation. |
| `Template` | stable core | This is the compiled template render and introspection object. |
| `TemplateError` | stable core | Applications depend on one catch-all Kida exception boundary. |
| `TemplateMetadata` | stable advanced | Frameworks consume immutable whole-template analysis facts. |
| `TemplateNotFoundError` | stable core | Loader failures need a specific documented exception contract. |
| `TemplateRuntimeError` | stable core | Render failures need a specific documented exception contract. |
| `TemplateStructureManifest` | stable advanced | Framework composition consumes lightweight structural metadata. |
| `TemplateSyntaxError` | stable core | Compilation failures need a specific documented exception contract. |
| `TemplateWarning` | stable advanced | Template compilation exposes structured warning records through this type. |
| `Token` | internal-before-1.0 | The lexer record shape is exported but has no supported root-level user workflow. |
| `TokenType` | stable advanced | Extension parsers use the token enum to consume custom tag syntax. |
| `UndefinedError` | stable core | Strict undefined access is a primary documented runtime failure. |
| `WorkerEnvironment` | internal-before-1.0 | This alias only disambiguates a worker heuristic enum from `Environment`. |
| `WorkloadProfile` | tooling/observability | Describes inputs to worker-count planning tools. |
| `WorkloadType` | tooling/observability | Classifies workloads for worker-count planning tools. |
| `__version__` | stable core | Standard package version introspection belongs at the package root. |
| `async_render_context` | stable advanced | Async integrations need the scoped render-context manager. |
| `build_source_snippet` | stable advanced | Framework error views can construct the public snippet model. |
| `captured_render` | tooling/observability | Activates render capture for build and diff tooling. |
| `default_field_extractor` | tooling/observability | Supplies the default render-capture to search-record adapter. |
| `get_accumulator` | tooling/observability | Custom instrumentation reads the active profiling accumulator. |
| `get_capture` | tooling/observability | Build hooks read the active render capture. |
| `get_optimal_workers` | tooling/observability | Computes a worker recommendation for deployment tooling. |
| `get_profile` | tooling/observability | Resolves the worker-planning profile for a workload. |
| `get_render_context` | stable advanced | Custom globals can inspect optional scoped render state. |
| `get_render_context_required` | stable advanced | Integration code can require scoped render state with a clear failure. |
| `html_escape` | stable core | This is the root escaping primitive behind safe HTML integration. |
| `is_free_threading_enabled` | tooling/observability | Reports runtime mode for deployment and worker planning. |
| `k` | stable core | This is the primary PEP 750 inline-template entrypoint. |
| `plain` | stable core | This is the documented non-escaping PEP 750 companion entrypoint. |
| `profiled_render` | tooling/observability | Activates opt-in profiling around a render. |
| `pure` | stable core | This decorator declares filters eligible for compile-time evaluation. |
| `render_context` | stable advanced | Frameworks establish scoped render metadata through this context manager. |
| `should_parallelize` | tooling/observability | Advises orchestration tooling whether a workload merits parallelism. |
| `strip_colors` | internal-before-1.0 | The generic terminal helper is root-exported without a root-level contract. |
| `timed_block` | tooling/observability | Adds custom spans to the active render profile. |

Category totals: 20 stable core, 28 stable advanced, 23
tooling/observability, 0 deprecated, and 3 internal-before-1.0; 74 exports total.

## Follow-up Gaps

The classification checkbox is complete, but it intentionally does not claim
that the separate "document and test every retained public export" checkbox is
complete.

- Issue #249 adds a cohesive published and checked workflow for `Fragment`,
  `FreezeCache`, `FreezeCacheStats`, `ManifestDiff`, `RenderCapture`,
  `RenderManifest`, `SearchEntry`, `SearchManifestBuilder`, `captured_render`,
  `default_field_extractor`, and `get_capture` without changing their contracts.
- The scorecard now finds two names absent from the README, published docs, and
  checked examples: `WorkerEnvironment` and `strip_colors`. `ComponentWarning`
  and `KidaWarning` have published hierarchy and filtering guidance plus focused
  behavior tests.
- `Token`, `WorkerEnvironment`, and `strip_colors` need public-contract review
  before 1.0. Any removal or relocation requires a separately approved
  deprecation path because all three remain in today's `kida.__all__` snapshot.
- No export is currently deprecated. Assigning that label later requires a
  supported replacement, user-visible guidance, tests, and changelog coverage.

Public submodules also carry documented advanced contracts without expanding
the root namespace. `kida.analysis.AdviceContext` and `AdviceFactValue` are
stable advanced adapter-analysis contracts: they are opt-in, immutable, and
covered by the reviewed adapter advice-context decision record. They remain
absent from `kida.__all__` intentionally.

## Proof And Collateral

`tests/test_public_api_classification.py` parses this table and compares it with
the literal root export list. It rejects missing, extra, duplicate, or unknown
classifications, closing the drift gap left by the count-only maintainability
scorecard and the export-only public API snapshot.

Issue #249 adds published API documentation, a checked runnable example, and
direct root-export coverage for the capture/manifest family. No collateral for
runtime code, `kida.__all__`, schemas, templates, CLI behavior, or changelog:
the workflow documents existing behavior without changing it. Benchmark and
free-threading evidence are not applicable because no hot path or shared-state
implementation changes.
