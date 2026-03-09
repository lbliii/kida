# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
