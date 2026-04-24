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

## Contract Status

The framework-author surface below is treated as the documented integration
contract:

- imports exported from `kida.__all__`
- `ErrorCode` names and values
- `Environment(...)` constructor parameters
- `Template` render, block-render, streaming, and metadata methods
- metadata dataclass fields for `BlockMetadata`, `DefParamInfo`,
  `DefMetadata`, `TemplateMetadata`, and `TemplateStructureManifest`
- loader constructor behavior documented on this page
- sandbox, render context, capture, and manifest objects exported from `kida`

Snapshot tests guard those contracts. Any change to the stable surface should be
deliberate and land with docs and changelog updates when behavior changes.

Internals remain internal even when they are visible to Python: underscored
attributes, generated template namespace entries, parser/compiler node shapes,
cache implementation details, and helper functions outside `kida.__all__`.

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
| `static_context` | `dict \| None` | `None` | Values for compile-time partial evaluation |
| `strict_undefined` | `bool` | `True` | Raise `UndefinedError` on missing variable or attribute access (set to `False` for lenient empty-string fallback) |
| `jinja2_compat_warnings` | `bool` | `True` | Warn when nested `{% set %}` shadows a `{% let %}`/`{% export %}` name |
| `validate_calls` | `bool` | `False` | Validate `{% def %}` call sites at compile time |

> **Constructor contract note**: the generated dataclass constructor is part of
> the snapshot gate. Parameters not documented here are compatibility details
> rather than recommended framework integration points.

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

> **Partial evaluation**: Pass `static_context={...}` to evaluate expressions at compile time. Overrides Environment's `static_context` for this call.

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

### Rendering (all users)

#### render(**context)

Render template with context.

```python
html = template.render(name="World", items=[1, 2, 3])
```

#### render_async(**context)

Render template asynchronously (thread-pool wrapper for sync templates).

```python
html = await template.render_async(items=async_generator())
```

#### render_stream(**context)

Render template as a sync generator of string chunks. Yields at statement boundaries for chunked HTTP and streaming.

```python
for chunk in template.render_stream(items=data):
    send_to_client(chunk)
```

#### render_stream_async(**context)

Render template as an async stream. Supports native `{% async for %}` and `{{ await }}` constructs. Also works on sync templates (wraps the sync stream).

```python
async for chunk in template.render_stream_async(items=async_iterable):
    send_to_client(chunk)
```

**Raises**: `RuntimeError` if no render function is available.

### Block rendering (fragments, frameworks)

#### render_block(block_name, **context)

Render a single block from the template. Supports inherited blocks: when the template extends a parent, you can render parent-only blocks by name (e.g. `render_block("content")` on a child that extends a base defining `content`). Child overrides still win; `super()` is not supported.

```python
html = template.render_block("content", title="Hello")
```

**Raises**: `KeyError` if the block does not exist in the template or any parent.

#### render_with_blocks(block_overrides, **context)

Render template with pre-rendered HTML injected into blocks. Enables programmatic layout composition without `{% extends %}` in the template source.

```python
layout = env.get_template("_layout.html")
html = layout.render_with_blocks({"content": inner_html}, title="Page")
```

Each key in `block_overrides` names a block; the value is a pre-rendered HTML string. Unknown block names now raise `TemplateRuntimeError` with did-you-mean suggestions.

#### render_block_stream_async(block_name, **context)

Render a single block as an async stream. Supports inherited blocks like `render_block()`. Falls back to wrapping the sync block stream if no async variant exists.

```python
async for chunk in template.render_block_stream_async("content", items=data):
    send_to_client(chunk)
```

**Raises**: `KeyError` if the block does not exist.

#### list_blocks()

List all blocks available for `render_block()`, including inherited blocks.

```python
blocks = template.list_blocks()
# ['title', 'nav', 'content', 'footer']
```

### Component Introspection

#### list_defs()

List all `{% def %}` component names in the template.

```python
names = template.list_defs()
# ['card', 'nav_link', 'badge']
```

#### def_metadata()

Return metadata for all `{% def %}` components in the template. Returns a `dict[str, DefMetadata]`.

```python
meta = template.def_metadata()
card = meta["card"]
print(card.name)              # "card"
print(card.template_name)     # "components/card.html"
print(card.lineno)            # 3
print(card.params)            # (DefParamInfo(name='title', annotation='str', ...), ...)
print(card.slots)             # ('actions', 'footer')
print(card.has_default_slot)  # True
```

**DefMetadata** fields:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Component name |
| `template_name` | `str \| None` | Source template |
| `lineno` | `int` | Line number of `{% def %}` |
| `params` | `tuple[DefParamInfo, ...]` | Parameter metadata |
| `slots` | `tuple[str, ...]` | Named slot names |
| `has_default_slot` | `bool` | Whether `{% slot %}` (unnamed) exists |

**DefParamInfo** fields:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Parameter name |
| `annotation` | `str \| None` | Type annotation (e.g. `"str"`, `"int"`) |
| `has_default` | `bool` | Whether a default value is defined |
| `is_required` | `bool` | `True` if no default value |

#### warnings

Compile-time warnings collected during template compilation.

```python
for w in template.warnings:
    print(w.code, w.message, w.lineno)
```

### Template Introspection (frameworks, build systems)

#### template_metadata()

Return full template analysis (blocks, extends, dependencies). Returns `None` if AST was not preserved.

```python
meta = template.template_metadata()
if meta:
    print(meta.extends, meta.blocks.keys())
    regions = meta.regions()  # Only {% region %} blocks (for OOB discovery)
```

#### block_metadata()

Return per-block analysis (purity, cache scope, inferred role).

```python
blocks = template.block_metadata()
nav = blocks.get("nav")
if nav and nav.cache_scope == "site":
    ...
```

