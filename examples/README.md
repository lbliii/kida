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
UI components. Supports default and named slots for multi-region composition.
Use the
[App-Owned Component Authoring Contract](https://lbliii.github.io/kida/docs/usage/components/#app-owned-authoring-contract)
to decide which boundaries belong in a component and which route composition
should remain inline.

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

### `regions/` -- Parameterized Blocks

`{% region %}` blocks are parameterized fragments that work as both blocks (for
`render_block()`) and callables (for `{{ name(args) }}`). Supports simple and
complex default expressions (`meta=page.metadata`, `count=items | length`,
`title=page?.title ?? "Default"`). Use for HTMX partials, OOB updates, or
layout composition.

```bash
cd examples/regions && python app.py
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
and project content through default and named slots. Demonstrates real-world component composition:
buttons inside cards, cards inside pages.

```bash
cd examples/design_system && python app.py
```

### `local_components/` -- App-Owned Components and CSS

A framework-neutral application with typed controls, a product-specific search
pattern, named and scoped slots, server-rendered accessible state, and ordinary
app-owned semantic CSS. Includes explicit `kida check` and machine-readable
component-inspection commands, plus tests for broken props and slot bindings.

```bash
uv run python examples/local_components/app.py
```

### `encapsulation_loop/` -- Evidence-Driven Component Refactoring

A deterministic before/after corpus for humans and coding agents. It consumes
ordinary structured advice, chooses extraction, inlining, or boundary
preservation, validates calls and slots, compares rendered surfaces, and reports
false positives, false negatives, and optional local analysis cost.

```bash
uv run python examples/encapsulation_loop/app.py
uv run python examples/encapsulation_loop/app.py --measure --rounds 5
```

### `flask_components/` -- Typed Components in Flask

A real Flask 3.1 app using `kida.contrib.flask`: a typed form component on the
full-page route and `render_block()` for a POST fragment response. Includes a
non-network smoke path used by CI.

```bash
uv run python examples/flask_components/app.py --smoke
```

### `django_components/` -- Typed Components in Django

A minimal Django 6.0 app registering `kida.contrib.django.KidaTemplates` through
the standard `TEMPLATES` setting. The GET route uses `django.shortcuts.render`;
the POST route returns a Kida block fragment.

```bash
uv run python examples/django_components/app.py --smoke
```

### `fastapi_components/` -- Typed Components in FastAPI

A FastAPI 0.139 / Starlette 1.3 app using `KidaTemplates.TemplateResponse()` and
an ASGI-tested POST fragment route, without requiring multipart parsing.

```bash
uv run python examples/fastapi_components/app.py --smoke
```

### `fastapi_async/` -- FastAPI Integration

`render_stream_async()` with FastAPI's `StreamingResponse` for true streaming HTML
delivery on Python 3.14+. Templates with `{% async for %}` consume async data
sources while the response streams to the client.

```bash
uv add fastapi uvicorn kida-templates
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

### `render_capture_manifest/` -- Build-Time Render Facts

`captured_render()` records rendered blocks and selected context into a
`RenderCapture`. The example accumulates captures in a `RenderManifest`, compares
two builds, inspects `FreezeCache` candidates and statistics, and derives search
entries with `SearchManifestBuilder`.

```bash
cd examples/render_capture_manifest && python app.py
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

Side-by-side comparison of equivalent templates. Shows that matching Jinja
closers such as `{% endif %}` and `{% endfor %}` are accepted unchanged while
`{% end %}` remains canonical Kida style, then compares `{% match %}`, `??`, and
`?.` with their Jinja patterns.

```bash
cd examples/jinja2_migration && python app.py
```

### `loop_context/` -- Loop Helpers

`loop.first`, `loop.last`, `loop.index`, `loop.length` in `{% for %}` blocks.
Use for styling first/last rows, row numbers, and progress indicators.

```bash
cd examples/loop_context && python app.py
```

## Additional Examples by Track

These examples are also part of the public catalog and are covered by focused
tests, smoke tests, or both.

### Component and State Patterns

- `provide_consume/` -- parent-to-child state propagation with `{% provide %}` and `consume()`.
- `content_stacks/` -- push/stack patterns for head tags, scripts, and deferred content.
- `list_comprehensions/` -- Python-style list comprehensions in template expressions.

### Agents and CI Reports

- `amp/` -- agent instruction examples for AMP-compatible structured output.
- `coverage/` -- render coverage data as a report.
- `review_packet/` -- render tests, lint, coverage, diagnostics, and steward findings as one PR review packet.

### Adoption and Refactor Safety

- `refactor_safety/` -- passing and broken template trees that demonstrate static call validation, parser diagnostics, fragile include linting, and pre-render context checks.

### Extension and Safety Patterns

- `extensions/` -- custom parser/compiler extension hooks.
- `sandbox/` -- sandboxed rendering policy examples.

### Terminal Rendering

- `terminal_basic/` -- minimal terminal rendering.
- `terminal_render/` -- render terminal templates from structured data.
- `terminal_report/` -- terminal report output.
- `terminal_table/` -- table formatting.
- `terminal_layout/` -- columns and layout helpers.
- `terminal_dashboard/` -- dashboard-style terminal output.
- `terminal_deploy/` -- deployment progress output.
- `terminal_gitlog/` -- git log formatting.
- `terminal_monitor/` -- monitoring-style output.
- `terminal_live/` -- live renderer loop; intentionally excluded from fast smoke tests.
- `terminal_saga_dashboard/` -- Milo-style saga dashboard with `Store` and `LiveRenderer`.

## Running Tests

Example tests are part of Kida's standard pytest collection, so `make test`,
`make test-cov`, and CI run them alongside `tests/`. Most examples have a local
`test_<name>.py` that verifies behavior end-to-end. `tests/test_examples.py`
also smoke-runs practical `run.py` or `app.py` examples and checks that every
runnable top-level example is listed here.

New examples should keep focused behavior tests beside the example. Use the
shared `example_app` fixture from `examples/conftest.py` when the test should
load the sibling `app.py`; guard optional integrations with
`pytest.importorskip()` so a minimal Kida checkout still collects cleanly.

```bash
# Standard suite (tests/ and examples/)
uv run pytest

# One example
uv run pytest examples/hello/
```

## What Each Example Exercises

| Feature | hello | file_loader | components | regions | streaming | async_rendering | caching | modern_syntax | introspection | htmx_partials | bytecode_cache | design_system | fastapi_async | llm_streaming | concurrent | profiling | dict_loader | custom_filters | rendered_template | t_string | jinja2_migration | loop_context |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `from_string()` | x | | | | | | | | | | | | | x | | x | x | x | | x |
| `FileSystemLoader` | | x | x | x | x | | x | x | x | x | x | x | x | | x | | x | | | | x |
| `DictLoader` | | | | | | | | | | | | | | | | x | | | | | |
| `render()` | x | x | x | x | | | x | x | x | x | x | | | x | x | x | x | | x | x | x |
| `render_stream()` | | | | | x | | | | | | | | | | | | x | | | | |
| `render_stream_async()` | | | | | | x | | | | | | x | x | | | | | | | | |
| `render_block()` | | | | x | | | | | x | x | | | | | | | | | | | |
| `{% region %}` | | | | x | | | | | | | | | | | | | | | | | |
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
| `depends_on()` | | | | x | | | | x | | | | | | | | | | | | | |
| `template_metadata()` | | | | x | | | | x | | | | | | | | | | | | | |
| `BytecodeCache` | | | | | | | | | | x | | | | | | | | | | | |
| `profiled_render()` | | | | | | | | | | | | | | | x | | | | | | |
| `add_filter()` / `add_test()` | | | | | | | | | | | | | | | | | x | | | | | |
| `k()` t-string | | | | | | | | | | | | | | | | | | | x | | | |
| `loop` (loop.first, etc.) | | | | | | | | | | | | | | | | | | | | | x |
| `ThreadPoolExecutor` | | | | | | | | | | | | | | x | | | | | | | |
| FastAPI integration | | | | | | | | | | | | x | | | | | | | | | |
| Filters (`upper`, `truncate`, etc.) | | | | | | | | | | | | | | | x | | x | | | | |
