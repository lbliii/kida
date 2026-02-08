---
title: API Reference
description: Core classes and methods
draft: false
weight: 10
lang: en
type: doc
tags:
- reference
- api
keywords:
- api
- environment
- template
- loaders
icon: code
---

# API Reference

## Environment

Central configuration and template management hub.

```python
from kida import Environment, FileSystemLoader

env = Environment(
    loader=FileSystemLoader("templates/"),
    autoescape=True,
)
```

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `loader` | `Loader` | `None` | Template source provider |
| `autoescape` | `bool \| Callable` | `True` | HTML auto-escaping |
| `auto_reload` | `bool` | `True` | Check for source changes |
| `cache_size` | `int` | `400` | Max cached templates |
| `fragment_cache_size` | `int` | `1000` | Max cached fragments |
| `fragment_ttl` | `float` | `300.0` | Fragment TTL (seconds) |

### Methods

#### get_template(name)

Load and cache a template by name.

```python
template = env.get_template("page.html")
```

**Raises**: `TemplateNotFoundError`, `TemplateSyntaxError`

#### from_string(source, name=None)

Compile a template from string (not cached in the template cache).

```python
template = env.from_string("Hello, {{ name }}!")
```

> **Bytecode caching**: If you have a `bytecode_cache` configured, pass `name=` to enable it. Without a name, there's no stable cache key, so the bytecode cache is bypassed. A `UserWarning` is emitted if you call `from_string()` without `name=` when a bytecode cache is active.

#### render(template_name, **context)

Load and render in one step.

```python
html = env.render("page.html", title="Hello", items=items)
```

#### render_string(source, **context)

Compile and render string in one step.

```python
html = env.render_string("{{ x * 2 }}", x=21)
```

#### add_filter(name, func)

Register a custom filter.

```python
env.add_filter("double", lambda x: x * 2)
```

#### add_test(name, func)

Register a custom test.

```python
env.add_test("even", lambda x: x % 2 == 0)
```

#### add_global(name, value)

Add a global variable.

```python
env.add_global("site_name", "My Site")
```

#### filter() (decorator)

Decorator to register a filter.

```python
@env.filter()
def double(value):
    return value * 2
```

#### test() (decorator)

Decorator to register a test.

```python
@env.test()
def is_even(value):
    return value % 2 == 0
```

#### cache_info()

Get cache statistics.

```python
info = env.cache_info()
# {'template': {...}, 'fragment': {...}}
```

#### clear_cache(include_bytecode=False)

Clear all caches.

```python
env.clear_cache()
```

---

## Template

Compiled template with render interface.

### Methods

#### render(**context)

Render template with context.

```python
html = template.render(name="World", items=[1, 2, 3])
```

#### render_async(**context)

Render template asynchronously.

```python
html = await template.render_async(items=async_generator())
```

#### render_stream_async(**context)

Render template as an async stream. Supports native `{% async for %}` and `{{ await }}` constructs. Also works on sync templates (wraps the sync stream).

```python
async for chunk in template.render_stream_async(items=async_iterable):
    send_to_client(chunk)
```

**Raises**: `RuntimeError` if no render function is available.

#### render_block_stream_async(block_name, **context)

Render a single block as an async stream. Falls back to wrapping the sync block stream if no async variant exists.

```python
async for chunk in template.render_block_stream_async("content", items=data):
    send_to_client(chunk)
```

**Raises**: `KeyError` if the block does not exist.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str \| None` | Template name |
| `filename` | `str \| None` | Source filename |
| `is_async` | `bool` | `True` if template uses `{% async for %}` or `{{ await }}` |

> **Note**: Calling `render()` or `render_stream()` on a template where `is_async` is `True` raises `TemplateRuntimeError`. Use `render_stream_async()` instead.

---

## Loaders

### FileSystemLoader

Load templates from filesystem directories.

```python
from kida import FileSystemLoader

# Single directory
loader = FileSystemLoader("templates/")

# Multiple directories (searched in order)
loader = FileSystemLoader(["templates/", "shared/"])
```

#### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `paths` | `str \| Path \| list` | Required | Search paths |
| `encoding` | `str` | `"utf-8"` | File encoding |

#### Methods

- `get_source(name)` → `tuple[str, str]`
- `list_templates()` → `list[str]`

### DictLoader

Load templates from a dictionary.

```python
from kida import DictLoader

