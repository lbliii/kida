# Kida Examples

Working examples that demonstrate kida's core capabilities. Each is self-contained
and runnable -- run the app or run the tests.

## Examples

### `hello/` -- The Basics

Compile a template from a string, render with context. Kida in ~10 lines.
No templates directory. Pure Python.

```bash
cd examples/hello && python app.py
```

### `file_loader/` -- File-Based Templates

The most common real-world pattern: load templates from disk with `FileSystemLoader`,
use template inheritance (`{% extends %}`), includes (`{% include %}`), and blocks.

```bash
cd examples/file_loader && python app.py
```

### `components/` -- Reusable Components

Kida's `{% def %}` / `{% call %}` / `{% slot %}` pattern for building reusable
UI components. Define a component once, use it everywhere with different content.

```bash
cd examples/components && python app.py
```

### `streaming/` -- Chunked Rendering

`render_stream()` yields template output as chunks at statement boundaries.
Ideal for chunked HTTP responses and Server-Sent Events.

```bash
cd examples/streaming && python app.py
```

### `async_rendering/` -- Native Async Templates

`{% async for %}` consumes async iterables directly. `{{ await expr }}` resolves
coroutines inline. `render_stream_async()` yields chunks as async data resolves.

```bash
cd examples/async_rendering && python app.py
```

### `caching/` -- Fragment Caching

Built-in `{% cache key %}` directive caches expensive template fragments.
Second render hits the cache -- no recomputation.

```bash
cd examples/caching && python app.py
```

### `modern_syntax/` -- Modern Syntax Features

Pattern matching (`{% match %}`), pipeline operator (`|>`), null coalescing (`??`),
and optional chaining (`?.`). Syntax with no Jinja2 equivalent.

```bash
cd examples/modern_syntax && python app.py
```

### `introspection/` -- Template Introspection

Static analysis API for pre-render validation and dependency tracking.
`required_context()` lists what a template needs, `block_metadata()` reports
per-block dependencies, `validate_context()` catches missing variables before
rendering, and `depends_on()` returns all dotted dependency paths. This is the
API that Purr's reactive pipeline uses to map content changes to template blocks.

```bash
cd examples/introspection && python app.py
```

### `htmx_partials/` -- Partial Block Rendering

`render_block()` extracts and renders a single block from a template -- the
pattern used by htmx, Turbo, and Unpoly for partial page updates. Full page
renders the entire template; partial renders extract just the block needed for
an AJAX swap response.

```bash
cd examples/htmx_partials && python app.py
```

### `bytecode_cache/` -- Cold Start Optimization

`BytecodeCache` compiles templates to Python bytecode on first load, caching the
code object to disk. Second load skips the parser and compiler entirely, loading
the pre-compiled bytecode directly. Useful for large template sets where startup
latency matters.

```bash
cd examples/bytecode_cache && python app.py
```

### `design_system/` -- Component Library

`{% def %}`, `{% slot %}`, and `{% call %}` composed into a design system with
reusable cards, buttons, and alerts. Components accept parameters with defaults
and project content through slots. Demonstrates real-world component composition:
buttons inside cards, cards inside pages.

```bash
cd examples/design_system && python app.py
```

### `fastapi_async/` -- FastAPI Integration

`render_stream_async()` with FastAPI's `StreamingResponse` for true streaming HTML
delivery. Templates with `{% async for %}` consume async data sources while the
response streams to the client.

```bash
pip install fastapi uvicorn
cd examples/fastapi_async && uvicorn app:app --reload
```

### `llm_streaming/` -- LLM Token Streaming

`{% async for %}` consuming a simulated LLM token stream. The template renders
progressively as tokens arrive, yielding HTML chunks via `render_stream_async()`.
O(n) total work instead of the O(n^2) re-render-per-token pattern.

```bash
cd examples/llm_streaming && python app.py
```

### `concurrent/` -- Free-Threading Proof

8 threads render different templates simultaneously with zero GIL contention.
Each thread gets its own render context via `ContextVar`, so there is no
cross-contamination between simultaneous renders. Demonstrates Python 3.14t
free-threading readiness.

```bash
cd examples/concurrent && python app.py
```

### `profiling/` -- Render Profiling

`profiled_render()` context manager collects block timings, filter usage, and
macro call counts during rendering. Zero overhead when profiling is not enabled.
Opt-in metrics for identifying template performance bottlenecks.

```bash
cd examples/profiling && python app.py
```

### `dict_loader/` -- In-Memory Templates

`DictLoader` loads templates from a dictionary. No filesystem required.
Use case: tests, generated templates, single-file apps.

```bash
cd examples/dict_loader && python app.py
```

### `custom_filters/` -- Custom Filters and Tests

`add_filter()`, `@env.filter()` decorator, and `add_test()` for extending Kida
with domain-specific helpers. Demonstrates money formatting, pluralize, and
custom tests like `is prime`.

