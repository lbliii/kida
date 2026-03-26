---
title: Extensions
description: Build custom template tags with the Extension plugin architecture
draft: false
weight: 20
lang: en
type: doc
tags:
  - extending
  - extensions
  - plugins
keywords:
  - extension
  - plugin
  - custom tags
  - node_types
icon: puzzle
---

# Extensions

Extensions let you add custom template tags to Kida without modifying core code. An extension registers new block keywords, parses them into AST nodes, and compiles those nodes into Python statements.

## Extension Base Class

Subclass `kida.extensions.Extension` and declare your tag keywords, node types, and optional end keywords:

```python
from kida.extensions import Extension

class MyExtension(Extension):
    tags = {"mytag"}               # Block keywords this extension handles
    node_types = {"MyTagNode"}     # Node class names this extension compiles
    end_keywords = {"endmytag"}    # End keywords for tags with bodies (optional)
```

Every extension receives the `Environment` instance on initialization and can provide filters, tests, and globals alongside custom tags:

```python
class MyExtension(Extension):
    tags = {"mytag"}
    node_types = {"MyTagNode"}

    def get_filters(self):
        return {"myfilter": lambda v: v.upper()}

    def get_tests(self):
        return {"even": lambda v: v % 2 == 0}

    def get_globals(self):
        return {"MY_CONST": 42}
```

## Registering Extensions

Pass extension classes (not instances) to the `Environment`:

```python
from kida import Environment

env = Environment(extensions=[MyExtension])
```

On initialization, the environment:

1. Instantiates each extension class with itself (`ext = ExtClass(self)`)
2. Registers `get_filters()`, `get_tests()`, and `get_globals()` results
3. Maps each tag in `tags` to the extension instance (parser dispatch)
4. Maps each name in `node_types` to the extension instance (compiler dispatch)
5. Merges `end_keywords` into the parser's end-keyword set

## Custom Node Types

Define your AST node as a frozen dataclass inheriting from `Node`:

```python
from dataclasses import dataclass
from kida.nodes.base import Node

@dataclass(frozen=True, slots=True)
class MyTagNode(Node):
    name: str
    body: tuple  # child nodes
```

The `Node` base class provides `lineno` and `col_offset` fields for source mapping. Use `frozen=True` and `slots=True` for immutable, memory-efficient nodes.

## Compiler Dispatch

The compiler resolves nodes by type name. When it encounters a node whose class name matches a `node_types` entry, it calls that extension's `compile()` method:

```
Compiler._compile_node(node)
  -> look up type(node).__name__ in _extension_compilers
  -> ext.compile(compiler, node)
```

This is an O(1) dictionary lookup. The extension's `compile()` method must return a `list[ast.stmt]` of Python AST statements.

## End Keywords

If your custom tag wraps a body (like `{% mytag %}...{% endmytag %}`), declare the closing keyword in `end_keywords` so the parser recognizes it:

```python
class MyExtension(Extension):
    tags = {"mytag"}
    node_types = {"MyTagNode"}
    end_keywords = {"endmytag"}
```

End keywords are merged into the parser's keyword set at initialization. Without this, the parser will not recognize `{% endmytag %}` as a valid block terminator.

You can also use the universal `{% end %}` syntax to close extension tags, but declaring `end_keywords` enables the explicit form.

## Example

Build a complete `{% debug expr %}` tag that prints a value during rendering:

```python
import ast
from dataclasses import dataclass

from kida import Environment
from kida.extensions import Extension
from kida.nodes.base import Node


@dataclass(frozen=True, slots=True)
class DebugNode(Node):
    expr: object  # Expr node from parser


class DebugExtension(Extension):
    tags = {"debug"}
    node_types = {"DebugNode"}

    def parse(self, parser, tag_name):
        # Current token is "debug" — advance past it
        token = parser._advance()

        # Parse the expression after the tag name
        expr = parser._parse_expression()

        # Expect the block-end delimiter (%})
        parser._expect(parser.TokenType.BLOCK_END)

        return DebugNode(
            lineno=token.lineno,
            col_offset=token.col_offset,
            expr=expr,
        )

    def compile(self, compiler, node):
        # Compile the Kida expression into a Python AST expression
        expr = compiler._compile_expr(node.expr)

        # Return a print() call statement
        return [
            ast.Expr(
                value=ast.Call(
                    func=ast.Name(id="print", ctx=ast.Load()),
                    args=[expr],
                    keywords=[],
                )
            )
        ]


# Register and use
env = Environment(extensions=[DebugExtension])
```

Template usage:

```kida
{% debug user.name %}
{# Prints the value of user.name to stdout during rendering #}
```

### Extension with a Body

For tags that wrap content, declare `end_keywords` and use `_parse_body()`:

```python
@dataclass(frozen=True, slots=True)
class TimedNode(Node):
    label: object
    body: tuple


class TimedExtension(Extension):
    tags = {"timed"}
    node_types = {"TimedNode"}
    end_keywords = {"endtimed"}

    def parse(self, parser, tag_name):
        token = parser._advance()
        label = parser._parse_expression()
        parser._expect(parser.TokenType.BLOCK_END)
        body = parser._parse_body()

        # Consume {% end %} or {% endtimed %}
        parser._advance()  # {%
        parser._advance()  # end/endtimed
        parser._expect(parser.TokenType.BLOCK_END)

        return TimedNode(
            lineno=token.lineno,
            col_offset=token.col_offset,
            label=label,
            body=tuple(body),
        )

    def compile(self, compiler, node):
        # Compile body nodes
        body_stmts = []
        for child in node.body:
            body_stmts.extend(compiler._compile_node(child))

        label_expr = compiler._compile_expr(node.label)

        # Wrap body in timing instrumentation
        return [
            ast.Expr(value=ast.Call(
                func=ast.Name(id="print", ctx=ast.Load()),
                args=[ast.JoinedStr(values=[
                    ast.Constant(value="[timed] start: "),
                    ast.FormattedValue(value=label_expr, conversion=-1),
                ])],
                keywords=[],
            )),
            *body_stmts,
            ast.Expr(value=ast.Call(
                func=ast.Name(id="print", ctx=ast.Load()),
                args=[ast.JoinedStr(values=[
                    ast.Constant(value="[timed] end: "),
                    ast.FormattedValue(value=label_expr, conversion=-1),
                ])],
                keywords=[],
            )),
        ]
```

Template usage:

```kida
{% timed "sidebar" %}
    {% include "partials/sidebar.html" %}
{% end %}
```

## See Also

- [[docs/extending/custom-filters|Custom Filters]] -- Add custom filters
- [[docs/extending/custom-tests|Custom Tests]] -- Add custom tests
- [[docs/extending/custom-globals|Custom Globals]] -- Add global variables
- [[docs/extending/custom-loaders|Custom Loaders]] -- Add template loaders
