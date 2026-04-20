# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Parser error hints for Jinja2 traps** — When a template uses a Jinja2-only block keyword that Kida does not accept, the `K-PAR-001` ParseError now prepends a targeted suggestion before the generic "Valid keywords: …" list. Covers `macro` → `{% def %}`, `endmacro`/`endset` → unified `{% end %}`, `namespace` → `{% let %}`/`{% export %}`, and `fill`/`endfill` → `{% slot %}` inside `{% call %}`. The trap table lives in `kida.parser.errors.JINJA2_TRAPS` and is data-only — easy to extend as new traps surface.

### Fixed

- **Docs: `{% macro %}` false claim corrected** — `CLAUDE.md`, `docs/syntax/_index.md`, `docs/syntax/functions.md`, `docs/tutorials/migrate-from-jinja2.md`, `.cursor/skills/kida-jinja2-migration/SKILL.md`, and `releases/0.1.0.md` previously implied `{% macro %}` was a valid Kida keyword. It is not (attempts raise `K-PAR-001: Unknown block keyword: macro`). Docs now clearly state that `{% macro %}` must be renamed to `{% def %}` when migrating from Jinja2.

### Changed

- **`jinja2_compat_warnings` defaults to `True`** — `MigrationWarning` (K-WARN-002) now fires out of the box on the canonical Jinja2 `{% set %}` scoping trap (nested `{% set x %}` shadowing an outer `{% let x %}` or `{% export x %}`). The warning was previously silent unless users opted in. The trigger is **narrowly scoped** to the actual trap pattern — fresh names used for legitimate block-scoped work (e.g., loop-local counters) do not warn. Suppress via `Environment(jinja2_compat_warnings=False)` or `warnings.filterwarnings("ignore", category=MigrationWarning)`. Warning message now names the shadowed variable and the shadowing source (`{% let %}` or `{% export %}`) for actionable diagnostics.

## [0.6.0] - 2026-04-13

### Added