```bash
cd examples/custom_filters && python app.py
```

### `rendered_template/` -- RenderedTemplate Lazy Wrapper

`RenderedTemplate(template, context)` wraps a template + context pair.
- `str(rt)` renders fully
- `for chunk in rt` iterates over `render_stream()` chunks

Use case: pass to `StreamingResponse` without calling `render()` first.

```bash
cd examples/rendered_template && python app.py
```

### `t_string/` -- t-string Interpolation (Python 3.14+)

`k(t"Hello {name}!")` processes PEP 750 t-strings with automatic HTML escaping.
Zero parser overhead. Ideal for high-frequency simple interpolation.

```bash
cd examples/t_string && python app.py
```

### `jinja2_migration/` -- Jinja2 Migration Guide

Side-by-side comparison of equivalent templates. Highlights syntax differences:
`{% end %}` vs `{% endif %}/{% endfor %}`, `{% match %}` vs `{% if %}/{% elif %}`,
`??` vs `| default()`, `?.` vs optional chaining patterns.

```bash
cd examples/jinja2_migration && python app.py
```

### `loop_context/` -- Loop Helpers

`loop.first`, `loop.last`, `loop.index`, `loop.length` in `{% for %}` blocks.
Use for styling first/last rows, row numbers, and progress indicators.

```bash
cd examples/loop_context && python app.py
```

## Running Tests

Each example has a `test_<name>.py` that verifies it works end-to-end.

```bash
# All examples
pytest examples/

# One example
pytest examples/hello/
```

## What Each Example Exercises

| Feature | hello | file_loader | components | streaming | async_rendering | caching | modern_syntax | introspection | htmx_partials | bytecode_cache | design_system | fastapi_async | llm_streaming | concurrent | profiling | dict_loader | custom_filters | rendered_template | t_string | jinja2_migration | loop_context |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `from_string()` | x | | | | | | | | | | | | | x | | x | x | x | | x |
| `FileSystemLoader` | | x | x | x | | x | x | x | x | x | x | x | x | | x | | x | | | | x |
| `DictLoader` | | | | | | | | | | | | | | | | x | | | | | |
| `render()` | x | x | x | | | x | x | x | x | x | x | | | x | x | x | x | | x | x | x |
| `render_stream()` | | | | x | | | | | | | | | | | | | x | | | | |
| `render_stream_async()` | | | | | x | | | | | | | x | x | | | | | | | | |
| `render_block()` | | | | | | | | | x | | | | | | | | | | | | |
| `RenderedTemplate` | | | | | | | | | | | | | | | | | | x | | | | |
| `render_stream()` via RenderedTemplate | | | | | | | | | | | | | | | | | | x | | | | |
| `{% extends %}` / `{% block %}` | | x | | | | | | x | x | | | | | | x | x | | | | | | |
| `{% include %}` | | x | x | | | | | | | | | | | | | | | | | | |
| `{% def %}` / `{% call %}` / `{% slot %}` | | | x | | | | | | | | x | | | | x | | | | | | |
| `{% async for %}` / `{{ await }}` | | | | | x | | | | | | | x | x | | | | | | | | |
| `{% cache %}` | | | | | | x | | | | | | | | | | | | | | | |
| `{% match %}` / `{% case %}` | | | | | | | x | | | | | | | | | | | | x | | |
| `\|>` pipeline | | | | | | | x | | | | | | | | | | | | | | |
| `??` null coalescing | | | | | | | x | | | | | | | | | | | | x | | |
| `?.` optional chaining | | | | | | | x | | | | | | | | | | | | x | | |
| `required_context()` | | | | | | | | x | | | | | | | | | | | | | |
| `block_metadata()` | | | | | | | | x | | | | | | | | | | | | | |
| `validate_context()` | | | | | | | | x | | | | | | | | | | | | | |
| `depends_on()` | | | | | | | | x | | | | | | | | | | | | | |
| `template_metadata()` | | | | | | | | x | | | | | | | | | | | | | |
| `BytecodeCache` | | | | | | | | | | x | | | | | | | | | | | |
| `profiled_render()` | | | | | | | | | | | | | | | x | | | | | | |
| `add_filter()` / `add_test()` | | | | | | | | | | | | | | | | | x | | | | | |
| `k()` t-string | | | | | | | | | | | | | | | | | | | x | | | |
| `loop` (loop.first, etc.) | | | | | | | | | | | | | | | | | | | | | x |
| `ThreadPoolExecutor` | | | | | | | | | | | | | | x | | | | | | | |
| FastAPI integration | | | | | | | | | | | | x | | | | | | | | | |
| Filters (`upper`, `truncate`, etc.) | | | | | | | | | | | | | | | x | | x | | | | |
