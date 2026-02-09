# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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

## [0.2.0] - 2026-02-08

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

[0.2.0]: https://github.com/lbliii/kida/releases/tag/v0.2.0
[0.1.2]: https://github.com/lbliii/kida/releases/tag/v0.1.2
[0.1.1]: https://github.com/lbliii/kida/releases/tag/v0.1.1
[0.1.0]: https://github.com/lbliii/kida/releases/tag/v0.1.0
