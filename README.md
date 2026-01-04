# Kida

**Modern template engine for Python 3.14t — AST-native, free-threading ready**

Kida is a pure-Python template engine designed for free-threaded Python 3.14t+. It features AST-native compilation, StringBuilder rendering (25-40% faster than Jinja2), and full async support.

## Installation

```bash
pip install kida
```

## Quick Start

```python
from kida import Environment

env = Environment()
template = env.from_string("Hello, {{ name }}!")
print(template.render(name="World"))
# Output: Hello, World!
```

### File-based Templates

```python
from kida import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("templates/"))
template = env.get_template("index.html")
print(template.render(page=page, site=site))
```

## Key Features

### AST-Native Compilation

Unlike Jinja2 which generates Python source strings, Kida generates `ast.Module` objects directly:

```
Template Source → Lexer → Parser → Kida AST → Compiler → Python AST → exec()
```

This enables structured code manipulation, compile-time optimization, and precise error source mapping.

### Free-Threading Ready (PEP 703)

Kida declares GIL-independence via `_Py_mod_gil = 0` and is safe for concurrent template rendering in Python 3.14t+ free-threaded builds.

### StringBuilder Rendering

25-40% faster than Jinja2's generator yield pattern:

```python
# Kida's approach (O(n))
_out.append(...)
return "".join(_out)

# vs Jinja2's approach (O(n) with higher overhead)
yield ...
```

### Modern Syntax

```kida
{# Unified block endings #}
{% if condition %}
    ...
{% end %}

{% for item in items %}
    {{ item }}
{% end %}

{# Pattern matching #}
{% match status %}
{% case "active" %}
    Active user
{% case "pending" %}
    Pending verification
{% case _ %}
    Unknown status
{% end %}

{# Pipeline operator #}
{{ title |> escape |> capitalize |> truncate(50) }}

{# Built-in caching #}
{% cache "navigation" %}
    {% for item in nav_items %}
        <a href="{{ item.url }}">{{ item.title }}</a>
    {% end %}
{% end %}
```

### Native Async Support

```python
{% async for item in fetch_items() %}
    {{ item }}
{% end %}

{{ await get_user() }}
```

### Template Inheritance

```kida
{# base.html #}
<!DOCTYPE html>
<html>
<body>
    {% block content %}{% end %}
</body>
</html>

{# page.html #}
{% extends "base.html" %}
{% block content %}
    <h1>{{ title }}</h1>
    <p>{{ content }}</p>
{% end %}
```

### Explicit Scoping

```kida
{# let - block-scoped variable #}
{% let temp = value * 2 %}

{# set - update existing variable #}
{% set counter = counter + 1 %}

{# export - make available to parent template #}
{% export title = "Page Title" %}
```

### Functions

```kida
{% def greet(name, greeting="Hello") %}
    {{ greeting }}, {{ name }}!
{% end %}

{{ greet("World") }}
{{ greet("Friend", greeting="Hi") }}
```

## Comparison with Jinja2

| Feature | Kida | Jinja2 |
|---------|------|--------|
| **Compilation** | AST → AST | String generation |
| **Rendering** | StringBuilder | Generator yields |
| **Block endings** | Unified `{% end %}` | Specific `{% endif %}`, `{% endfor %}` |
| **Scoping** | Explicit `let`/`set`/`export` | Implicit |
| **Async** | Native `async for`, `await` | `auto_await()` wrapper |
| **Pattern matching** | `{% match %}...{% case %}` | N/A |
| **Pipelines** | `{{ value \|> filter1 \|> filter2 }}` | N/A |
| **Caching** | `{% cache key %}...{% end %}` | N/A |
| **Free-threading** | Native (PEP 703) | N/A |

## Strict Mode

By default, undefined variables raise `UndefinedError`:

```python
>>> env.from_string("{{ missing }}").render()
# Raises UndefinedError

>>> env.from_string("{{ missing | default('N/A') }}").render()
'N/A'
```

## Thread-Safety

All public APIs are thread-safe by design:
- Template compilation is idempotent (same input → same output)
- Rendering uses only local state (StringBuilder pattern, no shared buffers)
- Environment caching uses copy-on-write for filters/tests/globals
- LRU caches use atomic operations

## Performance

Kida's StringBuilder pattern and AST-native compilation provide significant performance improvements:

- **25-40% faster rendering** than Jinja2 for typical templates
- **O(n) output generation** vs O(n²) string concatenation
- **Local variable caching** for frequently used functions (`_escape`, `_str`)
- **O(1) operator dispatch** via dict-based token → handler lookup
- **Single-pass HTML escaping** via `str.translate()`

## Requirements

- Python 3.14 or later
- **Zero runtime dependencies** (pure Python, includes native `Markup` implementation)

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Credits

Kida was originally developed as part of the [Bengal](https://github.com/lbliii/bengal) static site generator.

