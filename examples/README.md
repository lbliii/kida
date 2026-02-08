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

## Running Tests

Each example has a `test_app.py` that verifies it works end-to-end.

```bash
# All examples
pytest examples/

# One example
pytest examples/hello/
```

## What Each Example Exercises

| Feature | hello | file_loader | components | streaming | async_rendering | caching | modern_syntax |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `from_string()` | x | | | | | | |
| `FileSystemLoader` | | x | x | x | | x | x |
| `render()` | x | x | x | | | x | x |
| `render_stream()` | | | | x | | | |
| `render_stream_async()` | | | | | x | | |
| `{% extends %}` / `{% block %}` | | x | | | | | |
| `{% include %}` | | x | x | | | | |
| `{% def %}` / `{% call %}` / `{% slot %}` | | | x | | | | |
| `{% async for %}` / `{{ await }}` | | | | | x | | |
| `{% cache %}` | | | | | | x | |
| `{% match %}` / `{% case %}` | | | | | | | x |
| `\|>` pipeline | | | | | | | x |
| `??` null coalescing | | | | | | | x |
| `?.` optional chaining | | | | | | | x |
