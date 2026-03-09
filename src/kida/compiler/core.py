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
import re
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, cast

from kida.compiler.coalescing import FStringCoalescingMixin
from kida.compiler.expressions import ExpressionCompilationMixin
from kida.compiler.statements import StatementCompilationMixin
from kida.compiler.utils import OperatorUtilsMixin
from kida.nodes import Block, Region

_BLOCK_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

if TYPE_CHECKING:
    import types

    from kida.environment import Environment
    from kida.nodes import Block, Extends, Node, Region
    from kida.nodes import Template as TemplateNode

_TOP_LEVEL_STATEMENTS = frozenset(
    {"FromImport", "Import", "Set", "Let", "Export", "Def", "Do", "Region"}
)


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
        "_def_caller_stack",
        "_def_names",
        "_env",
        "_filename",
        "_has_async",
        "_locals",
        "_loop_vars",
        "_name",
        "_node_dispatch",
        "_outer_caller_expr",
        "_streaming",
    )

    def __init__(self, env: Environment):
        self._env = env
        self._name: str | None = None
        self._filename: str | None = None
        # Track local variables (loop variables, etc.) for O(1) direct access
        self._locals: set[str] = set()
        # Track blocks for inheritance
        self._blocks: dict[str, Block | Region] = {}
        # Counter for unique variable names in nested structures
        self._block_counter: int = 0
        # When True, output statements generate yield instead of _append
        self._streaming: bool = False
        # Set True when AsyncFor or Await nodes are compiled (RFC: rfc-async-rendering)
        self._has_async: bool = False
        # When True, generating async function bodies (enables ast.AsyncFor/ast.Await)
        self._async_mode: bool = False
        # Track {% def %} names for profiling instrumentation
        self._def_names: set[str] = set()
        # Track loop variables for include scope propagation
        self._loop_vars: set[str] = set()
        # Lexical caller scoping: def → call → caller() (reset in compile())
        self._def_caller_stack: list[ast.expr] = []
        self._outer_caller_expr: ast.expr | None = None

    def _get_literal_extends_target(self, node: TemplateNode) -> str | None:
        """Return literal extends target if template uses {% extends "literal" %}, else None."""
        from kida.nodes import Const, Extends

        for child in node.body:
            if isinstance(child, Extends):
                if isinstance(child.template, Const) and isinstance(child.template.value, str):
                    return child.template.value
                return None
        return None

    def _collect_blocks(self, nodes: Sequence[Node]) -> None:
        """Recursively collect all Block nodes from the AST.

        This ensures nested blocks (blocks inside blocks, blocks inside
        conditionals, etc.) are all registered for compilation.
        """
        from kida.environment.exceptions import TemplateSyntaxError
        from kida.nodes import Block, CallBlock, Def, Region, Slot, SlotBlock

        for node in nodes:
            if isinstance(node, Block):
                if not _BLOCK_NAME_RE.match(node.name):
                    raise TemplateSyntaxError(
                        f"Invalid block name '{node.name}': must be identifier-like "
                        "(e.g. [a-zA-Z_][a-zA-Z0-9_]*)",
                        lineno=node.lineno,
                        name=self._name,
                        filename=self._filename,
                    )
                if node.name in self._blocks and isinstance(self._blocks[node.name], Region):
                    raise TemplateSyntaxError(
                        f"Duplicate block/region name '{node.name}'",
                        lineno=node.lineno,
                        name=self._name,
                        filename=self._filename,
                    )
                self._blocks[node.name] = node
                # Recurse into block body to find nested blocks
                self._collect_blocks(node.body)
            elif isinstance(node, Def):
                if not _BLOCK_NAME_RE.match(node.name):
                    raise TemplateSyntaxError(
                        f"Invalid def name '{node.name}': must be identifier-like "
                        "(e.g. [a-zA-Z_][a-zA-Z0-9_]*)",
                        lineno=node.lineno,
                        name=self._name,
                        filename=self._filename,
                    )
                self._collect_blocks(node.body)
            elif isinstance(node, Region):
                if not _BLOCK_NAME_RE.match(node.name):
                    raise TemplateSyntaxError(
                        f"Invalid region name '{node.name}': must be identifier-like "
                        "(e.g. [a-zA-Z_][a-zA-Z0-9_]*)",
                        lineno=node.lineno,
                        name=self._name,
                        filename=self._filename,
                    )
                if node.name in self._blocks:
                    raise TemplateSyntaxError(
                        f"Duplicate block/region name '{node.name}'",
                        lineno=node.lineno,
                        name=self._name,
                        filename=self._filename,
                    )
                self._blocks[node.name] = node  # Region stored as block for registration
                self._collect_blocks(node.body)
            elif isinstance(node, CallBlock):
                for slot_name in node.slots:
                    if slot_name != "default" and not _BLOCK_NAME_RE.match(slot_name):
                        raise TemplateSyntaxError(
                            f"Invalid slot name '{slot_name}': must be identifier-like "
                            "(e.g. [a-zA-Z_][a-zA-Z0-9_]*)",
                            lineno=node.lineno,
                            name=self._name,
                            filename=self._filename,
                        )
                for slot_body in node.slots.values():
                    self._collect_blocks(slot_body)
            elif isinstance(node, SlotBlock):
                if node.name != "default" and not _BLOCK_NAME_RE.match(node.name):
                    raise TemplateSyntaxError(
                        f"Invalid slot name '{node.name}': must be identifier-like "
                        "(e.g. [a-zA-Z_][a-zA-Z0-9_]*)",
                        lineno=node.lineno,
                        name=self._name,
                        filename=self._filename,
                    )
                self._collect_blocks(node.body)
            elif isinstance(node, Slot):
                if node.name != "default" and not _BLOCK_NAME_RE.match(node.name):
                    raise TemplateSyntaxError(
                        f"Invalid slot name '{node.name}': must be identifier-like "
                        "(e.g. [a-zA-Z_][a-zA-Z0-9_]*)",
                        lineno=node.lineno,
                        name=self._name,
                        filename=self._filename,
                    )
            elif hasattr(node, "body"):
                # Node has a body (If, For, With, Def, etc.)
                body = node.body
                if isinstance(body, Sequence):
                    self._collect_blocks(cast("Sequence[Node]", body))
                # Check for else/elif bodies
                else_ = getattr(node, "else_", None)
                if isinstance(else_, Sequence):
                    self._collect_blocks(cast("Sequence[Node]", else_))
                empty = getattr(node, "empty", None)
                if isinstance(empty, Sequence):
                    self._collect_blocks(cast("Sequence[Node]", empty))
                elif_ = getattr(node, "elif_", None)
                if elif_:
                    for _, elif_body in elif_:
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
        self._def_caller_stack = []  # Lexical caller scoping: def → call → caller()
        self._outer_caller_expr = None  # Set when compiling call body inside def

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

        # Emit _extends_target for literal-string {% extends %} (inherited block lookup)
        extends_target = self._get_literal_extends_target(node)
        if extends_target is not None:
            module_body.append(
                ast.Assign(
                    targets=[ast.Name(id="_extends_target", ctx=ast.Store())],
                    value=ast.Constant(value=extends_target),
                )
            )

        # Emit region callables (module-level) before _globals_setup
        for block_name, block_node in saved_blocks.items():
            if isinstance(block_node, Region):
                module_body.append(self._make_region_function(block_name, block_node))

        # Detect {% globals %} blocks and compile _globals_setup function
        globals_setup = self._make_globals_setup(node)
        if globals_setup is not None:
            module_body.append(globals_setup)

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
            module_body.append(self._make_block_function_stream_async(block_name, block_node))
        module_body.append(self._make_render_function_stream_async(node, saved_blocks))
        self._async_mode = False
        self._streaming = False

        return ast.Module(
            body=module_body,
            type_ignores=[],
        )

    def _make_globals_setup(self, node: TemplateNode) -> ast.FunctionDef | None:
        """Generate _globals_setup(ctx) from {% globals %}, {% imports %}, and top-level imports.

        Scans the template body for:
        1. Top-level FromImport and Import nodes (so render_block has macros in scope)
        2. Globals and Imports nodes (macros/variables for block context)

        This function is called by render_block() to inject macros and variables
        into the block's context. Returns None if neither globals nor top-level
        imports exist.
        """
        from kida.nodes import Def, FromImport, Globals, Import, Imports

        setup_nodes = [n for n in node.body if isinstance(n, (Globals, Imports))]
        top_level_imports = [n for n in node.body if isinstance(n, (FromImport, Import))]
        top_level_defs = [n for n in node.body if isinstance(n, Def)]
        top_level_regions = [n for n in node.body if isinstance(n, Region)]
        if (
            not setup_nodes
            and not top_level_imports
            and not top_level_defs
            and not top_level_regions
        ):
            return None

        # Preamble: scope stack, buf, _append, _e, _s, _acc (needed by imports/globals)
        body_stmts: list[ast.stmt] = self._make_runtime_preamble(
            include_scope_stack=True,
            include_escape_str=True,
            include_buf_append=True,
            include_acc=True,
            acc_none=True,
        )

        # Top-level imports first (so macros are in ctx for blocks)
        for imp_node in top_level_imports:
            body_stmts.extend(self._compile_node(imp_node))

        # Top-level defs (so render_block has macros in scope)
        for def_node in top_level_defs:
            body_stmts.extend(self._compile_node(def_node))

        # Top-level regions (ctx['name'] = _region_name for render_block)
        body_stmts.extend(
            ast.Assign(
                targets=[
                    ast.Subscript(
                        value=ast.Name(id="ctx", ctx=ast.Load()),
                        slice=ast.Constant(value=region_node.name),
                        ctx=ast.Store(),
                    )
                ],
                value=ast.Name(id=f"_region_{region_node.name}", ctx=ast.Load()),
            )
            for region_node in top_level_regions
        )

        for setup_node in setup_nodes:
            for child in setup_node.body:
                body_stmts.extend(self._compile_node(child))

        return ast.FunctionDef(
            name="_globals_setup",
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg="ctx")],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
            ),
            body=body_stmts or [ast.Pass()],
            decorator_list=[],
        )

    def _make_runtime_preamble(
        self,
        *,
        include_blocks_guard: bool = False,
        include_scope_stack: bool = False,
        include_escape_str: bool = False,
        include_buf_append: bool = False,
        include_acc: bool = False,
        acc_none: bool = False,
    ) -> list[ast.stmt]:
        """Build shared runtime locals preamble for generated functions."""
        stmts: list[ast.stmt] = []
        if include_blocks_guard:
            stmts.append(
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
        if include_scope_stack:
            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id="_scope_stack", ctx=ast.Store())],
                    value=ast.List(elts=[], ctx=ast.Load()),
                )
            )
        if include_escape_str:
            stmts.extend(
                [
                    ast.Assign(
                        targets=[ast.Name(id="_e", ctx=ast.Store())],
                        value=ast.Name(id="_escape", ctx=ast.Load()),
                    ),
                    ast.Assign(
                        targets=[ast.Name(id="_s", ctx=ast.Store())],
                        value=ast.Name(id="_str", ctx=ast.Load()),
                    ),
                ]
            )
        if include_buf_append:
            stmts.extend(
                [
                    ast.Assign(
                        targets=[ast.Name(id="buf", ctx=ast.Store())],
                        value=ast.List(elts=[], ctx=ast.Load()),
                    ),
                    ast.Assign(
                        targets=[ast.Name(id="_append", ctx=ast.Store())],
                        value=ast.Attribute(
                            value=ast.Name(id="buf", ctx=ast.Load()),
                            attr="append",
                            ctx=ast.Load(),
                        ),
                    ),
                ]
            )
        if include_acc:
            acc_value: ast.expr = (
                ast.Constant(value=None)
                if acc_none
                else ast.Call(
                    func=ast.Name(id="_get_accumulator", ctx=ast.Load()),
                    args=[],
                    keywords=[],
                )
            )
            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id="_acc", ctx=ast.Store())],
                    value=acc_value,
                )
            )
        return stmts

    def _make_block_preamble(self, streaming: bool) -> list[ast.stmt]:
        """Common setup stmts for block functions.

        Non-streaming adds buf and _append for StringBuilder.
        """
        return self._make_runtime_preamble(
            include_scope_stack=True,
            include_escape_str=True,
            include_buf_append=not streaming,
            include_acc=True,
        )

    def _make_region_block_function(self, name: str, region_node: Region) -> ast.FunctionDef:
        """Generate block wrapper that delegates to region callable with ctx params."""
        param_names = [p.name for p in region_node.params]
        n_defaults = len(region_node.defaults)
        n_required = len(param_names) - n_defaults

        # Build call: ctx['name'](param=ctx.get/ctx[], ..., _outer_ctx=ctx)
        keywords: list[ast.keyword] = []
        for i, param_name in enumerate(param_names):
            if i < n_required:
                # Required param: _lookup(ctx, name) raises UndefinedError if missing
                val = ast.Call(
                    func=ast.Name(id="_lookup", ctx=ast.Load()),
                    args=[
                        ast.Name(id="ctx", ctx=ast.Load()),
                        ast.Constant(value=param_name),
                    ],
                    keywords=[],
                )
            else:
                # Optional param: ctx.get('param', default)
                default_val = self._compile_expr(region_node.defaults[i - n_required])
                val = ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="ctx", ctx=ast.Load()),
                        attr="get",
                        ctx=ast.Load(),
                    ),
                    args=[ast.Constant(value=param_name), default_val],
                    keywords=[],
                )
            keywords.append(ast.keyword(arg=param_name, value=val))
        keywords.append(ast.keyword(arg="_outer_ctx", value=ast.Name(id="ctx", ctx=ast.Load())))

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
            body=[
                ast.Return(
                    value=ast.Call(
                        func=ast.Subscript(
                            value=ast.Name(id="ctx", ctx=ast.Load()),
                            slice=ast.Constant(value=name),
                            ctx=ast.Load(),
                        ),
                        args=[],
                        keywords=keywords,
                    ),
                )
            ],
            decorator_list=[],
            returns=None,
        )

    def _make_block_function(self, name: str, block_node: Block | Region) -> ast.FunctionDef:
        """Generate a block function: _block_name(ctx, _blocks) -> str."""
        if isinstance(block_node, Region):
            return self._make_region_block_function(name, block_node)

        body: list[ast.stmt] = self._make_block_preamble(streaming=False)

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

    def _make_render_preamble(self) -> list[ast.stmt]:
        """Shared init block for render functions: if _blocks, _scope_stack, _acc."""
        return self._make_runtime_preamble(
            include_blocks_guard=True,
            include_scope_stack=True,
            include_acc=True,
        )

    def _make_render_extends_body(
        self,
        node: TemplateNode,
        extends_node: Extends,
        block_names: dict[str, Block | Region],
        block_suffix: str,
        extends_helper: str,
    ) -> list[ast.stmt]:
        """Top-level statements, block registration, and extends return/yield."""
        body: list[ast.stmt] = []
        for child in node.body:
            child_type = type(child).__name__
            if child_type in _TOP_LEVEL_STATEMENTS:
                body.extend(self._compile_node(child))
        body.extend(
            ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="_blocks", ctx=ast.Load()),
                        attr="setdefault",
                        ctx=ast.Load(),
                    ),
                    args=[
                        ast.Constant(value=bn),
                        ast.Name(id=f"_block_{bn}{block_suffix}", ctx=ast.Load()),
                    ],
                    keywords=[],
                ),
            )
            for bn in block_names
        )
        extend_call = ast.Call(
            func=ast.Name(id=extends_helper, ctx=ast.Load()),
            args=[
                self._compile_expr(extends_node.template),
                ast.Name(id="ctx", ctx=ast.Load()),
                ast.Name(id="_blocks", ctx=ast.Load()),
            ],
            keywords=[],
        )
        if extends_helper == "_extends":
            body.append(ast.Return(value=extend_call))
        elif extends_helper == "_extends_stream":
            body.append(ast.Expr(value=ast.YieldFrom(value=extend_call)))
        else:
            body.append(
                ast.AsyncFor(
                    target=ast.Name(id="_chunk", ctx=ast.Store()),
                    iter=extend_call,
                    body=[ast.Expr(value=ast.Yield(value=ast.Name(id="_chunk", ctx=ast.Load())))],
                    orelse=[],
                )
            )
        return body

    def _make_render_direct_body(self, node: TemplateNode, streaming: bool) -> list[ast.stmt]:
        """No-extends path: buf setup (if not streaming), body compile, return vs yield."""
        body: list[ast.stmt] = self._make_runtime_preamble(
            include_escape_str=True,
            include_buf_append=not streaming,
        )
        body.extend(self._compile_body_with_coalescing(list(node.body)))
        if streaming:
            body.append(ast.Return(value=None))
            body.append(ast.Expr(value=ast.Yield(value=None)))
        else:
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
        return body

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
        self._blocks = {}
        extends_node: Extends | None = None
        self._collect_blocks(node.body)
        for child in node.body:
            if type(child).__name__ == "Extends":
                extends_node = child  # type: ignore[assignment]
                break

        body: list[ast.stmt] = self._make_render_preamble()
        if extends_node:
            body.extend(
                self._make_render_extends_body(node, extends_node, self._blocks, "", "_extends")
            )
        else:
            body.extend(self._make_render_direct_body(node, streaming=False))

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

    def _make_block_function_stream(self, name: str, block_node: Block | Region) -> ast.FunctionDef:
        """Generate a streaming block: _block_name_stream(ctx, _blocks) -> Generator[str]."""
        if isinstance(block_node, Region):
            return self._make_region_block_function_stream(name, block_node)

        body: list[ast.stmt] = self._make_block_preamble(streaming=True)

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
        self, node: TemplateNode, blocks: dict[str, Block | Region]
    ) -> ast.FunctionDef:
        """Generate render_stream(ctx, _blocks=None) generator function.

        For templates with extends:
            yield from _extends_stream('parent.html', ctx, _blocks)

        For templates without extends:
            yield chunks directly
        """
        extends_node: Extends | None = None
        for child in node.body:
            if type(child).__name__ == "Extends":
                extends_node = child  # type: ignore[assignment]
                break

        body: list[ast.stmt] = self._make_render_preamble()
        if extends_node:
            body.extend(
                self._make_render_extends_body(
                    node, extends_node, blocks, "_stream", "_extends_stream"
                )
            )
        else:
            body.extend(self._make_render_direct_body(node, streaming=True))

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

    def _make_region_block_function_stream(self, name: str, region_node: Region) -> ast.FunctionDef:
        """Streaming block wrapper for region — yields callable result."""
        param_names = [p.name for p in region_node.params]
        n_defaults = len(region_node.defaults)
        n_required = len(param_names) - n_defaults
        keywords: list[ast.keyword] = []
        for i, param_name in enumerate(param_names):
            if i < n_required:
                # Required param: _lookup(ctx, name) raises UndefinedError if missing
                val = ast.Call(
                    func=ast.Name(id="_lookup", ctx=ast.Load()),
                    args=[
                        ast.Name(id="ctx", ctx=ast.Load()),
                        ast.Constant(value=param_name),
                    ],
                    keywords=[],
                )
            else:
                default_val = self._compile_expr(region_node.defaults[i - n_required])
                val = ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="ctx", ctx=ast.Load()),
                        attr="get",
                        ctx=ast.Load(),
                    ),
                    args=[ast.Constant(value=param_name), default_val],
                    keywords=[],
                )
            keywords.append(ast.keyword(arg=param_name, value=val))
        keywords.append(ast.keyword(arg="_outer_ctx", value=ast.Name(id="ctx", ctx=ast.Load())))
        call = ast.Call(
            func=ast.Subscript(
                value=ast.Name(id="ctx", ctx=ast.Load()),
                slice=ast.Constant(value=name),
                ctx=ast.Load(),
            ),
            args=[],
            keywords=keywords,
        )
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
            body=[
                ast.Expr(value=ast.Yield(value=call)),
                ast.Return(value=None),
            ],
            decorator_list=[],
            returns=None,
        )

    def _make_region_block_function_stream_async(
        self, name: str, region_node: Region
    ) -> ast.AsyncFunctionDef:
        """Async streaming block wrapper for region."""
        stream_sync = self._make_region_block_function_stream(name, region_node)
        return ast.AsyncFunctionDef(
            name=f"_block_{name}_stream_async",
            args=stream_sync.args,
            body=stream_sync.body,
            decorator_list=[],
            returns=None,
        )

    def _make_block_function_stream_async(
        self, name: str, block_node: Block | Region
    ) -> ast.AsyncFunctionDef:
        """Generate async streaming block: _block_name_stream_async(ctx, _blocks).

        Mirrors _make_block_function_stream() but produces an async generator
        function (async def + yield). Used when the template contains async
        constructs (AsyncFor, Await).

        Part of RFC: rfc-async-rendering.
        """
        if isinstance(block_node, Region):
            return self._make_region_block_function_stream_async(name, block_node)

        body: list[ast.stmt] = self._make_block_preamble(streaming=True)

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
        self, node: TemplateNode, blocks: dict[str, Block | Region]
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

        body: list[ast.stmt] = self._make_render_preamble()
        if extends_node:
            body.extend(
                self._make_render_extends_body(
                    node,
                    extends_node,
                    blocks,
                    "_stream_async",
                    "_extends_stream_async",
                )
            )
        else:
            body.extend(self._make_render_direct_body(node, streaming=True))

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
                "Globals": self._compile_globals,
                "Imports": self._compile_imports,
                "Def": self._compile_def,
                "Region": self._compile_region,
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
                "Flush": self._compile_flush,
                "Embed": self._compile_embed,
            }
        return self._node_dispatch
