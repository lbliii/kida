"""Kida Compiler Core — main Compiler class.

The Compiler transforms Kida AST into Python AST, then compiles to
executable code objects. Uses a mixin-based design for maintainability.

Design Principles:
1. **AST-to-AST**: Generate `ast.Module`, not source strings
2. **StringBuilder**: Output via `buf.append()`, join at end
3. **Local caching**: Cache `_escape`, `_str`, `buf.append` as locals
4. **O(1) dispatch**: Dict-based node type → handler lookup

Performance Optimizations:
- `LOAD_FAST` for cached functions (vs `LOAD_GLOBAL` + hash)
- Method lookup cached once: `_append = buf.append`
- Single `''.join(buf)` at return (vs repeated concatenation)
- Line markers only for error-prone nodes (Output, For, If, etc.)

Block Inheritance:
Templates with `{% extends %}` generate:
1. Block functions: `_block_header(ctx, _blocks)`
2. Render function: Registers blocks, delegates to parent

    ```python
    def _block_header(ctx, _blocks):
        buf = []
        # Block body...
        return ''.join(buf)

    def render(ctx, _blocks=None):
        if _blocks is None: _blocks = {}
        _blocks.setdefault('header', _block_header)
        return _extends('base.html', ctx, _blocks)
    ```

"""

from __future__ import annotations

import ast
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

from kida.compiler.coalescing import FStringCoalescingMixin
from kida.compiler.expressions import ExpressionCompilationMixin
from kida.compiler.statements import StatementCompilationMixin
from kida.compiler.utils import OperatorUtilsMixin

if TYPE_CHECKING:
    import types

    from kida.environment import Environment
    from kida.nodes import Block, Extends, Node
    from kida.nodes import Template as TemplateNode