loader = DictLoader({
    "base.html": "<html>{% block content %}{% end %}</html>",
    "page.html": "{% extends 'base.html' %}...",
})
```

### ChoiceLoader

Try multiple loaders in order, returning the first match.

```python
from kida import ChoiceLoader, FileSystemLoader

loader = ChoiceLoader([
    FileSystemLoader("themes/custom/"),
    FileSystemLoader("themes/default/"),
])
```

#### Constructor Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `loaders` | `list[Loader]` | Loaders to try in order |

#### Methods

- `get_source(name)` → `tuple[str, str | None]` — Returns first successful match
- `list_templates()` → `list[str]` — Merged, deduplicated, sorted list from all loaders

### PrefixLoader

Namespace templates by prefix, delegating to per-prefix loaders.

```python
from kida import PrefixLoader, FileSystemLoader

loader = PrefixLoader({
    "app": FileSystemLoader("templates/app/"),
    "admin": FileSystemLoader("templates/admin/"),
})

# env.get_template("app/index.html") → templates/app/index.html
```

#### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mapping` | `dict[str, Loader]` | Required | Prefix → loader mapping |
| `delimiter` | `str` | `"/"` | Prefix delimiter |

#### Methods

- `get_source(name)` → `tuple[str, str | None]` — Splits on delimiter, delegates to prefix loader
- `list_templates()` → `list[str]` — All templates with prefix prepended

### PackageLoader

Load templates from an installed Python package via `importlib.resources`.

```python
from kida import PackageLoader

loader = PackageLoader("my_app", "templates")
# env.get_template("pages/index.html") → my_app/templates/pages/index.html
```

#### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `package_name` | `str` | Required | Dotted Python package name |
| `package_path` | `str` | `"templates"` | Subdirectory within the package |
| `encoding` | `str` | `"utf-8"` | File encoding |

#### Methods

- `get_source(name)` → `tuple[str, str | None]` — Loads from package resources
- `list_templates()` → `list[str]` — All templates in the package directory (recursive)

### FunctionLoader

Wrap a callable as a loader.

```python
from kida import FunctionLoader

loader = FunctionLoader(lambda name: templates.get(name))
```

#### Constructor Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `load_func` | `Callable[[str], str \| tuple[str, str \| None] \| None]` | Returns source, `(source, filename)`, or `None` |

#### Methods

- `get_source(name)` → `tuple[str, str | None]` — Calls `load_func` and normalizes result
- `list_templates()` → `list[str]` — Always returns `[]` (cannot enumerate)

---

## Exceptions

### TemplateError

Base class for all template errors.

### TemplateSyntaxError

Invalid template syntax.

```python
from kida import TemplateSyntaxError

try:
    env.from_string("{% if x %}")  # Missing end
except TemplateSyntaxError as e:
    print(e)
```

### TemplateNotFoundError

Template file not found.

```python
from kida import TemplateNotFoundError

try:
    env.get_template("nonexistent.html")
except TemplateNotFoundError as e:
    print(e)
```

### UndefinedError

Accessing undefined variable.

```python
from kida import UndefinedError

try:
    env.from_string("{{ missing }}").render()
except UndefinedError as e:
    print(e)
```

---

## Markup

HTML-safe string wrapper.

```python
from kida import Markup

# Create safe HTML
safe = Markup("<b>Bold</b>")

# Escape unsafe content
escaped = Markup.escape("<script>")
# &lt;script&gt;

# Format with escaping
result = Markup("<p>{}</p>").format(user_input)
```

### Class Methods

| Method | Description |
|--------|-------------|
| `escape(s)` | Escape string and return Markup |

### Operations

| Operation | Behavior |
|-----------|----------|
| `Markup + str` | str is escaped |
| `Markup + Markup` | Concatenated as-is |
| `Markup.format(...)` | Arguments are escaped |

---

## LoopContext

Available as `loop` variable inside `{% for %}` loops.

