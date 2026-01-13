# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[0.1.2]: https://github.com/lbliii/kida/releases/tag/v0.1.2
[0.1.1]: https://github.com/lbliii/kida/releases/tag/v0.1.1
[0.1.0]: https://github.com/lbliii/kida/releases/tag/v0.1.0
