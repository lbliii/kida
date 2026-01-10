---
title: FAQ
description: Frequently asked questions about Kida
draft: false
weight: 50
lang: en
type: doc
tags:
- about
- faq
keywords:
- faq
- questions
- answers
icon: help-circle
---

# FAQ

Frequently asked questions about Kida.

## General

### Why Kida instead of Jinja2?

Kida offers:

- **Performance**: 25-40% faster rendering (StringBuilder vs generators)
- **Free-threading**: Native PEP 703 support for Python 3.14t
- **Zero dependencies**: No external packages required
- **Modern syntax**: Unified `{% end %}`, pattern matching, pipelines
- **Built-in caching**: `{% cache %}` directive for fragment caching

### Is Kida production-ready?

Kida is in beta. It's suitable for:

- ✅ Personal projects
- ✅ Internal tools
- ⚠️ Production (test thoroughly first)

### What Python versions are supported?

**Required**: Python 3.14+

Kida uses modern Python features and is designed for the free-threaded future.

---

## Compatibility

### Can I use my existing Jinja2 templates?

Yes! Kida parses Jinja2 syntax. Most templates work unchanged:

```python
# Just change the import
from kida import Environment, FileSystemLoader
```

See [[docs/tutorials/migrate-from-jinja2|Migration Guide]].

### What Jinja2 features are missing?

- Sandboxed environment
- LaTeX/RTF formatters (HTML only)
- Line statements disabled by default (enable with `line_statement_prefix`)

### Do I need markupsafe?

No. Kida includes a native `Markup` class:

```python
from kida import Markup  # Built-in, not markupsafe
```

---

## Syntax

### Why unified `{% end %}`?

Unified endings are:

- **Simpler**: One syntax to remember
- **Cleaner**: Less visual noise
- **Consistent**: Same pattern for all blocks

```kida
{% if condition %}
    {% for item in items %}
        {{ item }}
    {% end %}
{% end %}
```

Kida still accepts `{% endif %}`, `{% endfor %}`, etc. for compatibility.

### What's the pipeline operator?

`|>` is a more readable way to chain filters:

```kida
{# Traditional pipe #}
{{ title | escape | upper | truncate(50) }}

{# Pipeline (same result) #}
{{ title |> escape |> upper |> truncate(50) }}
```

### How does pattern matching work?

`{% match %}` provides cleaner branching than if/elif chains:

```kida
{% match status %}
{% case "active" %}
    ✓ Active
{% case "pending" %}
    ⏳ Pending
{% case _ %}
    Unknown
{% end %}
```

---

## Performance

### How fast is Kida?

25-40% faster than Jinja2 in benchmarks:

| Template | Kida | Jinja2 | Speedup |
|----------|------|--------|---------|
| Small | 0.3ms | 0.5ms | 1.6x |
| Large | 15ms | 25ms | 1.67x |

### Why is Kida faster?

- **StringBuilder pattern**: O(n) vs generator overhead
- **AST-native compilation**: No string manipulation
- **Local variable caching**: Fewer attribute lookups

### How do I optimize templates?

1. Disable `auto_reload` in production
2. Use bytecode cache for cold starts
3. Cache expensive fragments with `{% cache %}`
4. Precompute complex logic in Python

See [[docs/about/performance|Performance]].

---

## Threading

### Is Kida thread-safe?

Yes. All public APIs are thread-safe:

- Configuration is immutable
- Rendering uses only local state
- Caches use atomic operations

### What's free-threading support?

Kida declares GIL-independence (PEP 703):

```python
_Py_mod_gil = 0  # Safe for free-threading
```

On Python 3.14t, templates render with true parallelism.

### Can I render concurrently?

Yes:

```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(template.render, contexts))
```

---

## Development

### How do I debug templates?

Use the `debug` filter:

```kida
{{ posts | debug }}
{{ posts | debug("my posts") }}
```

Output goes to stderr with type info and values.

### How do I report bugs?

Open an issue: https://github.com/lbliii/kida/issues

Include:
- Kida version
- Python version
- Minimal reproduction
- Error message

### How do I contribute?

See CONTRIBUTING.md in the repository.

---

## See Also

- [[docs/about/comparison|Comparison]] — Kida vs Jinja2
- [[docs/tutorials/migrate-from-jinja2|Migration]] — Moving from Jinja2
- [[docs/troubleshooting/|Troubleshooting]] — Common issues
