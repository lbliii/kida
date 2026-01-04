---
title: Configuration
description: All Environment configuration options
draft: false
weight: 40
lang: en
type: doc
tags:
- reference
- configuration
keywords:
- configuration
- options
- environment
icon: settings
---

# Configuration

All Environment configuration options.

## Environment Constructor

```python
from kida import Environment, FileSystemLoader

env = Environment(
    loader=FileSystemLoader("templates/"),
    autoescape=True,
    auto_reload=True,
    cache_size=400,
    fragment_cache_size=1000,
    fragment_ttl=300.0,
)
```

---

## Core Options

### loader

Template source provider.

| Type | Default | Description |
|------|---------|-------------|
| `Loader \| None` | `None` | Template loader |

```python
# FileSystemLoader
loader = FileSystemLoader("templates/")

# Multiple paths
loader = FileSystemLoader(["templates/", "shared/"])

# DictLoader
loader = DictLoader({"page.html": "..."})
```

### autoescape

HTML auto-escaping for output.

| Type | Default | Description |
|------|---------|-------------|
| `bool \| Callable` | `True` | Enable escaping |

```python
# Always escape
autoescape=True

# Never escape
autoescape=False

# Conditional by filename
def should_escape(name):
    if name is None:
        return True
    return name.endswith((".html", ".xml"))

autoescape=should_escape
```

### auto_reload

Check for template source changes.

| Type | Default | Description |
|------|---------|-------------|
| `bool` | `True` | Check on each load |

```python
# Development: check for changes
auto_reload=True

# Production: skip checks
auto_reload=False
```

---

## Cache Options

### cache_size

Maximum compiled templates to cache.

| Type | Default | Description |
|------|---------|-------------|
| `int` | `400` | LRU cache size |

```python
# Small cache (testing)
cache_size=10

# Large cache (production)
cache_size=1000
```

### fragment_cache_size

Maximum `{% cache %}` fragments to cache.

| Type | Default | Description |
|------|---------|-------------|
| `int` | `1000` | Fragment cache size |

### fragment_ttl

Fragment cache time-to-live in seconds.

| Type | Default | Description |
|------|---------|-------------|
| `float` | `300.0` | 5 minutes |

```python
# Short TTL for development
fragment_ttl=1.0

# Longer TTL for production
fragment_ttl=3600.0  # 1 hour
```

### bytecode_cache

Persistent bytecode cache for cold-start performance.

| Type | Default | Description |
|------|---------|-------------|
| `BytecodeCache \| bool \| None` | `None` | Bytecode cache |

```python
from kida.bytecode_cache import BytecodeCache

# Auto-detect (default)
bytecode_cache=None

# Explicit disable
bytecode_cache=False

# Custom location
bytecode_cache=BytecodeCache("__pycache__/kida/")
```

---

## Lexer Options

Control template syntax delimiters.

### block_start / block_end

Tag delimiters.

| Option | Default | Description |
|--------|---------|-------------|
| `block_start` | `"{%"` | Opening tag |
| `block_end` | `"%}"` | Closing tag |

### variable_start / variable_end

Output delimiters.

| Option | Default | Description |
|--------|---------|-------------|
| `variable_start` | `"{{"` | Opening output |
| `variable_end` | `"}}"` | Closing output |

### comment_start / comment_end

Comment delimiters.

| Option | Default | Description |
|--------|---------|-------------|
| `comment_start` | `"{#"` | Opening comment |
| `comment_end` | `"#}"` | Closing comment |

### Custom Delimiters

```python
# Ruby-like syntax
env = Environment(
    block_start="<%",
    block_end="%>",
    variable_start="<%=",
    variable_end="%>",
    comment_start="<%#",
    comment_end="%>",
)
```

---

## Whitespace Options

### trim_blocks

Remove newline after block tags.

| Type | Default | Description |
|------|---------|-------------|
| `bool` | `False` | Trim after `%}` |

### lstrip_blocks

Remove leading whitespace before block tags.

| Type | Default | Description |
|------|---------|-------------|
| `bool` | `False` | Strip before `{%` |

```python
env = Environment(
    trim_blocks=True,
    lstrip_blocks=True,
)
```

---

## Behavior Options

### strict_none

Strict None comparison in sorting.

| Type | Default | Description |
|------|---------|-------------|
| `bool` | `False` | Fail on None comparisons |

```python
# Lenient (default): None sorts last
strict_none=False

# Strict: raise error on None
strict_none=True
```

### preserve_ast

Preserve AST for template introspection.

| Type | Default | Description |
|------|---------|-------------|
| `bool` | `True` | Keep AST after compile |

```python
# Enable introspection (default)
preserve_ast=True

# Disable to save memory
preserve_ast=False
```

---

## Development vs Production

### Development

```python
env = Environment(
    loader=FileSystemLoader("templates/"),
    autoescape=True,
    auto_reload=True,          # Check for changes
    cache_size=50,             # Small cache
    fragment_ttl=1.0,          # Short TTL
)
```

### Production

```python
env = Environment(
    loader=FileSystemLoader("templates/"),
    autoescape=True,
    auto_reload=False,         # No reload checks
    cache_size=1000,           # Large cache
    fragment_ttl=3600.0,       # 1 hour TTL
)
```

---

## Cache Methods

### cache_info()

Get cache statistics.

```python
info = env.cache_info()
print(info["template"])
# {'size': 5, 'max_size': 400, 'hits': 100, 'misses': 5, 'hit_rate': 0.95}
```

### clear_cache(include_bytecode=False)

Clear all caches.

```python
env.clear_cache()                    # Memory only
env.clear_cache(include_bytecode=True)  # Include disk
```

### clear_template_cache(names=None)

Clear specific templates.

```python
env.clear_template_cache()           # All
env.clear_template_cache(["base.html", "page.html"])  # Specific
```

### clear_fragment_cache()

Clear fragment cache only.

```python
env.clear_fragment_cache()
```

## See Also

- [[docs/reference/api|API Reference]] — Environment methods
- [[docs/usage/loading-templates|Loading Templates]] — Loader configuration
- [[docs/about/performance|Performance]] — Optimization tips