#### depends_on()

Return all context paths this template may access.

```python
deps = template.depends_on()
# frozenset({'page.title', 'site.pages'})
```

#### required_context()

Return top-level variable names the template needs.

```python
names = template.required_context()
# frozenset({'page', 'site'})
```

#### validate_context(context)

Check a context dict for missing variables. Returns list of missing names.

```python
missing = template.validate_context(user_context)
if missing:
    raise ValueError(f"Missing: {missing}")
```

#### is_cacheable(block_name=None)

Check if a block (or all blocks) can be safely cached.

```python
template.is_cacheable("nav")   # True if nav is cacheable
template.is_cacheable()       # True only if all blocks cacheable
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str \| None` | Template name |
| `filename` | `str \| None` | Source filename |
| `is_async` | `bool` | `True` if template uses `{% async for %}` or `{{ await }}` |
| `warnings` | `list[TemplateWarning]` | Compile-time warnings (precedence, coercion, migration) |

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

## Composition Helpers

Validation and structure helpers for frameworks. See [Framework Integration](/docs/usage/framework-integration/) for full usage.

```python
from kida.composition import (
    validate_block_exists,
    validate_template_block,
    get_structure,
    block_role_for_framework,
)
```

### validate_block_exists(env, template_name, block_name) → bool

Check if a block exists in a template (including inherited blocks). Returns `False` if template not found or block missing.

```python
if validate_block_exists(env, "skills/page.html", "page_content"):
    html = env.get_template("skills/page.html").render_block("page_content", ...)
```

### validate_template_block(template, block_name) → bool

Check if a block exists in a loaded Template instance.

### get_structure(env, template_name) → TemplateStructureManifest | None

Get lightweight structure manifest (block names, extends, dependencies). Cached by Environment.

```python
struct = get_structure(env, "page.html")
if struct and "page_root" in struct.block_names:
    ...
```

**TemplateStructureManifest** fields:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str \| None` | Template name |
| `extends` | `str \| None` | Parent template from `{% extends %}` |
| `block_names` | `tuple[str, ...]` | Ordered block names |
| `block_hashes` | `dict[str, str]` | Per-block structural hashes |
| `dependencies` | `frozenset[str]` | Context paths accessed |

### block_role_for_framework(block_metadata, ...) → str | None

Classify block metadata into framework roles: `"fragment"`, `"page_root"`, or `None`.

---

## Exceptions

### TemplateError

Base class for all template errors. All Kida exceptions carry an `ErrorCode` accessible via `exc.code`.

### TemplateSyntaxError

Invalid template syntax.

```python
from kida import TemplateSyntaxError

try:
    env.from_string("{% if x %}")  # Missing end
except TemplateSyntaxError as e:
    print(e)
```

### TemplateRuntimeError

Error during template rendering. Includes `component_stack` for errors inside `{% def %}` components:

```python
from kida import TemplateRuntimeError

try:
    template.render(items=None)
except TemplateRuntimeError as e:
    print(e.code)             # ErrorCode enum value
    print(e.component_stack)  # [(def_name, lineno, template_name), ...]
    print(e.format_compact()) # Formatted error with source snippet
```

### TemplateNotFoundError

Template file not found. Includes caller context (requesting template and line number).

```python
from kida import TemplateNotFoundError

try:
    env.get_template("nonexistent.html")
except TemplateNotFoundError as e:
    print(e)
```

### UndefinedError

Accessing undefined variable or attribute. The `kind` field distinguishes between variable, attribute, and key lookups.

```python
from kida import UndefinedError

try:
    env.from_string("{{ missing }}").render()
except UndefinedError as e:
    print(e.kind)  # "variable", "attribute", or "key"
    print(e)       # "Undefined variable 'missing' in <string>:1"
```

Under the default strict mode, attribute access errors also include component context:

```python
env = Environment()  # strict_undefined=True by default
# "Undefined attribute 'typo' on User object in page.html:5"
```

Opt out per-Environment with `strict_undefined=False` if you need empty-string fallback for missing attributes.

### SecurityError

Raised by `SandboxedEnvironment` when a template violates the security policy. Carries error codes K-SEC-001 through K-SEC-005.

### Warning Classes

Compile-time warnings emitted during template compilation:

| Class | Code | Description |
|-------|------|-------------|
| `PrecedenceWarning` | K-WARN-001 | `\|` binds tighter than `??` |
| `CoercionWarning` | — | Silent type coercion in filters (e.g. `"abc" \| float` → `0.0`) |
| `MigrationWarning` | K-WARN-002 | Nested `{% set %}` shadows a `{% let %}`/`{% export %}` name (Jinja2 scoping trap) |

These are standard Python warnings and can be filtered with `warnings.filterwarnings`.

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
    async_render_context,
    get_render_context,
    get_render_context_required,
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
| `child_context(template_name=None, *, source=None)` | Create child for include/embed with incremented depth |
| `child_context_for_extends(parent_name, *, source=None)` | Create child for extends with incremented extends_depth |
| `get_meta(key, default=None)` | Get framework metadata (HTMX, CSRF, etc.) |
| `set_meta(key, value)` | Set framework metadata before rendering |

### Functions

| Function | Description |
|----------|-------------|
| `get_render_context()` | Get current context (None if not rendering) |
| `get_render_context_required()` | Get context or raise RuntimeError |
| `render_context(...)` | Context manager for render scope |
| `async_render_context(...)` | Async context manager for render scope |

### Low-Level APIs

For cases where the context manager isn't suitable (e.g. nested include/embed that need manual restore):

| Function | Description |
|----------|-------------|
| `set_render_context(ctx)` | Set a RenderContext, returns reset token |
| `reset_render_context(token)` | Restore previous context using token from `set_render_context()` |

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
