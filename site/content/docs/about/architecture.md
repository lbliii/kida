---
title: Architecture
description: How Kida works internally
draft: false
weight: 10
lang: en
type: doc
tags:
- about
- architecture
keywords:
- architecture
- internals
- compiler
icon: cpu
---

# Architecture

Kida's compilation and rendering pipeline.

## Overview

```
Template Source → Lexer → Parser → Kida AST → Compiler → Python AST → exec()
```

## Pipeline Stages

### 1. Lexer

Tokenizes template source into a stream of tokens.

```python
from kida.lexer import Lexer, LexerConfig

lexer = Lexer("Hello, {{ name }}!", LexerConfig())
tokens = list(lexer.tokenize())
# [TEXT("Hello, "), VAR_START, NAME("name"), VAR_END, TEXT("!")]
```

**Token types**:
- `TEXT` — Raw text content
- `VAR_START` / `VAR_END` — `{{` and `}}`
- `BLOCK_START` / `BLOCK_END` — `{%` and `%}`
- `NAME`, `STRING`, `NUMBER` — Expression tokens

### 2. Parser

Builds an immutable Kida AST from the token stream.

```python
from kida.parser import Parser

parser = Parser(tokens, name="template.html", source=source)
ast = parser.parse()
```

**AST nodes**:
- `TemplateNode` — Root container
- `TextNode` — Static text
- `OutputNode` — `{{ expr }}`
- `IfNode`, `ForNode`, `MatchNode` — Control flow
- `BlockNode`, `ExtendsNode` — Inheritance

### 3. Compiler

Transforms Kida AST to Python AST directly.

```python
from kida.compiler import Compiler

compiler = Compiler(env)
code = compiler.compile(ast, name="template.html")
# Returns compiled code object
```

**Key difference from Jinja2**: Kida generates `ast.Module` objects directly, not Python source strings. This enables:
- Structured code manipulation
- Compile-time optimization
- Precise error source mapping

### 4. Template

Wraps the compiled code with the render interface.

```python
template = Template(env, code, name="template.html")
html = template.render(name="World")
```

## Rendering

Kida uses the **StringBuilder pattern** for O(n) rendering:

```python
# Generated render function (simplified)
def _render(context):
    _out = []
    _out.append("Hello, ")
    _out.append(_escape(context["name"]))
    _out.append("!")
    return "".join(_out)
```

**Benefits**:
- O(n) string construction (vs O(n²) concatenation)
- Lower memory churn than generators
- 25-40% faster than Jinja2's yield-based approach

## Caching Architecture

Three cache layers:

### Bytecode Cache (Disk)

Persists compiled bytecode via `marshal`:

```python
from kida.bytecode_cache import BytecodeCache

cache = BytecodeCache("__pycache__/kida/")
cache.set(name, source_hash, code)
cached = cache.get(name, source_hash)
```

**Benefits**: 90%+ cold-start improvement for serverless.

### Template Cache (Memory)

LRU cache of compiled Template objects:

```python
env = Environment(cache_size=400)
info = env.cache_info()["template"]
# {'size': 50, 'max_size': 400, 'hits': 1000, 'misses': 50}
```

### Fragment Cache (Memory)

TTL-based cache for `{% cache %}` blocks:

```python
env = Environment(
    fragment_cache_size=1000,
    fragment_ttl=300.0,  # 5 minutes
)
```

## Design Principles

### 1. AST-Native

No string manipulation or regex. The entire pipeline operates on structured AST objects.

### 2. Free-Threading Ready

- Compilation is idempotent
- Rendering uses only local state
- Caches use atomic operations
- No shared mutable state

### 3. Zero Dependencies

Pure Python, no runtime dependencies. Includes native `Markup` class.

### 4. Jinja2 Compatible

Parses most Jinja2 templates. Migration path is smooth.

## See Also

- [[docs/about/performance|Performance]] — Benchmarks
- [[docs/about/thread-safety|Thread Safety]] — Free-threading details
- [[docs/reference/api|API Reference]] — Public interface