- **Component framework** — Def introspection API (`DefMetadata`, `DefParamInfo`, `list_defs`, `def_metadata`), component call stack in error reporting, `kida components` CLI command, type-aware prop validation with `TypeMismatch` diagnostics, Components Guide and Jinja2-vs-Kida comparison docs. (#90)
- **`kida readme` CLI** — Auto-generates README.md from project metadata (pyproject.toml, filesystem, git). Ships 4 preset templates (default, minimal, library, cli) with `--set` overrides and `--json` debug mode. (#89)

### Fixed

- **Sandbox `max_output_size` enforcement** — Was declared but never checked; now enforced. (#91)
- **Block capture rejection** — `{% set x %}...{% endset %}` block capture rejected at parse time. (#91)
- **Error codes for all SecurityError raises** — K-SEC-001 through K-SEC-005. (#91)
- **Autoescape validation at construction** — Invalid autoescape mode now rejected at `Environment()` creation, not first compile. (#91)
- **Structured errors** — All bare `RuntimeError` raises replaced with `TemplateRuntimeError`. (#91)
- **Optional chaining display** — `?.` now renders `""` instead of `"None"` in display context. (#91)
- **Broken `except` clauses** — Fixed 32 `except X, Y:` clauses (Python 2 syntax that only catches the first type). (#92)
- **`render_with_blocks()` validation** — Unknown block names now raise with did-you-mean suggestions. (#92)
- **Unknown compiler node types** — Now raises instead of silently ignoring. (#92)
- **CLI check error reporting** — Errors no longer swallowed silently. (#92)
- **`_Undefined.get()` API** — Fixed to match expected semantics. (#92)

### Changed

- **New warnings** — `PrecedenceWarning` (K-WARN-001) for `?? + |` without parens, `CoercionWarning` for silent filter type coercion, `MigrationWarning` (K-WARN-002) for `set` scoping with `jinja2_compat_warnings` flag. (#91)
- **`strict_undefined` mode** — Opt-in `Environment(strict_undefined=True)` for catching attribute typos. (#92)
- **`UndefinedError` context** — Attribute/key lookups now say "Undefined attribute/key" instead of "Undefined variable". (#92)
- **ErrorCode coverage** — Pushed from 21 to 73+ raise sites with full docs for all 38 ErrorCode values. (#91)

## [0.5.0] - 2026-04-12

### Added

- **`tojson` attribute mode** — `{{ value | tojson(attr=true) }}` HTML-entity-encodes JSON for safe use in double-quoted HTML attributes (e.g. Alpine `x-data`). Default `tojson` behavior is unchanged for `<script>` tags and JSON-in-script contexts.
- **`plain()` t-string tag** — New `plain(t"...")` tag for t-string inline templates that renders without HTML escaping.
- **Kida × Milo integration** — Saga benchmarks, terminal tutorial, and vision rewrite for the Milo integration layer.
- **GitHub App token support** — Branded PR comments now support GitHub App tokens for authentication. (#83)

### Fixed

- **Partial evaluator preserves loop var bindings** — Unrolled `for`-loops no longer lose loop variable bindings when the partial evaluator inlines the loop body. (#78, #79)

### Changed

- **Performance** — Cache `str.join` as local variable and enable built-in pure filter folding for faster template compilation. (#80)
- **Dispatch-dict compiler refactor** — Expression compilation in `_compile_expr` now uses a dispatch dictionary instead of if/elif chains. (#87)
- **Documentation audit** — Comprehensive accuracy, IA, and completeness pass across all docs. (#86)
- **CI dependency bumps** — Updated `actions/upload-artifact` to v7, `actions/setup-python` to v6, and `actions/download-artifact` to v8.

## [0.4.1] - 2026-04-10

### Fixed

- Partial evaluator now folds all types from `static_context`, including dicts, lists, and custom objects. Non-constant-safe types that Python's `compile()` rejects in `ast.Constant` nodes are emitted as precomputed module-level bindings (`_pc_N`), injected into the exec namespace at template load time. (`#68`)
- Scoped slot `let:` bindings now work correctly when the binding variable is referenced more than once in the slot body. The CSE (common subexpression elimination) optimisation previously hoisted the variable lookup to function entry — before `_slot_kwargs` were pushed onto the scope stack — causing `UndefinedError`. Slot bodies are now excluded from eager caching. (`#70`)

## [0.4.0] - 2026-04-10

### Added

- **List comprehensions** — `[expr for var in iterable if condition]` in template expressions with full parser, compiler, dependency tracking, and purity analysis integration. (#62)
- **Error boundaries** — `{% try %}...{% fallback %}...{% end %}` catches rendering errors and substitutes fallback content without aborting the page. Supports error binding, nesting, and streaming. (#61)
- **Scoped slots** — `{% slot let:name=expr %}` exposes data from components back to callers via `let:` bindings on `{% call %}`. (#61)
- **`{% trans %}` / `{% pluralize %}` blocks** — Internationalization with variable interpolation, plural forms, and automatic escaping. (#61)
- **Babel message extraction** — `kida.babel.extract` entry point for `pybabel extract` compatibility. (#63)
- **`kida i18n` CLI** — `kida i18n extract` and `kida i18n analyze` commands for standalone message extraction and translation coverage analysis. (#63)
- **i18n analysis module** — Tracks translatable strings, detects missing translations, integrates with dependency and purity analyzers. (#63)
- **Partial evaluator phase 1** — Constant folding, filter inlining for pure built-in filters, assignment propagation, static loop unrolling, literal evaluation, and boolean short-circuit simplification. Opt-in via `Environment(partial_eval=True)`. (#64)
- **Partial evaluator phase 2** — Extends optimization to conditional expressions, nested structures, string operations, comprehension folding, and cross-block constant propagation. (#65)
- **`kida compile --optimize` CLI** — Inspect the optimized AST with before/after comparisons. (#64, #65)
- **`@pure` decorator** — Mark custom filters for compile-time evaluation when inputs are static. (#64)

### Changed

- **Performance docs** — Updated to cover partial evaluation strategies and benchmarks.
- **Compiler docs** — New sections on the optimization pipeline and `@pure` decorator.
- **Configuration docs** — Documents `partial_eval` and related environment options.
- **Custom filters docs** — Added `@pure` decorator usage and compile-time evaluation guide.

## [0.3.4] - 2026-04-09

### Added

- **`provide`/`consume` render context** — `{% provide key = expr %}` / `consume("key")` primitive for parent-to-child component state flow across slot boundaries. Stack-based nesting with `try/finally` cleanup.
- **Agentic comment templates** — GitHub Action now supports agentic comment templates with release notes rendering across multiple surfaces.
- **Release notes action** — Multi-surface rendering and rich data collection for automated release notes generation.
- **AMP protocol documentation** — Agent template site documentation for the AMP protocol.

### Fixed

- **Markup-aware `~` operator** — `code(x) ~ " " ~ copy_button(x)` no longer double-escapes HTML. Also fixes the `+` operator's string concatenation branch.
- **GitHub Action description** — Shortened `action.yml` description to meet GitHub's 125-character limit.

### Changed

- **README** — Slimmed down README, promoted Render Anywhere as hero section.

## [0.3.3] - 2026-04-07

### Added

- **`syntax()` terminal filter** — Regex-based JSON and YAML syntax highlighting for terminal rendering mode.
- **PR comment support in GitHub Action** — CI reports can now be posted as pull request comments in addition to step summaries. Includes comment deduplication via `comment-header`, `comment-mode: append` for combining multiple reports into one comment, and extra template variables via the `context` input.

### Fixed

- **`CachedBlocksDict` miss tracking** — Fixed cache miss tracking so block lookups that miss are properly recorded; expanded test coverage for cached blocks, purity checks, and t-strings.

## [0.3.2] - 2026-04-03

### Added

- **`kida explain` CLI** — `kida explain <template>` prints which compile-time optimizations are active (f-string coalescing, dead code elimination, partial evaluation, component inlining, free-threading status).
- **`kida bench` CLI** — Quick benchmarking command for template compile and render performance.
- **Expanded partial evaluator** — Handles `Def`, `FuncCall`, `MarkSafe`, `NullCoalesce`, `OptionalFilter`, `SafePipeline`, `Slot`, and `SlotBlock` nodes for deeper compile-time optimization.
- **Partial eval benchmarks** — Dedicated benchmark suite for measuring partial evaluation speedups.
- **Terminal benchmarks** — Dedicated benchmark suite for terminal rendering mode.
- **Kida vs Jinja2 comparison** — Side-by-side comparison document covering syntax, architecture, performance, and feature differences.

### Changed

- **Python 3.14 modernization** — `@final` decorators on key classes; `match` statements replace `if`/`elif` chains throughout the partial evaluator and constant evaluator; stricter ruff linting rules.
- **Consolidated AST traversals** — Dependency analysis merged redundant walks into a single-pass visitor, reducing compile-time overhead.
- **Cached AST in bytecode cache** — Bytecode cache now stores parsed AST alongside compiled code for faster recompilation.
- **Render helper consolidation** — Deduplicated common patterns in `render_helpers.py` and `render_context.py`.
- **README rewrite** — Concise, feature-focused README with architecture overview and benchmark highlights.
- **Import path cleanup** — `TemplateSyntaxError` imported from `kida.exceptions` instead of `kida.environment.exceptions`.

### Removed

- **`analysis/visitor.py`** — Redundant visitor module consolidated into `analysis/node_visitor.py`.

## [0.3.1] - 2026-04-02

### Added

- **Safe pipeline (`?|>`)** — None-propagating filter chain. If the value is None, all subsequent filters are skipped instead of erroring: `{{ user?.name ?|> upper ?|> trim ?? "Anonymous" }}`.
- **Optional filter (`?|`)** — Skip a single filter when the value is None: `{{ value ?| upper ?? "N/A" }}`. Unlike `| default("") | filter`, preserves falsy values like `0` and `""`.
- **Nullish assignment (`??=`)** — Assign only if the variable is undefined or None. Works with `let`, `set`, `export`, and `promote`: `{% let title ??= "Untitled" %}`.
- **`promote` keyword** — Alias for `export`. Reads more naturally for scope promotion: `{% promote result = value %}`.
- **Markdown rendering mode** — `autoescape="markdown"` with markdown-safe escaping and CI report filters.
- **GitHub Action** — `lbliii/kida@v0.3.1` renders CI reports (pytest, coverage, ruff, ty, jest, gotest, SARIF) as step summaries or PR comments.
- **SARIF parser** — Parse SARIF static analysis output for template rendering.
- **LCOV parser** — Parse LCOV coverage data for template rendering.
- **JUnit XML parser** — Parse JUnit XML test results for template rendering.
- **Built-in CI report templates** — `pytest`, `coverage`, `ruff`, `ty`, `jest`, `gotest`, `sarif` templates with snapshot tests.

### Changed

- **Jinja2 migration docs** — Documented sharp edges and behavioral differences for migrators.
- **Benchmark regression gate** — Excluded Jinja2 tests from benchmark regression checks (CI noise).

## [0.3.0] - 2026-03-26

### Added

- **Terminal rendering mode** — `Environment(autoescape="terminal")` activates declarative terminal/CLI output. Includes ANSI-safe escaping, 30+ terminal filters (colors, badges, tables, trees, diffs), icon/box-drawing character sets with Unicode/ASCII degradation, reusable built-in components (panel, header, footer, rule, connector, row, cols), and TTY/NO_COLOR-aware graceful fallbacks.
- **S-tier terminal enhancements** — Configurable character width (`WidthStrategy`) with terminal probe auto-detection and wcwidth support; VS15 text presentation selectors; `fg()`/`bg()` color depth fallback (truecolor → 256 → basic → none); `LiveRenderer` for in-place terminal re-rendering with `Spinner` animation; `stream_to_terminal()` for progressive chunk-by-chunk output; responsive `stack()` component (side-by-side when wide, stacked when narrow).
- **`kida render` CLI** — `kida render template.txt --data context.json [--stream]` for rendering templates from the command line.
- **Framework integrations** — `kida.contrib.flask`, `kida.contrib.starlette`, and `kida.contrib.django` adapter modules for Flask, Starlette/FastAPI, and Django.
- **`SandboxedEnvironment`** — Configurable security policies with read-only collection method restrictions, call-time safety checking, and `allow_mutating_methods` / `allow_calling` allowlists.
- **Template coverage collector** — `CoverageCollector` tracks which template lines execute during rendering, with LCOV and Cobertura output formats.
- **Accessibility linting** — `a11y.py` checks for `img-alt`, `heading-order`, `html-lang`, and `input-label` violations.
- **Template type checker** — `{% template %}` declarations for annotating expected context types with compile-time validation.
- **Template formatter** — `kida fmt` opinionated template formatter with configurable blank line and indentation rules.
- **Extension/plugin architecture** — `Extension` base class with `node_types` registration, `_extension_compilers` dispatch, and `_extension_end_keywords` for custom tags.
- **Content stacks/portals** — `{% push %}` / `{% stack %}` tags for collecting and rendering content from nested templates (CSS/JS aggregation).
- **CSP nonce support** — `inject_csp_nonce()` and `csp_nonce_filter` for inline script/style Content Security Policy compliance.
- **`StreamTransform`** — Progressive rendering transform for streaming template output.
- **Unified `NodeVisitor`/`NodeTransformer`** — MRO-aware dispatch cache for AST traversal.
- **Terminal examples** — 8 new examples: `terminal_basic`, `terminal_dashboard`, `terminal_table`, `terminal_deploy`, `terminal_gitlog`, `terminal_layout`, `terminal_live`, `terminal_monitor`, `terminal_render`, `terminal_report`.

### Changed

- **Immutable AST** — Frozen-dataclass AST nodes with structural equality.
- **Free-threading safe `RenderContext`** — No shared mutable state; `__setattr__` override removed from hot path (was causing 22–49% benchmark regression).
- **Custom exception hierarchy** — `kida.exceptions` module with source-context-aware error classes, extracted from `environment.exceptions`.
- **Constant folding** — Compiler partial evaluator folds constant expressions at compile time.
- **Output coalescing** — Adjacent string concatenations merged in compiled output.
- **Compiler pipeline optimizations** — Copy-on-write AST transformer replaces `deepcopy` in `sync_body_to_stream`; class-level dispatch table hoisted from per-instance bound methods; `_block_has_append_rebind` flag replaces post-hoc `ast.walk` scans.
- **Parser validation** — Raises `ParseError` on multiple `{% template %}` declarations.
- **Extension compiler dispatch** — `_extension_compilers` dict lookup replaces try/except iteration.

## [0.2.9] - 2026-03-23

### Added

- **`kida check` CLI** — `kida check <dir>` loads and parses every `*.html` template under a directory (syntax plus loader resolution). Optional `--strict` flags unified `{% end %}` closers with suggestions for explicit `{% endblock %}`, `{% enddef %}`, etc. Optional `--validate-calls` checks macro call sites against defs via `BlockAnalyzer` (unknown params, missing required, duplicates).
- **Parser unified-end tracking** — Parser records unified `{% end %}` closures for strict-mode diagnostics.

### Changed

- **`render_block()` ancestor macro imports** — Block-only renders resolve macro imports from ancestor templates consistently with full-template loads.
- **Globals setup** — Reuses the cached inheritance chain instead of rebuilding it.
- **Compiler traversal reductions** — Fewer redundant AST walks during f-string coalescing and post-compile validation; consolidated `saved_blocks` iteration; `_analyze_for_cse` deduplicates CSE analysis call sites.
- **Benchmark matrix** — `benchmarks/RESULTS.md` refreshed for Python 3.14t free-threading.

### Documentation

- End-tag guidance for unified `{% end %}` versus explicit block closers.

## [0.2.8] - 2026-03-18

### Added

- **`{% yield %}` directive** — Context-independent slot rendering for nested `{% def %}` / `{% call %}` chains. `{% yield %}` renders the caller's default slot; `{% yield name %}` renders a named slot. Replaces the fragile `{% slot x %}{% slot x %}{% end %}` double-nesting workaround with clear, unambiguous syntax.
- **Region default expressions** — Optional region parameters now support arbitrary expressions as defaults (e.g. `meta=page.metadata`, `count=items | length`, `title=page?.title ?? "Default"`). Previously only simple variable names worked; complex expressions leaked an internal sentinel. Defaults are evaluated at call time from the caller's context. Static analysis (`depends_on`) correctly captures paths from complex defaults.
- **Region `_blocks` parameter** — Region callables now receive the block dispatch dict, enabling regions to render inherited blocks within `render_block()` flows.
- **Imported macro namespace injection** — `MacroWrapper` now injects the defining template's namespace so imported macros can call sibling macros (e.g. `article_card` calling `tag_list` from the same import) without the caller importing every dependency.
- **Regions example** — New `examples/regions/` with a working app, templates, and test suite demonstrating parameterized region blocks.

### Changed

- **mtime-based `auto_reload` stale checks** — `get_template()` now checks file mtime (`st_mtime_ns`) before reading and hashing source. Skips the slow hash-comparison path when the file hasn't been modified, reducing per-call overhead for `auto_reload=True` environments.
- **Pre-computed block wrappers** — `CachedBlocksDict` builds wrapper functions once at init instead of creating a new closure on every `.get()`, `.setdefault()`, or `[]` access.
- **Single-pass context merge** — `_build_render_context` uses `{**globals, **args, **kwargs}` dict unpacking instead of filtering `UNDEFINED` values and calling `.update()` multiple times.
- **`lookup_scope` fast path** — Skips the `reversed()` iterator when `scope_stack` is empty (the common case at template top level).
- **Single-pass tag counting** — `estimate_template_weight` scans template source once instead of four separate `str.count()` calls.
- **Compiler node dispatch table** — Built once at `__init__` instead of being reconstructed per compilation pass.

## [0.2.7] - 2026-03-12

### Added

- **`typeof` filter** — Returns stable type names for common template values: `bool`, `int`, `float`, `path`, `list`, `dict`, `none`, and `str`. Useful for debugging mixed YAML/config inputs in templates.
- **Macro collision diagnostics** — Imported macros now raise a targeted error when used as iterables, helping diagnose macro/context variable name collisions like `route_tabs` vs `render_route_tabs`.

### Changed

- **Template error handling improvements** — `pluralize` now raises on non-numeric input; `replace` coerces `count` from YAML/config strings and raises on invalid coercion; `decimal` and `format_number` support `strict=True`; runtime error enhancement adds clearer suggestions for macro iteration, date/strftime, invalid numeric literals, and sequence-only filters.
- **`join` and `reverse` filters (breaking)** — No longer fall back to `str(value)` or `str(value)[::-1]` on non-iterable input. `42 | join(", ")` and `42 | reverse` now raise `TypeError` instead of returning `"42"` or `"24"`. Use `list(value) | reverse` or ensure iterable input for `join`.

### Fixed

- **Nested slot passthrough** — Empty or whitespace-only slot bodies now delegate correctly to the outer caller in nested `{% def %}` / `{% call %}` / `{% slot %}` chains, fixing layout/component passthrough patterns.

## [0.2.6] - 2026-03-09

### Added

- **`{% region %}` blocks** — Parameterized blocks that work as both blocks (for `render_block()`) and callables (for `{{ name(args) }}`). Use when you need parameterized fragments for HTMX partials, OOB updates, or layout composition. Regions support required and optional params, default values, and access to outer render context.
- **Region metadata** — `BlockMetadata` now includes `is_region` and `region_params`. `TemplateMetadata.regions()` returns only region-typed blocks for framework OOB discovery (e.g. Chirp's AST-driven layout contracts).
- **Functions reference docs** — New syntax page documenting `{% def %}`, `{% region %}`, parameters, typed params, slots, `caller()`, `has_slot()`, and the regions vs defs comparison.
- **render_block and def scope troubleshooting** — New guide explaining the historical limitation where blocks could not inherit defs from the same template, how 0.2.6 lets blocks call top-level defs, and when to still split defs into imports or use regions for shared logic.
- **Framework integration docs** — Expanded guide with Chirp + Regions step-by-step, adapter pattern, and case studies for Bengal, Chirp, and Dori.
- **Doc tracks** — Learning tracks for Chirp+Kida, framework integration, and Jinja2 migration.
- **Render block tests** — Test suite for `render_block()` contract (Chirp fragment dependency), inheritance, regions, and slot context inheritance.

### Changed

- **Top-level defs and regions in globals setup** — Defs and regions at template top-level are now compiled into `_globals_setup`, so `render_block()` has access to macros and region callables. Fixes `NameError` when blocks call defs defined in the same template.
- **Compiler preamble refactor** — `_make_runtime_preamble()` centralizes shared runtime locals (scope stack, escape/str, buf/append, acc). `_make_block_preamble()` and `_make_render_preamble()` delegate to it.
- **Block/region name collision** — Compiler rejects duplicate block and region names with `TemplateSyntaxError`.

### Fixed

- **render_block def scope** — Blocks can now call defs from the same template when defs are top-level; previously `render_block("content")` would fail with `NameError` if the block used `{{ helper() }}` and `helper` was a def in the same file.

## [0.2.5] - 2026-03-07

### Added

- **Filter modularization** — Built-in filters split into category submodules (`_collections`, `_debug`, `_html_security`, `_misc`, `_numbers`, `_string`, `_type_conversion`, `_validation`). `_impl.py` is now a registry aggregating implementations. Improves maintainability and discoverability.
- **Tests reference docs** — New reference page documenting all built-in tests (`defined`, `undefined`, `string`, `number`, `mapping`, `iterable`, comparison tests, HTMX tests, etc.).
- **Configuration reference docs** — Expanded documentation for all `Environment` options (loader, autoescape, bytecode_cache, etc.).
- **Benchmark dimensions** — New benchmark suites: static_context vs dynamic render, bytecode cache disk load, introspection (template_metadata, list_blocks, get_template_structure, render_block). `benchmark_compare.sh` integrated into release gate.
- **Render output regression guards** — Test suite for non-empty render, loop count parity, include chain counts, inheritance block deduplication, stream vs render parity. Run as release regression gate before PyPI publish.
- **PyPI publish workflow** — `.github/workflows/python-publish.yml` triggers on release publish; runs regression gate (expression tests, output guards, benchmark compare) before building and uploading to PyPI.

### Changed

- **`render_block()` performance** — Lock removed from cache-hit path in `_effective_block_map` and `_inheritance_chain`. Cache-hit path reads without lock; double-check inside lock on miss. ~2µs per call improvement.
- **Polymorphic `+` operator** — `add_polymorphic()` now preserves Python semantics for compatible types (`list + list`, `tuple + tuple`). Avoids silently stringifying collection arithmetic, which could explode template output. String concatenation fallback still applies when one operand is string-like.
- **Template inheritance refactor** — `TemplateInheritanceMixin` extracted to `template/inheritance.py` with cached inheritance chain and effective block maps. `_build_local_block_maps()` precomputes block function maps at load time.
- **Error enhancement extraction** — `enhance_template_error()` moved to pure function in `template/error_enhancement.py`. Converts generic exceptions to `TemplateRuntimeError` with template name, line, and source snippet. Handles `NoneComparisonError` specially.
- **Attribute helpers extraction** — `safe_getattr()` and `getattr_preserve_none()` moved from `Template` to `template/helpers.py` for reuse. `html_escape` passed via render helpers instead of instance method.

### Fixed

- **Inherited block benchmark regression** — Lock acquisition on cache-hit path was adding ~2µs per `render_block()` call; fixed by lock-free read path with double-check on miss.

## [0.2.4] - 2026-03-06

### Added

- **Composition API** — `kida.composition` module with `validate_block_exists()`, `validate_template_block()`, and `get_structure()` for frameworks (Chirp, Dori) that compose templates via block rendering. `TemplateStructureManifest` exposes block names, extends parent, and dependencies.
- **Inherited block support** — `render_block()` and `list_blocks()` now include blocks inherited from parent templates. Child templates can render parent-only blocks (e.g. `render_block("sidebar")` on a descendant).
- **Slot context inheritance** — Lexical caller scoping for nested `{% def %}` / `{% call %}` / `{% slot %}` chains. `caller()` in slot bodies inside defs now correctly resolves to the def's caller, enabling layout chains (Dori/chirpui).
- **String concatenation** — Polymorphic `+` operator: numeric add when both operands are numeric, otherwise string concatenation. `{{ "Hello" + " " + name }}` and `{{ 1 + 2 }}` both work as expected.
- **String escape decoding** — Lexer decodes Python-style escape sequences in string literals: `\n`, `\t`, `\r`, `\\`, `\'`, `\"`, `\uXXXX`, `\UXXXXXXXX`.
- **Parser error codes** — `ParseError` now carries `ErrorCode` (e.g. `UNEXPECTED_TOKEN`, `UNCLOSED_BLOCK`, `INVALID_IDENTIFIER`) with docs URLs. `TokenType.display_name` provides human-readable names for error messages.
- **Block/fragment hyphen detection** — Parser rejects `{% block foo-bar %}` and `{% fragment foo-bar %}` with a suggestion to use underscores.
- **Framework integration docs** — New guide for block rendering, introspection, and composition APIs (Chirp, Bengal, Dori).
- **`strip_colors` export** — Restored colored exception output; `strip_colors()` available from `kida` for log-friendly output.

### Changed

- **Async API contract clarified** — `Template.render_async()` is now explicitly a thread-pool wrapper for synchronous templates. Async templates should use `render_stream_async()`.
- **Fragment cache TTL semantics** — `{% cache key, ttl=... %}` now enforces per-fragment TTL overrides (supports numeric seconds and `s/m/h/d` duration suffixes).

### Fixed

- **Bytecode cache write race** — `BytecodeCache.set()` now uses unique temp files plus atomic `os.replace()`, preventing concurrent writer collisions on shared `.tmp` paths.

## [0.2.3] - 2026-03-03

### Added

- **`{% flush %}` directive** — Emits a streaming boundary so buffered output is yielded immediately. Use for chunked HTTP and SSE to control when data reaches the client.
- **Resource exhaustion guards** — `max_extends_depth` (50) limits inheritance chains; partial evaluator depth limit (100) prevents stack overflow on deep attribute chains; `MAX_FILTER_CHAIN_LEN` (200) caps filter/pipeline length. Circular inheritance detection raises `TemplateRuntimeError`.
- **Encoding edge case tests** — BOM, NUL bytes, surrogates, invalid UTF-8, Latin-1 in template source and `FileSystemLoader`.
- **Concurrency tests** — BytecodeCache get/set, mixed `render()`/`render_stream()` on same template.
- **Property tests** — Parser and E2E Hypothesis fuzz; never crashes on arbitrary input.
- **Scaling benchmarks** — Inheritance depth, filter chains, `add_filter` vs `update_filters`, partial eval, template cache contention. See `benchmarks/RESULTS.md` for Kida vs Jinja2 matrix.
- **Coverage threshold** — `fail_under=80` in pyproject.toml.
- **Hypothesis CI profile** — `max_examples=200` when `CI=true`.
- **Def/slot name validation** — Compiler validates `{% def %}` and `{% slot %}` names with identifier regex; rejects invalid names at compile time.

### Changed

- **Thread-safety CI** — Now runs `test_bytecode_cache_concurrency.py` in addition to stress and LRU tests.
- **UNDEFINED in globals** — Render context filters `UNDEFINED` from `env.globals` before macro imports; prevents accidental exposure to templates. Documented in `custom-globals.md`.
- **Error attribution** — Improved source mapping and DX for template errors.

### Fixed

- **K-RUN-007** — Isolate `import_stack` and exclude `UNDEFINED` in macro imports; fixes shared mutable state in concurrent rendering.

### Security

- **Path traversal** — `BytecodeCache` rejects template names containing path traversal (`..`, path separators). `PackageLoader.get_source` rejects path traversal in template names.

## [0.2.2] - 2026-02-18

### Added

- **Named slots in `{% call %}` blocks** — `{% call %}` now supports per-slot
  content blocks with `{% slot name %}...{% end %}`, mapped to matching
  placeholders in `{% def %}`. Default-slot behavior remains backward-compatible.

### Changed

- **`caller()` slot dispatch** — call wrappers now support both `caller()` for the
  default slot and `caller("slot_name")` for named slot content, enabling
  multi-region component APIs.

- **Slot-aware analysis and transforms** — static analysis visitors and partial
  evaluation now traverse slot bodies inside `CallBlock`, so slot-contained calls
  and expressions are included in validation and optimization passes.

### Fixed

- **Circular macro import detection (`K-TPL-003`)** — `{% from "x" import y %}`
  now detects direct and transitive self-import cycles and raises
  `TemplateRuntimeError` with a deterministic error code instead of recursing
  until failure.

## [0.2.1] - 2026-02-14

### Added

- **Dead code elimination** — Const-only pass removes branches whose conditions are
  provably constant (e.g. `{% if false %}...{% end %}`, `{% if 1+1==2 %}...{% end %}`).
  Runs without `static_context`. Skips inlining when the body contains block-scoped nodes
  (Set, Let, Capture, Export) to preserve scoping semantics.

- **Filter/Pipeline partial evaluation** — When `static_context` is provided, the
  partial evaluator now evaluates Filter and Pipeline nodes for pure filters
  (e.g. `{{ site.title | default("Home") }}`, `{{ site.title | upper }}`). Uses
  built-in pure filters plus `Environment.pure_filters`.

## [0.2.0] - 2026-02-13

### Added

- **Streaming rendering** — `template.render_stream(**ctx)` yields template output as string chunks via Python generators. The compiler generates both StringBuilder (`render()`) and generator (`render_stream()`) functions from each template in a single compilation pass. Supports full template inheritance (`{% extends %}`, `{% block %}`), includes, and all control flow. Buffering blocks (`{% capture %}`, `{% spaceless %}`, `{% cache %}`, `{% filter %}`) buffer internally and yield the processed result. No performance impact on `render()` — the existing StringBuilder path is unchanged.

- **Native async streaming** — `template.render_stream_async(**ctx)` yields template output as string chunks via async generators. Supports native `{% async for %}` loops over async iterables, `{{ await expr }}` for inline coroutine resolution, and `{% empty %}` fallback clauses. All templates generate async streaming variants, enabling async child templates to extend sync parents seamlessly.

- **`AsyncLoopContext`** — Loop variable (`loop`) for `{% async for %}`. Provides index-forward properties (`index`, `index0`, `first`, `previtem`, `cycle()`). Size-dependent properties (`last`, `length`, `revindex`) raise `TemplateRuntimeError` since async iterables have no known length.

- **`render_block_stream_async(block_name, **ctx)`** — Render a single block as an async stream. Falls back to wrapping the sync block stream when no async variant exists.

- **`RenderedTemplate`** — Lazy iterable wrapper around `render_stream()`. Construct with a template and context dict, iterate to get chunks on demand.

  ```python
  from kida import RenderedTemplate

  rendered = RenderedTemplate(template, {"items": data})
  for chunk in rendered:
      send_to_client(chunk)
  ```

- **`Template.is_async`** — Boolean property indicating whether a template contains `{% async for %}` or `{{ await }}` constructs. `render()` and `render_stream()` raise `TemplateRuntimeError` when called on async templates.

- **`async_render_context()`** — Async context manager for per-render state isolation, matching the sync `render_context()` API.

- **Compiler-emitted profiling instrumentation** — `profiled_render()` now automatically tracks blocks (with timing), filters (call counts), and macros (call counts) without manual instrumentation. The compiler emits `_acc = _get_accumulator()` once per function and gates all recording behind a falsy check, so zero overhead when profiling is disabled.

- **Include scope propagation** — Loop variables from `{% for %}` and block-scoped `{% set %}` variables are now visible inside `{% include %}` templates. The compiler merges scope-stack and loop locals into a context copy at include call sites.

- **Bytecode cache warning** — `from_string()` without `name=` now emits a `UserWarning` when a `bytecode_cache` is configured, explaining how to enable caching.

- **ChoiceLoader** — Try multiple loaders in order, returning the first match. Enables theme fallback patterns where a custom theme overrides a subset of templates and the default theme provides the rest.

- **PrefixLoader** — Namespace templates by prefix, delegating to per-prefix loaders. Enables plugin architectures where different template sources are isolated by namespace.

- **PackageLoader** — Load templates from installed Python packages via `importlib.resources`. Enables pip-installable themes, plugins, and framework default templates without path resolution.

- **FunctionLoader** — Wrap any callable as a template loader. Returns `str`, `(str, filename)`, or `None`. Simplest way to create a custom loading strategy.

- **Static analysis API** — `validate_context()` for pre-render variable checking, plus `AnalysisConfig`, `BlockMetadata`, and `TemplateMetadata` exposed as lazy-loaded public surface from `kida`.

- **`*args` and `**kwargs` support in `{% def %}`** — Template-defined functions now accept variadic positional and keyword arguments.

- **Better error messages** — `UndefinedError` now suggests similar variable names via fuzzy matching. `TemplateSyntaxError` includes source snippets with line context. `DictLoader` suggests similar template names on miss. Bare `RuntimeError`s include template name and line context.

- **Typed `{% def %}` parameters** — Function parameters now accept optional type annotations
  following Python syntax: `{% def card(title: str, items: list, style: str | None = none) %}`.
  Annotations support simple types, unions (`str | None`), and generics (`dict[str, int]`).
  A new `DefParam` AST node carries name and annotation. The compiler propagates annotations
  into generated Python AST for IDE support. Enable `validate_calls=True` on the Environment
  to get compile-time warnings for unknown params, missing required args, and other call-site
  mismatches. Backward-compatible — the `Def.args` property still returns parameter names.

- **`_Undefined` sentinel** — Missing attribute access now returns an `_Undefined` sentinel
  instead of an empty string. `_Undefined` is falsy, stringifies to `""`, and is iterable
  (yields nothing), so existing templates are unaffected. The key improvement: `is defined`
  and `is undefined` tests now work correctly on attribute chains
  (e.g. `{% if pokemon.name is defined %}`).

- **Conditional blocks** — `{% block name if condition %}` skips the block body when the
  condition is falsy. Works with template inheritance — child blocks can override both
  content and condition.

- **`classes` filter** — Joins a list of CSS class names, dropping falsy values. Flattens
  nested lists. Ideal for conditional class composition:
  `{{ ["btn", "active" if is_active, ""] | classes }}` → `btn active`.

- **`decimal` filter** — Formats a number to a fixed number of decimal places:
  `{{ 3.14159 | decimal(2) }}` → `3.14`. Non-numeric values pass through unchanged.

- **`has_slot()` in `{% def %}`** — Inside a `{% def %}` body, `has_slot()` returns `true`
  when the function is invoked via `{% call %}` (i.e. slot content was provided) and `false`
  for direct calls. Enables components to adapt their markup based on slot presence.

- **Error codes** — Every exception now carries an `ErrorCode` enum (`K-LEX-*`, `K-PAR-*`,
  `K-RUN-*`, `K-TPL-*`) that categorizes the error and links to documentation. Access via
  `exc.code` and `exc.code.value`.

- **`format_compact()`** — All `TemplateError` subclasses provide a structured, human-readable
  summary including error code, source snippet, hint, and docs link. Recommended for frameworks
  and logging integrations.

- **Source snippets** — `TemplateRuntimeError` and `UndefinedError` now carry a `source_snippet`
  attribute (`SourceSnippet` dataclass) with the relevant source lines and error pointer.
  `build_source_snippet()` is available for manual snippet construction.

- **Public API exports** — `TemplateRuntimeError`, `ErrorCode`, `SourceSnippet`, and
  `build_source_snippet` are now exported from the top-level `kida` package.

- **Compile-time partial evaluation** — `PartialEvaluator` transforms template ASTs by
  evaluating expressions whose values are known at compile time (e.g. `{{ site.title }}`
  when the Site object is available). Static expressions become `Data` nodes (literal
  strings in bytecode), enabling more aggressive f-string coalescing and eliminating
  per-render dictionary lookups for site-wide constants. The evaluator is conservative —
  any expression it cannot prove static is left unchanged.

- **Block-level recompilation** — `detect_block_changes()` compares two `TemplateNode`
  ASTs and produces a `BlockDelta` describing which named blocks changed, were added, or
  were removed. `recompile_blocks()` patches a live `Template` object by recompiling only
  the affected block functions (standard, streaming, async streaming) without recompiling
  the entire template. Used by Purr's reactive pipeline for O(changed_blocks) updates.

### Changed

- **Dict-safe attribute resolution** — `_safe_getattr` now tries subscript before `getattr` for dict objects. `{{ section.items }}` resolves to `section["items"]` (user data), not the `dict.items` method. Non-dict objects retain the previous `getattr`-first behavior. This prevents dict method names (`items`, `keys`, `values`, `get`, `pop`, `update`) from shadowing user data keys.

- **Lazy analysis imports** — `AnalysisConfig`, `BlockMetadata`, and `TemplateMetadata` are now lazy-loaded via `__getattr__`, avoiding eager import of `kida.nodes` (974 lines of frozen dataclass AST definitions). Results in **48% faster cold-start** for `from kida import Environment`.

- **Compiler mixin extraction** — `CachingMixin`, `WithBlockMixin`, and `PatternMatchingMixin` extracted from monolithic compiler modules, improving maintainability and readability.

- **`template.py` split into `template/` package** — The 1,277-line `template.py` module has been split into focused submodules: `core.py`, `helpers.py`, `introspection.py`, `loop_context.py`, and `cached_blocks.py`.

- **Narrowed type annotations** — Broad `Node` type annotations replaced with specific subclasses throughout `DependencyWalker` and `PurityAnalyzer` visitor methods. `Any` types tightened in template and compiler modules. Broad exception handlers narrowed.

- **CI: replaced mypy with ty** — All type checking now uses Astral's Rust-based `ty` type checker. Fixed all 41 ruff lint errors across the codebase.

- **Sorted `__all__`** — Public API exports in `kida/__init__.py` are now alphabetically sorted for discoverability.

## [0.1.2] - 2026-01-13

### Added

- **RenderContext** — ContextVar-based per-render state management. Isolates internal state (`_template`, `_line`, `_include_depth`, `_cached_blocks`) from user context. User `ctx` dicts are now clean with no internal key pollution. Thread-safe and async-safe via Python 3.14 ContextVar propagation.

- **RenderAccumulator** — opt-in profiling for template rendering. Collects block render times, macro call counts, include/embed counts, and filter usage. Zero overhead when disabled.

  ```python
  from kida import profiled_render

  with profiled_render() as metrics:
      html = template.render(page=page)

  print(metrics.summary())
  # {"total_ms": 12.5, "blocks": {"content": {"ms": 8.2, "calls": 1}}, ...}
  ```

- **Public API exports** — `RenderContext`, `RenderAccumulator`, `profiled_render`, `get_accumulator`, `timed_block`, `render_context`, `get_render_context`, `get_render_context_required` now exported from `kida`.

- **F-string coalescing optimization** — consecutive template outputs are merged into single f-string appends, reducing function call overhead by ~11% in output-heavy templates. Controlled via `Environment.fstring_coalescing` (enabled by default) and `Environment.pure_filters` for custom filter registration.

### Changed

- **Clean user context** — template rendering no longer injects internal keys (`_template`, `_line`, `_include_depth`, `_cached_blocks`, `_cached_stats`) into user context. Users can now safely use `_template` or `_line` as variable names without collision.

### Removed

- `{% do %}` directive — use `{% set _ = expr %}` for side effects instead

## [0.1.1] - 2026-01-12

### Fixed

- **`__html__` protocol support** — `html_escape()` now respects the `__html__` protocol, enabling interoperability with `markupsafe.Markup` and other libraries that implement this standard. Previously, only Kida's native `Markup` class was recognized as safe, causing double-escaping of content from external libraries.

## [0.1.0] - 2026-01-04

### Added

- Initial release extracted from Bengal static site generator
- AST-native compilation — generates `ast.Module` directly (no string manipulation)
- StringBuilder rendering — 25-40% faster than Jinja2's generator yields
- Free-threading ready — GIL-independent via `_Py_mod_gil = 0` for Python 3.14t+
- Modern syntax — unified `{% end %}`, pattern matching, pipelines
- Native async — true async/await support (no `auto_await()` wrappers)
- Built-in caching — `{% cache key %}...{% end %}` directive
- Pipeline operator — `{{ value |> filter1 |> filter2 }}`
- Pattern matching — `{% match %}...{% case %}` syntax
- Explicit scoping — `{% let %}`, `{% set %}`, `{% export %}` semantics
- Template inheritance — `{% extends %}`, `{% block %}`, `{% include %}`
- Bytecode caching — fast cold starts via marshalled code objects
- Thread-safe LRU cache with optional TTL support

### Changed

- Import paths changed from `bengal.rendering.kida` to `kida`

[0.3.1]: https://github.com/lbliii/kida/releases/tag/v0.3.1
[0.3.0]: https://github.com/lbliii/kida/releases/tag/v0.3.0
[0.2.9]: https://github.com/lbliii/kida/releases/tag/v0.2.9
[0.2.8]: https://github.com/lbliii/kida/releases/tag/v0.2.8
[0.2.7]: https://github.com/lbliii/kida/releases/tag/v0.2.7
[0.2.6]: https://github.com/lbliii/kida/releases/tag/v0.2.6
[0.2.5]: https://github.com/lbliii/kida/releases/tag/v0.2.5
[0.2.4]: https://github.com/lbliii/kida/releases/tag/v0.2.4
[0.2.3]: https://github.com/lbliii/kida/releases/tag/v0.2.3
[0.2.2]: https://github.com/lbliii/kida/releases/tag/v0.2.2
[0.2.1]: https://github.com/lbliii/kida/releases/tag/v0.2.1
[0.2.0]: https://github.com/lbliii/kida/releases/tag/v0.2.0
[0.1.2]: https://github.com/lbliii/kida/releases/tag/v0.1.2
[0.1.1]: https://github.com/lbliii/kida/releases/tag/v0.1.1
[0.1.0]: https://github.com/lbliii/kida/releases/tag/v0.1.0