class Compiler(
    OperatorUtilsMixin,
    ExpressionCompilationMixin,
    StatementCompilationMixin,
    FStringCoalescingMixin,
):
    """Compile Kida AST to Python code objects.

    The Compiler transforms a Kida Template AST into an `ast.Module`, then
    compiles it to a code object ready for `exec()`. The generated code
    defines a `render(ctx, _blocks=None)` function.

    Attributes:
        _env: Parent Environment (for filter/test access)
        _name: Template name for error messages
        _filename: Source file path for compile()
        _locals: Set of local variable names (loop vars, macro args)
        _blocks: Dict of block_name → Block node (for inheritance)
        _block_counter: Counter for unique variable names

    Node Dispatch:
        Uses O(1) dict lookup for node type → handler:
            ```python
            dispatch = {
                "Data": self._compile_data,
                "Output": self._compile_output,
                "If": self._compile_if,
                ...
            }
            handler = dispatch[type(node).__name__]
            ```

    Line Tracking:
        For nodes that can cause runtime errors (Output, For, If, etc.),
        generates `_get_render_ctx().line = N` before the node's code.
        This updates the ContextVar-stored RenderContext instead of polluting
        the user's ctx dict, enabling rich error messages with source line
        numbers while keeping user context clean.

    Example:
            >>> from kida import Environment
            >>> from kida.compiler import Compiler
            >>> from kida.parser import Parser
            >>> from kida.lexer import tokenize
            >>>
            >>> env = Environment()
            >>> tokens = tokenize("Hello, {{ name }}!")
            >>> parser = Parser(tokens)
            >>> ast = parser.parse()
            >>> compiler = Compiler(env)
            >>> code = compiler.compile(ast, name="greeting.html")
            >>>
            >>> namespace = {"_escape": str, "_str": str, ...}
            >>> exec(code, namespace)
            >>> namespace["render"]({"name": "World"})
            'Hello, World!'

    """

    __slots__ = (
        "_async_mode",
        "_block_counter",
        "_blocks",
        "_env",
        "_filename",
        "_has_async",
        "_locals",
        "_name",
        "_node_dispatch",
        "_streaming",
    )

    def __init__(self, env: Environment):
        self._env = env
        self._name: str | None = None
        self._filename: str | None = None
        # Track local variables (loop variables, etc.) for O(1) direct access
        self._locals: set[str] = set()
        # Track blocks for inheritance
        self._blocks: dict[str, Block] = {}
        # Counter for unique variable names in nested structures
        self._block_counter: int = 0
        # When True, output statements generate yield instead of _append
        self._streaming: bool = False
        # Set True when AsyncFor or Await nodes are compiled (RFC: rfc-async-rendering)
        self._has_async: bool = False
        # When True, generating async function bodies (enables ast.AsyncFor/ast.Await)
        self._async_mode: bool = False

    def _collect_blocks(self, nodes: Sequence[Node]) -> None:
        """Recursively collect all Block nodes from the AST.

        This ensures nested blocks (blocks inside blocks, blocks inside
        conditionals, etc.) are all registered for compilation.
        """
        for node in nodes:
            node_type = type(node).__name__

            if node_type == "Block":
                self._blocks[node.name] = node
                # Recurse into block body to find nested blocks
                self._collect_blocks(node.body)
            elif hasattr(node, "body"):
                # Node has a body (If, For, With, Def, etc.)
                self._collect_blocks(node.body)
                # Check for else/elif bodies
                if hasattr(node, "else_") and node.else_:
                    self._collect_blocks(node.else_)
                if hasattr(node, "empty") and node.empty:
                    self._collect_blocks(node.empty)
                if hasattr(node, "elif_") and node.elif_:
                    for _, elif_body in node.elif_:
                        self._collect_blocks(elif_body)

    def compile(
        self,
        node: TemplateNode,
        name: str | None = None,
        filename: str | None = None,
    ) -> types.CodeType:
        """Compile template AST to code object.

        Args:
            node: Root Template node
            name: Template name for error messages
            filename: Source filename for error messages

        Returns:
            Compiled code object ready for exec()
        """
        self._name = name
        self._filename = filename
        self._locals = set()  # Reset locals for each compilation
        self._block_counter = 0  # Reset counter for each compilation
        self._has_async = False  # Reset async flag for each compilation

        # Generate Python AST
        module = self._compile_template(node)

        # Fix missing locations for Python 3.8+
        ast.fix_missing_locations(module)

        # Compile to code object
        return compile(
            module,
            filename or "<template>",
            "exec",
        )

    def _emit_output(self, value_expr: ast.expr) -> ast.stmt:
        """Generate output statement: yield (streaming) or _append (StringBuilder).

        All output generation in compiled templates flows through this method,
        allowing the compiler to switch between StringBuilder and generator modes.
        """
        if self._streaming:
            return ast.Expr(value=ast.Yield(value=value_expr))
        return ast.Expr(
            value=ast.Call(
                func=ast.Name(id="_append", ctx=ast.Load()),
                args=[value_expr],
                keywords=[],
            ),
        )

    def _compile_template(self, node: TemplateNode) -> ast.Module:
        """Generate Python module from template.

        Produces both StringBuilder functions (render, _block_*) and
        generator functions (render_stream, _block_*_stream) in a single
        module. The StringBuilder path is used by Template.render() and
        the generator path by Template.render_stream().

        When async constructs are detected (AsyncFor, Await), also generates
        async generator functions (render_stream_async, _block_*_stream_async).
        """
        # Generate render + _block_* (StringBuilder mode, _streaming=False)
        render_func = self._make_render_function(node)
        saved_blocks = dict(self._blocks)

        module_body: list[ast.stmt] = []

        for block_name, block_node in saved_blocks.items():
            module_body.append(self._make_block_function(block_name, block_node))
        module_body.append(render_func)

        # Generate render_stream + _block_*_stream (generator mode)
        self._streaming = True
        for block_name, block_node in saved_blocks.items():
            module_body.append(self._make_block_function_stream(block_name, block_node))
        module_body.append(self._make_render_function_stream(node, saved_blocks))
        self._streaming = False

        # Always generate async streaming variants so async blocks from child
        # templates can be dispatched through sync parent templates.
        # RFC: rfc-async-rendering
        if self._has_async:
            # _is_async = True  (module-level flag for Template.is_async)
            module_body.append(
                ast.Assign(
                    targets=[ast.Name(id="_is_async", ctx=ast.Store())],
                    value=ast.Constant(value=True),
                )
            )

        # Generate async streaming functions for ALL templates.
        # For sync templates, these wrap sync code in async def (no yield from).
        # This ensures every parent template has render_stream_async for
        # inheritance chains where a child introduces async constructs.
        self._streaming = True
        self._async_mode = True
        for block_name, block_node in saved_blocks.items():
            module_body.append(
                self._make_block_function_stream_async(block_name, block_node)
            )
        module_body.append(
            self._make_render_function_stream_async(node, saved_blocks)
        )
        self._async_mode = False
        self._streaming = False

        return ast.Module(
            body=module_body,
            type_ignores=[],
        )

    def _make_block_function(self, name: str, block_node: Block) -> ast.FunctionDef:
        """Generate a block function: _block_name(ctx, _blocks) -> str."""
        body: list[ast.stmt] = [
            # _e = _escape
            ast.Assign(
                targets=[ast.Name(id="_e", ctx=ast.Store())],
                value=ast.Name(id="_escape", ctx=ast.Load()),
            ),
            # _s = _str
            ast.Assign(
                targets=[ast.Name(id="_s", ctx=ast.Store())],
                value=ast.Name(id="_str", ctx=ast.Load()),
            ),
            # buf = []
            ast.Assign(
                targets=[ast.Name(id="buf", ctx=ast.Store())],
                value=ast.List(elts=[], ctx=ast.Load()),
            ),
            # _append = buf.append
            ast.Assign(
                targets=[ast.Name(id="_append", ctx=ast.Store())],
                value=ast.Attribute(
                    value=ast.Name(id="buf", ctx=ast.Load()),
                    attr="append",
                    ctx=ast.Load(),
                ),
            ),
            # _scope_stack = [] (for block-scoped variables)
            ast.Assign(
                targets=[ast.Name(id="_scope_stack", ctx=ast.Store())],
                value=ast.List(elts=[], ctx=ast.Load()),
            ),
        ]

        # Compile block body with f-string coalescing
        body.extend(self._compile_body_with_coalescing(list(block_node.body)))

        # return ''.join(buf)
        body.append(
            ast.Return(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Constant(value=""),
                        attr="join",
                        ctx=ast.Load(),
                    ),
                    args=[ast.Name(id="buf", ctx=ast.Load())],
                    keywords=[],
                ),
            )
        )

        return ast.FunctionDef(
            name=f"_block_{name}",
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg="ctx"), ast.arg(arg="_blocks")],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            body=body,
            decorator_list=[],
            returns=None,
        )

    def _make_render_function(self, node: TemplateNode) -> ast.FunctionDef:
        """Generate the render(ctx, _blocks=None) function.

        Optimization: Cache global function references as locals for
        O(1) LOAD_FAST instead of O(1) LOAD_GLOBAL + hash lookup.

        For templates with extends:
            def render(ctx, _blocks=None):
                if _blocks is None: _blocks = {}
                # Register child blocks
                _blocks.setdefault('name', _block_name)
                # Render parent with blocks
                return _extends('parent.html', ctx, _blocks)
        """
        # Reset blocks dict for this compilation
        self._blocks = {}

        # First pass: recursively collect ALL blocks (including nested) and find extends
        extends_node: Extends | None = None
        self._collect_blocks(node.body)
        for child in node.body:
            if type(child).__name__ == "Extends":
                extends_node = child  # type: ignore[assignment]
                break

        body: list[ast.stmt] = []

        # Initialize _blocks parameter: if _blocks is None: _blocks = {}
        body.append(
            ast.If(
                test=ast.Compare(
                    left=ast.Name(id="_blocks", ctx=ast.Load()),
                    ops=[ast.Is()],
                    comparators=[ast.Constant(value=None)],
                ),
                body=[
                    ast.Assign(
                        targets=[ast.Name(id="_blocks", ctx=ast.Store())],
                        value=ast.Dict(keys=[], values=[]),
                    )
                ],
                orelse=[],
            )
        )

        # Initialize scope stack for block-scoped variables
        body.append(
            ast.Assign(
                targets=[ast.Name(id="_scope_stack", ctx=ast.Store())],
                value=ast.List(elts=[], ctx=ast.Load()),
            )
        )

        if extends_node:
            # Template with inheritance - collect blocks and delegate to parent

            # First, execute top-level statements that modify context (imports, sets, etc.)
            # These need to run before blocks are called so imported macros are available.
            # We compile FromImport, Import, Set, Let, Export, and Def nodes at the top level.
            for child in node.body:
                child_type = type(child).__name__
                if child_type in (
                    "FromImport",
                    "Import",
                    "Set",
                    "Let",
                    "Export",
                    "Def",
                    "Do",
                ):
                    body.extend(self._compile_node(child))

            # For each block: _blocks.setdefault('name', block_func)
            # Block functions are added to module namespace during compilation
            body.extend(
                ast.Expr(
                    value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id="_blocks", ctx=ast.Load()),
                            attr="setdefault",
                            ctx=ast.Load(),
                        ),
                        args=[
                            ast.Constant(value=block_name),
                            ast.Name(id=f"_block_{block_name}", ctx=ast.Load()),
                        ],
                        keywords=[],
                    ),
                )
                for block_name in self._blocks
            )

            # return _extends('parent.html', ctx, _blocks)
            body.append(
                ast.Return(
                    value=ast.Call(
                        func=ast.Name(id="_extends", ctx=ast.Load()),
                        args=[
                            self._compile_expr(extends_node.template),
                            ast.Name(id="ctx", ctx=ast.Load()),
                            ast.Name(id="_blocks", ctx=ast.Load()),
                        ],
                        keywords=[],
                    ),
                )
            )
        else:
            # No inheritance - render directly
            # Local function cache for hot-path operations
            body.append(
                ast.Assign(
                    targets=[ast.Name(id="_e", ctx=ast.Store())],
                    value=ast.Name(id="_escape", ctx=ast.Load()),
                )
            )
            body.append(
                ast.Assign(
                    targets=[ast.Name(id="_s", ctx=ast.Store())],
                    value=ast.Name(id="_str", ctx=ast.Load()),
                )
            )

            # buf = []
            body.append(
                ast.Assign(
                    targets=[ast.Name(id="buf", ctx=ast.Store())],
                    value=ast.List(elts=[], ctx=ast.Load()),
                )
            )

            # _append = buf.append (cache method lookup)
            body.append(
                ast.Assign(
                    targets=[ast.Name(id="_append", ctx=ast.Store())],
                    value=ast.Attribute(
                        value=ast.Name(id="buf", ctx=ast.Load()),
                        attr="append",
                        ctx=ast.Load(),
                    ),
                )
            )

            # Compile template body with f-string coalescing
            body.extend(self._compile_body_with_coalescing(list(node.body)))

            # return ''.join(buf)
            body.append(
                ast.Return(
                    value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Constant(value=""),
                            attr="join",
                            ctx=ast.Load(),
                        ),
                        args=[ast.Name(id="buf", ctx=ast.Load())],
                        keywords=[],
                    ),
                )
            )

        return ast.FunctionDef(
            name="render",
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg="ctx"), ast.arg(arg="_blocks")],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[ast.Constant(value=None)],  # _blocks=None
            ),
            body=body,
            decorator_list=[],
            returns=None,
        )

    def _make_block_function_stream(self, name: str, block_node: Block) -> ast.FunctionDef:
        """Generate a streaming block: _block_name_stream(ctx, _blocks) -> Generator[str]."""
        body: list[ast.stmt] = [
            # _e = _escape
            ast.Assign(
                targets=[ast.Name(id="_e", ctx=ast.Store())],
                value=ast.Name(id="_escape", ctx=ast.Load()),
            ),
            # _s = _str
            ast.Assign(
                targets=[ast.Name(id="_s", ctx=ast.Store())],
                value=ast.Name(id="_str", ctx=ast.Load()),
            ),
            # _scope_stack = []
            ast.Assign(
                targets=[ast.Name(id="_scope_stack", ctx=ast.Store())],
                value=ast.List(elts=[], ctx=ast.Load()),
            ),
        ]

        # Compile block body with streaming yields
        body.extend(self._compile_body_with_coalescing(list(block_node.body)))

        # Ensure generator semantics: unreachable yield after return
        # guarantees Python treats this as a generator even for empty blocks.
        body.append(ast.Return(value=None))
        body.append(ast.Expr(value=ast.Yield(value=None)))

        return ast.FunctionDef(
            name=f"_block_{name}_stream",
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg="ctx"), ast.arg(arg="_blocks")],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            body=body,
            decorator_list=[],
            returns=None,
        )

    def _make_render_function_stream(
        self, node: TemplateNode, blocks: dict[str, Block]
    ) -> ast.FunctionDef:
        """Generate render_stream(ctx, _blocks=None) generator function.

        For templates with extends:
            yield from _extends_stream('parent.html', ctx, _blocks)

        For templates without extends:
            yield chunks directly
        """
        # Find extends node
        extends_node: Extends | None = None
        for child in node.body:
            if type(child).__name__ == "Extends":
                extends_node = child  # type: ignore[assignment]
                break

        body: list[ast.stmt] = []

        # if _blocks is None: _blocks = {}
        body.append(
            ast.If(
                test=ast.Compare(
                    left=ast.Name(id="_blocks", ctx=ast.Load()),
                    ops=[ast.Is()],
                    comparators=[ast.Constant(value=None)],
                ),
                body=[
                    ast.Assign(
                        targets=[ast.Name(id="_blocks", ctx=ast.Store())],
                        value=ast.Dict(keys=[], values=[]),
                    )
                ],
                orelse=[],
            )
        )

        # _scope_stack = []
        body.append(
            ast.Assign(
                targets=[ast.Name(id="_scope_stack", ctx=ast.Store())],
                value=ast.List(elts=[], ctx=ast.Load()),
            )
        )

        if extends_node:
            # Execute top-level statements (imports, sets, etc.)
            for child in node.body:
                child_type = type(child).__name__
                if child_type in (
                    "FromImport",
                    "Import",
                    "Set",
                    "Let",
                    "Export",
                    "Def",
                    "Do",
                ):
                    body.extend(self._compile_node(child))

            # Register streaming block functions
            for block_name in blocks:
                body.append(
                    ast.Expr(
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id="_blocks", ctx=ast.Load()),
                                attr="setdefault",
                                ctx=ast.Load(),
                            ),
                            args=[
                                ast.Constant(value=block_name),
                                ast.Name(
                                    id=f"_block_{block_name}_stream", ctx=ast.Load()
                                ),
                            ],
                            keywords=[],
                        ),
                    )
                )

            # yield from _extends_stream('parent.html', ctx, _blocks)
            body.append(
                ast.Expr(
                    value=ast.YieldFrom(
                        value=ast.Call(
                            func=ast.Name(id="_extends_stream", ctx=ast.Load()),
                            args=[
                                self._compile_expr(extends_node.template),
                                ast.Name(id="ctx", ctx=ast.Load()),
                                ast.Name(id="_blocks", ctx=ast.Load()),
                            ],
                            keywords=[],
                        ),
                    ),
                )
            )
        else:
            # No inheritance - render directly with streaming
            body.append(
                ast.Assign(
                    targets=[ast.Name(id="_e", ctx=ast.Store())],
                    value=ast.Name(id="_escape", ctx=ast.Load()),
                )
            )
            body.append(
                ast.Assign(
                    targets=[ast.Name(id="_s", ctx=ast.Store())],
                    value=ast.Name(id="_str", ctx=ast.Load()),
                )
            )

            body.extend(self._compile_body_with_coalescing(list(node.body)))

        # Ensure generator semantics
        body.append(ast.Return(value=None))
        body.append(ast.Expr(value=ast.Yield(value=None)))

        return ast.FunctionDef(
            name="render_stream",
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg="ctx"), ast.arg(arg="_blocks")],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[ast.Constant(value=None)],
            ),
            body=body,
            decorator_list=[],
            returns=None,
        )

    def _make_block_function_stream_async(
        self, name: str, block_node: Block
    ) -> ast.AsyncFunctionDef:
        """Generate async streaming block: _block_name_stream_async(ctx, _blocks).

        Mirrors _make_block_function_stream() but produces an async generator
        function (async def + yield). Used when the template contains async
        constructs (AsyncFor, Await).

        Part of RFC: rfc-async-rendering.
        """
        body: list[ast.stmt] = [
            ast.Assign(
                targets=[ast.Name(id="_e", ctx=ast.Store())],
                value=ast.Name(id="_escape", ctx=ast.Load()),
            ),
            ast.Assign(
                targets=[ast.Name(id="_s", ctx=ast.Store())],
                value=ast.Name(id="_str", ctx=ast.Load()),
            ),
            ast.Assign(
                targets=[ast.Name(id="_scope_stack", ctx=ast.Store())],
                value=ast.List(elts=[], ctx=ast.Load()),
            ),
        ]

        body.extend(self._compile_body_with_coalescing(list(block_node.body)))

        # Ensure async generator semantics
        body.append(ast.Return(value=None))
        body.append(ast.Expr(value=ast.Yield(value=None)))

        return ast.AsyncFunctionDef(
            name=f"_block_{name}_stream_async",
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg="ctx"), ast.arg(arg="_blocks")],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            body=body,
            decorator_list=[],
            returns=None,
        )

    def _make_render_function_stream_async(
        self, node: TemplateNode, blocks: dict[str, Block]
    ) -> ast.AsyncFunctionDef:
        """Generate async render_stream_async(ctx, _blocks=None) function.

        Mirrors _make_render_function_stream() but produces an async generator
        for native async iteration over AsyncFor loops and Await expressions.

        For templates with extends:
            async for chunk in _extends_stream_async(parent, ctx, _blocks):
                yield chunk

        For templates without extends:
            yield chunks directly via async generator

        Part of RFC: rfc-async-rendering.
        """
        extends_node: Extends | None = None
        for child in node.body:
            if type(child).__name__ == "Extends":
                extends_node = child  # type: ignore[assignment]
                break

        body: list[ast.stmt] = []

        # if _blocks is None: _blocks = {}
        body.append(
            ast.If(
                test=ast.Compare(
                    left=ast.Name(id="_blocks", ctx=ast.Load()),
                    ops=[ast.Is()],
                    comparators=[ast.Constant(value=None)],
                ),
                body=[
                    ast.Assign(
                        targets=[ast.Name(id="_blocks", ctx=ast.Store())],
                        value=ast.Dict(keys=[], values=[]),
                    )
                ],
                orelse=[],
            )
        )

        # _scope_stack = []
        body.append(
            ast.Assign(
                targets=[ast.Name(id="_scope_stack", ctx=ast.Store())],
                value=ast.List(elts=[], ctx=ast.Load()),
            )
        )

        if extends_node:
            # Execute top-level statements
            for child in node.body:
                child_type = type(child).__name__
                if child_type in (
                    "FromImport",
                    "Import",
                    "Set",
                    "Let",
                    "Export",
                    "Def",
                    "Do",
                ):
                    body.extend(self._compile_node(child))

            # Register async streaming block functions
            for block_name in blocks:
                body.append(
                    ast.Expr(
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id="_blocks", ctx=ast.Load()),
                                attr="setdefault",
                                ctx=ast.Load(),
                            ),
                            args=[
                                ast.Constant(value=block_name),
                                ast.Name(
                                    id=f"_block_{block_name}_stream_async",
                                    ctx=ast.Load(),
                                ),
                            ],
                            keywords=[],
                        ),
                    )
                )

            # async for chunk in _extends_stream_async(parent, ctx, _blocks):
            #     yield chunk
            # Note: yield from doesn't work with async generators, so we use
            # async for + yield instead
            body.append(
                ast.AsyncFor(
                    target=ast.Name(id="_chunk", ctx=ast.Store()),
                    iter=ast.Call(
                        func=ast.Name(id="_extends_stream_async", ctx=ast.Load()),
                        args=[
                            self._compile_expr(extends_node.template),
                            ast.Name(id="ctx", ctx=ast.Load()),
                            ast.Name(id="_blocks", ctx=ast.Load()),
                        ],
                        keywords=[],
                    ),
                    body=[
                        ast.Expr(value=ast.Yield(value=ast.Name(id="_chunk", ctx=ast.Load())))
                    ],
                    orelse=[],
                )
            )
        else:
            # No inheritance - render directly with async streaming
            body.append(
                ast.Assign(
                    targets=[ast.Name(id="_e", ctx=ast.Store())],
                    value=ast.Name(id="_escape", ctx=ast.Load()),
                )
            )
            body.append(
                ast.Assign(
                    targets=[ast.Name(id="_s", ctx=ast.Store())],
                    value=ast.Name(id="_str", ctx=ast.Load()),
                )
            )

            body.extend(self._compile_body_with_coalescing(list(node.body)))

        # Ensure async generator semantics
        body.append(ast.Return(value=None))
        body.append(ast.Expr(value=ast.Yield(value=None)))

        return ast.AsyncFunctionDef(
            name="render_stream_async",
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg="ctx"), ast.arg(arg="_blocks")],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[ast.Constant(value=None)],
            ),
            body=body,
            decorator_list=[],
            returns=None,
        )

    # Node types that can cause runtime errors and should track line numbers
    _LINE_TRACKED_NODES = frozenset(
        {
            "Output",  # Expression evaluation
            "For",  # Iterator access, filter application
            "AsyncFor",  # Async iterator access (RFC: rfc-async-rendering)
            "If",  # Boolean coercion, attribute access
            "Match",  # Pattern matching
            "Set",  # Expression evaluation
            "Let",  # Expression evaluation
            "CallBlock",  # Function calls
            "Do",  # Side-effect expressions
            "WithConditional",  # Conditional with block (expression evaluation)
            "Include",  # Template inclusion (errors in included templates)
            "FromImport",  # Template import (macro/function access)
            "Import",  # Template import
            "Embed",  # Template embedding
        }
    )

    def _make_line_marker(self, lineno: int) -> ast.stmt:
        """Generate RenderContext line update for error tracking.

        Generates: _get_render_ctx().line = lineno

        This updates the ContextVar-stored RenderContext instead of
        polluting the user's ctx dict.

        RFC: kida-contextvar-patterns
        """
        return ast.Assign(
            targets=[
                ast.Attribute(
                    value=ast.Call(
                        func=ast.Name(id="_get_render_ctx", ctx=ast.Load()),
                        args=[],
                        keywords=[],
                    ),
                    attr="line",
                    ctx=ast.Store(),
                )
            ],
            value=ast.Constant(value=lineno),
        )

    def _compile_node(self, node: Node) -> list[ast.stmt]:
        """Compile a single AST node to Python statements.

        Complexity: O(1) type dispatch using class name lookup.

        For nodes that can cause runtime errors, injects a line marker
        statement (ctx['_line'] = N) before the node's code. This enables
        rich error messages with source line numbers.
        """
        node_type = type(node).__name__

        # Inject line marker for risky nodes (only if they have lineno)
        stmts: list[ast.stmt] = []
        if node_type in self._LINE_TRACKED_NODES and hasattr(node, "lineno"):
            stmts.append(self._make_line_marker(node.lineno))

        # Dispatch table - O(1) lookup instead of isinstance chain
        dispatch = self._get_node_dispatch()
        handler = dispatch.get(node_type)
        if handler:
            stmts.extend(handler(node))

        return stmts

    def _get_node_dispatch(self) -> dict[str, Callable]:
        """Get node type dispatch table (cached on first call)."""
        if not hasattr(self, "_node_dispatch"):
            self._node_dispatch = {
                "Data": self._compile_data,
                "Output": self._compile_output,
                "If": self._compile_if,
                "For": self._compile_for,
                "AsyncFor": self._compile_async_for,  # RFC: rfc-async-rendering
                "While": self._compile_while,
                "Match": self._compile_match,
                "Set": self._compile_set,
                "Let": self._compile_let,
                "Export": self._compile_export,
                "Import": self._compile_import,
                "Include": self._compile_include,
                "Block": self._compile_block,
                "Def": self._compile_def,
                "CallBlock": self._compile_call_block,
                "Slot": self._compile_slot,
                "FromImport": self._compile_from_import,
                "With": self._compile_with,
                "WithConditional": self._compile_with_conditional,
                "Raw": self._compile_raw,
                "Capture": self._compile_capture,
                "Cache": self._compile_cache,
                "FilterBlock": self._compile_filter_block,
                # RFC: kida-modern-syntax-features
                "Break": self._compile_break,
                "Continue": self._compile_continue,
                "Spaceless": self._compile_spaceless,
                "Embed": self._compile_embed,
            }
        return self._node_dispatch