| Property | Type | Description |
|----------|------|-------------|
| `index` | `int` | 1-based index |
| `index0` | `int` | 0-based index |
| `first` | `bool` | True on first iteration |
| `last` | `bool` | True on last iteration |
| `length` | `int` | Total items |
| `revindex` | `int` | Reverse 1-based index |
| `revindex0` | `int` | Reverse 0-based index |

```kida
{% for item in items %}
    {{ loop.index }}/{{ loop.length }}
{% end %}
```

---

## AsyncLoopContext

Available as `loop` variable inside `{% async for %}` loops. Provides index-forward properties only — properties that require knowing the total size raise `TemplateRuntimeError` since async iterables have no known length.

| Property | Type | Description |
|----------|------|-------------|
| `index` | `int` | 1-based index |
| `index0` | `int` | 0-based index |
| `first` | `bool` | True on first iteration |
| `previtem` | `Any \| None` | Previous item (`None` on first) |
| `cycle(*values)` | method | Cycle through values |
| `last` | — | Raises `TemplateRuntimeError` |
| `length` | — | Raises `TemplateRuntimeError` |
| `revindex` | — | Raises `TemplateRuntimeError` |
| `revindex0` | — | Raises `TemplateRuntimeError` |
| `nextitem` | — | Raises `TemplateRuntimeError` |

```kida
{% async for user in fetch_users() %}
    {{ loop.index }}: {{ user.name }}
    {% if loop.first %}(first!){% end %}
{% end %}
```

---

## RenderContext

Per-render state management via ContextVar.

```python
from kida.render_context import (
    RenderContext,
    render_context,
    get_render_context,
)
```

### RenderContext Dataclass

| Attribute | Type | Description |
|-----------|------|-------------|
| `template_name` | `str \| None` | Current template name |
| `filename` | `str \| None` | Source file path |
| `line` | `int` | Current line (for errors) |
| `include_depth` | `int` | Include nesting depth |
| `max_include_depth` | `int` | Max depth (default: 50) |
| `cached_blocks` | `dict[str, str]` | Site-scoped block cache |

### Methods

| Method | Description |
|--------|-------------|
| `check_include_depth(name)` | Raise if depth exceeded |
| `child_context(name)` | Create child with incremented depth |

### Functions

| Function | Description |
|----------|-------------|
| `get_render_context()` | Get current context (None if not rendering) |
| `get_render_context_required()` | Get context or raise RuntimeError |
| `render_context(...)` | Context manager for render scope |

---

## RenderAccumulator

Opt-in profiling for template rendering. When enabled via `profiled_render()`, the compiler-emitted instrumentation automatically tracks:

- **Blocks** — render timing (milliseconds) and call counts
- **Filters** — call counts per filter name
- **Macros** — call counts per `{% def %}` name
- **Includes** — counts per included template

Zero overhead when profiling is disabled — the instrumentation gates on a falsy check.

```python
from kida.render_accumulator import (
    RenderAccumulator,
    profiled_render,
    get_accumulator,
)
```

### Usage

```python
with profiled_render() as metrics:
    html = template.render(page=page)

summary = metrics.summary()
# {
#     "total_ms": 12.5,
#     "blocks": {"content": {"ms": 8.2, "calls": 1}, "nav": {"ms": 1.1, "calls": 1}},
#     "filters": {"upper": 3, "truncate": 2},
#     "macros": {"card": 5},
#     "includes": {"header.html": 1},
# }
```

### RenderAccumulator Properties

| Property | Type | Description |
|----------|------|-------------|
| `block_timings` | `dict[str, BlockTiming]` | Block render times |
| `macro_calls` | `dict[str, int]` | Macro call counts |
| `include_counts` | `dict[str, int]` | Include counts |
| `filter_calls` | `dict[str, int]` | Filter usage counts |
| `total_duration_ms` | `float` | Total render time |

### Methods

| Method | Description |
|--------|-------------|
| `record_block(name, ms)` | Record block timing |
| `record_macro(name)` | Record macro call |
| `record_include(name)` | Record include |
| `record_filter(name)` | Record filter usage |
| `summary()` | Get metrics dict |

## See Also

- [[docs/reference/filters|Filters Reference]] — All built-in filters
- [[docs/reference/tests|Tests Reference]] — All built-in tests
- [[docs/reference/configuration|Configuration]] — All options
