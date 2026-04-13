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
from typing import TYPE_CHECKING, Any, ClassVar, cast

from kida.compiler.coalescing import FStringCoalescingMixin
from kida.compiler.expressions import ExpressionCompilationMixin
from kida.compiler.statements import StatementCompilationMixin
from kida.compiler.utils import OperatorUtilsMixin
from kida.nodes import (
    AsyncFor,
    Block,
    CallBlock,
    Capture,
    Def,
    Export,
    Extends,
    For,
    FromImport,
    If,
    Import,
    Let,
    ListComp,
    Match,
    Name,
    Region,
    Set,
    While,
)
from kida.nodes.structure import With, WithConditional

_BLOCK_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

if TYPE_CHECKING:
    import types

    from kida.environment import Environment
    from kida.nodes import Node
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
        "_block_has_append_rebind",
        "_blocks",
        "_cached_pure_filters",
        "_ctx_override",
        "_def_caller_stack",
        "_def_names",
        "_env",
        "_extension_compilers",
        "_filename",
        "_has_async",
        "_last_block_compiled_stmts",
        "_locals",
        "_loop_vars",
        "_name",
        "_node_dispatch",
        "_outer_caller_expr",
        "_scope_override",
        "_streaming",
    )

    # Class-level dispatch table: node type name → unbound method name.
    # Resolved to actual functions once per class (see _ensure_dispatch).
    _NODE_DISPATCH_NAMES: ClassVar[dict[str, str]] = {
        "Data": "_compile_data",
        "Output": "_compile_output",
        "If": "_compile_if",
        "For": "_compile_for",
        "AsyncFor": "_compile_async_for",
        "While": "_compile_while",
        "Try": "_compile_try",
        "Match": "_compile_match",
        "Set": "_compile_set",
        "Let": "_compile_let",
        "Export": "_compile_export",
        "Import": "_compile_import",
        "Include": "_compile_include",
        "Block": "_compile_block",
        "Globals": "_compile_globals",
        "Imports": "_compile_imports",
        "Def": "_compile_def",
        "Region": "_compile_region",
        "CallBlock": "_compile_call_block",
        "Slot": "_compile_slot",
        "FromImport": "_compile_from_import",
        "With": "_compile_with",
        "WithConditional": "_compile_with_conditional",
        "Raw": "_compile_raw",
        "Capture": "_compile_capture",
        "Cache": "_compile_cache",
        "FilterBlock": "_compile_filter_block",
        "Break": "_compile_break",
        "Continue": "_compile_continue",
        "Spaceless": "_compile_spaceless",
        "Flush": "_compile_flush",
        "Embed": "_compile_embed",
        "Provide": "_compile_provide",
        "Push": "_compile_push",
        "Stack": "_compile_stack",
        "TemplateContext": "_compile_template_context",
        "Trans": "_compile_trans",
    }

    # Resolved dispatch table (unbound functions, built once per class)
    _class_dispatch: ClassVar[dict[str, Callable] | None] = None

    @classmethod
    def _ensure_dispatch(cls) -> dict[str, Callable]:
        """Build and cache the class-level dispatch table of unbound functions."""
        if cls._class_dispatch is None:
            cls._class_dispatch = {
                type_name: getattr(cls, method_name)
                for type_name, method_name in cls._NODE_DISPATCH_NAMES.items()
            }
        return cls._class_dispatch

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._class_dispatch = None  # Reset so subclasses rebuild dispatch

    def __init__(self, env: Environment):
        self._env = env
        self._cached_pure_filters: frozenset[str] | None = None
        self._last_block_compiled_stmts: list[ast.stmt] | None = None
        self._name: str | None = None
        self._filename: str | None = None
        self._warnings: list = []  # TemplateWarning instances
        self._scope_depth: int = 0  # Track nesting depth inside scoping blocks (if/for/while)
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
        # Context-override for thunk compilation (region defaults): use param names
        # instead of hardcoded ctx/_scope_stack when compiling expressions
        self._ctx_override: str | None = None
        self._scope_override: str | None = None
        # Variable caching / CSE: names cached as locals to avoid repeated _ls() calls
        self._cached_vars: set[str] = set()
        # Precomputed constants: values that can't be stored in ast.Constant
        # (dict, list, set, custom objects) are injected into the exec()
        # namespace as _pc_0, _pc_1, etc.  The list is exposed via the
        # .precomputed property after compile().
        self._precomputed: list[Any] = []
        self._precomputed_ids: dict[int, int] = {}
        # Extension compiler handlers: {node_type_name: Extension instance}
        self._extension_compilers: dict[str, object] = getattr(
            env, "_extension_compilers", getattr(env, "_extension_tags", {})
        )  # node_type→ext dispatch
        # Tracks whether current block compilation has _append rebinding
        # (set by _compile_capture, _compile_cache, etc.)
        self._block_has_append_rebind: bool = False
        # Node dispatch table — shared class-level unbound functions, resolved once
        self._node_dispatch: dict[str, Callable] = type(self)._ensure_dispatch()

    @property
    def warnings(self) -> list:
        """Compile-time warnings accumulated during compilation."""
        return self._warnings

    def _emit_warning(
        self, code, message: str, *, lineno: int | None = None, suggestion: str | None = None
    ) -> None:
        """Record a compile-time warning."""
        from kida.exceptions import TemplateWarning

        self._warnings.append(
            TemplateWarning(
                code=code,
                message=message,
                template_name=self._name,
                lineno=lineno,
                suggestion=suggestion,
            )
        )

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
        from kida.exceptions import ErrorCode, TemplateSyntaxError
        from kida.nodes import Block, CallBlock, Def, Region, Slot, SlotBlock

        for node in nodes:
            if isinstance(node, Block):
                if not _BLOCK_NAME_RE.match(node.name):
                    err = TemplateSyntaxError(
                        f"Invalid block name '{node.name}': must be identifier-like "
                        "(e.g. [a-zA-Z_][a-zA-Z0-9_]*)",
                        lineno=node.lineno,
                        name=self._name,
                        filename=self._filename,
                    )
                    err.code = ErrorCode.INVALID_IDENTIFIER
                    raise err
                if node.name in self._blocks and isinstance(self._blocks[node.name], Region):
                    err = TemplateSyntaxError(
                        f"Duplicate block/region name '{node.name}'",
                        lineno=node.lineno,
                        name=self._name,
                        filename=self._filename,
                    )
                    err.code = ErrorCode.INVALID_IDENTIFIER
                    raise err
                self._blocks[node.name] = node
                # Recurse into block body to find nested blocks
                self._collect_blocks(node.body)
            elif isinstance(node, Def):
                if not _BLOCK_NAME_RE.match(node.name):
                    err = TemplateSyntaxError(
                        f"Invalid def name '{node.name}': must be identifier-like "
                        "(e.g. [a-zA-Z_][a-zA-Z0-9_]*)",
                        lineno=node.lineno,
                        name=self._name,
                        filename=self._filename,
                    )
                    err.code = ErrorCode.INVALID_IDENTIFIER
                    raise err
                self._collect_blocks(node.body)
            elif isinstance(node, Region):
                if not _BLOCK_NAME_RE.match(node.name):
                    err = TemplateSyntaxError(
                        f"Invalid region name '{node.name}': must be identifier-like "
                        "(e.g. [a-zA-Z_][a-zA-Z0-9_]*)",
                        lineno=node.lineno,
                        name=self._name,
                        filename=self._filename,
                    )
                    err.code = ErrorCode.INVALID_IDENTIFIER
                    raise err
                if node.name in self._blocks:
                    err = TemplateSyntaxError(
                        f"Duplicate block/region name '{node.name}'",
                        lineno=node.lineno,
                        name=self._name,
                        filename=self._filename,
                    )
                    err.code = ErrorCode.INVALID_IDENTIFIER
                    raise err
                self._blocks[node.name] = node  # Region stored as block for registration
                self._collect_blocks(node.body)
            elif isinstance(node, CallBlock):
                for slot_name in node.slots:
                    if slot_name != "default" and not _BLOCK_NAME_RE.match(slot_name):
                        err = TemplateSyntaxError(
                            f"Invalid slot name '{slot_name}': must be identifier-like "
                            "(e.g. [a-zA-Z_][a-zA-Z0-9_]*)",
                            lineno=node.lineno,
                            name=self._name,
                            filename=self._filename,
                        )
                        err.code = ErrorCode.INVALID_IDENTIFIER
                        raise err
                for slot_body in node.slots.values():
                    self._collect_blocks(slot_body)
            elif isinstance(node, SlotBlock):
                if node.name != "default" and not _BLOCK_NAME_RE.match(node.name):
                    err = TemplateSyntaxError(
                        f"Invalid slot name '{node.name}': must be identifier-like "
                        "(e.g. [a-zA-Z_][a-zA-Z0-9_]*)",
                        lineno=node.lineno,
                        name=self._name,
                        filename=self._filename,
                    )
                    err.code = ErrorCode.INVALID_IDENTIFIER
                    raise err
                self._collect_blocks(node.body)
            elif isinstance(node, Slot):
                if node.name != "default" and not _BLOCK_NAME_RE.match(node.name):
                    err = TemplateSyntaxError(
                        f"Invalid slot name '{node.name}': must be identifier-like "
                        "(e.g. [a-zA-Z_][a-zA-Z0-9_]*)",
                        lineno=node.lineno,
                        name=self._name,
                        filename=self._filename,
                    )
                    err.code = ErrorCode.INVALID_IDENTIFIER
                    raise err
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
        self._warnings = []  # Reset warnings for each compilation
        self._locals = set()  # Reset locals for each compilation
        self._block_counter = 0  # Reset counter for each compilation
        self._has_async = False  # Reset async flag for each compilation
        self._def_caller_stack = []  # Lexical caller scoping: def → call → caller()
        self._outer_caller_expr = None  # Set when compiling call body inside def
        self._precomputed = []  # Reset precomputed for each compilation
        self._precomputed_ids = {}

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

    @property
    def precomputed(self) -> list[Any]:
        """Values that must be injected into the exec() namespace as ``_pc_N``."""
        return self._precomputed

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
                thunk_defs, region_func = self._make_region_function(block_name, block_node)
                module_body.extend(thunk_defs)
                module_body.append(region_func)

        # Detect {% globals %} blocks and compile _globals_setup function
        globals_setup = self._make_globals_setup(node)
        if globals_setup is not None:
            module_body.append(globals_setup)

        # Generate all three block function variants (sync, stream, async stream).
        # Regular blocks compile the Kida body once (sync), then derive stream
        # variants via Python AST transformation (_append → yield), eliminating
        # 2 redundant Kida AST compilations per block.
        # Region blocks use their own delegation path and are unaffected.
        from kida.compiler.stream_transform import sync_body_to_stream

        sync_blocks: list[ast.stmt] = []
        stream_blocks: list[ast.stmt] = []
        async_stream_blocks: list[ast.stmt] = []

        for block_name, block_node in saved_blocks.items():
            # Reset per-block flag before sync compilation
            self._block_has_append_rebind = False
            sync_blocks.append(self._make_block_function(block_name, block_node))

            if isinstance(block_node, Region):
                # Region blocks: compile separately (they delegate, not compile body)
                self._streaming = True
                stream_blocks.append(self._make_block_function_stream(block_name, block_node))
                self._async_mode = True
                async_stream_blocks.append(
                    self._make_block_function_stream_async(block_name, block_node)
                )
                self._async_mode = False
                self._streaming = False
            else:
                # Regular blocks: reuse sync body compilation saved by
                # _make_block_function, transform for streaming.
                compiled_stmts = self._last_block_compiled_stmts or []

                if self._block_has_append_rebind:
                    # Block rebinds _append (capture/cache/spaceless/push) —
                    # fall back to dedicated stream compilation so that the
                    # _append → yield transform does not leak captured content.
                    self._streaming = True
                    stream_blocks.append(self._make_block_function_stream(block_name, block_node))
                    self._async_mode = True
                    async_stream_blocks.append(
                        self._make_block_function_stream_async(block_name, block_node)
                    )
                    self._async_mode = False
                    self._streaming = False
                else:
                    stream_stmts = sync_body_to_stream(compiled_stmts)

                    # Build stream block function
                    stream_body: list[ast.stmt] = self._make_block_preamble(streaming=True)
                    stream_body.extend(stream_stmts)
                    stream_body.append(ast.Return(value=None))
                    stream_body.append(ast.Expr(value=ast.Yield(value=None)))
                    stream_blocks.append(
                        ast.FunctionDef(
                            name=f"_block_{block_name}_stream",
                            args=ast.arguments(
                                posonlyargs=[],
                                args=[ast.arg(arg="ctx"), ast.arg(arg="_blocks")],
                                vararg=None,
                                kwonlyargs=[],
                                kw_defaults=[],
                                kwarg=None,
                                defaults=[],
                            ),
                            body=stream_body,
                            decorator_list=[],
                            returns=None,
                        )
                    )

                    # Async stream: if template has async constructs, must compile
                    # separately (AsyncFor → ast.AsyncFor requires _async_mode=True).
                    # Otherwise, derive from sync body transform.
                    if self._has_async:
                        self._streaming = True
                        self._async_mode = True
                        async_stream_blocks.append(
                            self._make_block_function_stream_async(block_name, block_node)
                        )
                        self._async_mode = False
                        self._streaming = False
                    else:
                        async_stmts = sync_body_to_stream(compiled_stmts)
                        async_body: list[ast.stmt] = self._make_block_preamble(streaming=True)
                        async_body.extend(async_stmts)
                        async_body.append(ast.Return(value=None))
                        async_body.append(ast.Expr(value=ast.Yield(value=None)))
                        async_stream_blocks.append(
                            ast.AsyncFunctionDef(
                                name=f"_block_{block_name}_stream_async",
                                args=ast.arguments(
                                    posonlyargs=[],
                                    args=[ast.arg(arg="ctx"), ast.arg(arg="_blocks")],
                                    vararg=None,
                                    kwonlyargs=[],
                                    kw_defaults=[],
                                    kwarg=None,
                                    defaults=[],
                                ),
                                body=async_body,
                                decorator_list=[],
                                returns=None,
                            )
                        )

        module_body.extend(sync_blocks)
        module_body.append(render_func)

        # Streaming render function
        self._streaming = True
        module_body.extend(stream_blocks)
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

        # Async streaming render function (generated for ALL templates).
        # For sync templates, these wrap sync code in async def.
        # This ensures every parent template has render_stream_async for
        # inheritance chains where a child introduces async constructs.
        self._streaming = True
        self._async_mode = True
        module_body.extend(async_stream_blocks)
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
        from kida.nodes import Def, FromImport, Globals, Import, Imports, Let

        # Single-pass classification instead of 5 separate list comprehensions
        setup_nodes: list[Any] = []
        top_level_imports: list[Any] = []
        top_level_defs: list[Any] = []
        top_level_regions: list[Any] = []
        top_level_lets: list[Any] = []
        for n in node.body:
            if isinstance(n, (Globals, Imports)):
                setup_nodes.append(n)
            elif isinstance(n, (FromImport, Import)):
                top_level_imports.append(n)
            elif isinstance(n, Def):
                top_level_defs.append(n)
            elif isinstance(n, Region):
                top_level_regions.append(n)
            elif isinstance(n, Let):
                top_level_lets.append(n)
        if (
            not setup_nodes
            and not top_level_imports
            and not top_level_defs
            and not top_level_regions
            and not top_level_lets
        ):
            return None

        # Preamble: scope stack, buf, _append, _e, _s, _acc (needed by imports/globals)
        profiling = self._env.enable_profiling
        body_stmts: list[ast.stmt] = self._make_runtime_preamble(
            include_scope_stack=True,
            include_escape_str=True,
            include_getattr=True,
            include_buf_append=True,
            include_acc=profiling,
            acc_none=True,
            include_render_ctx=True,
        )

        # Top-level imports first (so macros are in ctx for blocks)
        for imp_node in top_level_imports:
            body_stmts.extend(self._compile_node(imp_node))

        # Top-level lets (so render_block has same context as full render)
        for let_node in top_level_lets:
            body_stmts.extend(self._compile_node(let_node))

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
            body=cast("list[ast.stmt]", body_stmts or [ast.Pass()]),
            decorator_list=[],
        )

    def _make_runtime_preamble(
        self,
        *,
        include_blocks_guard: bool = False,
        include_scope_stack: bool = False,
        include_escape_str: bool = False,
        include_getattr: bool = False,
        include_buf_append: bool = False,
        include_acc: bool = False,
        acc_none: bool = False,
        include_lookup_scope: bool = False,
        include_render_ctx: bool = False,
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
        if include_lookup_scope:
            # Cache _lookup_scope as _ls for LOAD_FAST instead of LOAD_GLOBAL
            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id="_ls", ctx=ast.Store())],
                    value=ast.Name(id="_lookup_scope", ctx=ast.Load()),
                )
            )
        if include_getattr:
            # Cache _getattr as _ga for LOAD_FAST instead of LOAD_GLOBAL.
            # Called on every dot-access ({{ obj.attr }}), so high frequency.
            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id="_ga", ctx=ast.Store())],
                    value=ast.Name(id="_getattr", ctx=ast.Load()),
                )
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
                    # Cache ''.join as _join for LOAD_FAST on return path
                    ast.Assign(
                        targets=[ast.Name(id="_join", ctx=ast.Store())],
                        value=ast.Attribute(
                            value=ast.Constant(value=""),
                            attr="join",
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
        if include_render_ctx:
            # Cache render context as _rc for LOAD_FAST instead of
            # calling ContextVar.get() on every line-tracked node.
            # Falls back to _null_rc (absorbs .line = N) when called
            # outside a render context (e.g. block recompilation tests).
            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id="_rc", ctx=ast.Store())],
                    value=ast.BoolOp(
                        op=ast.Or(),
                        values=[
                            ast.Call(
                                func=ast.Name(id="_get_render_ctx", ctx=ast.Load()),
                                args=[],
                                keywords=[],
                            ),
                            ast.Name(id="_null_rc", ctx=ast.Load()),
                        ],
                    ),
                )
            )
        return stmts

    def _make_block_preamble(self, streaming: bool) -> list[ast.stmt]:
        """Common setup stmts for block functions.

        Non-streaming adds buf and _append for StringBuilder.
        """
        profiling = self._env.enable_profiling
        return self._make_runtime_preamble(
            include_scope_stack=True,
            include_escape_str=True,
            include_getattr=True,
            include_lookup_scope=True,
            include_buf_append=not streaming,
            include_acc=profiling,
            include_render_ctx=True,
        )

    def _build_region_keywords(self, region_node: Region) -> tuple[list[str], list[ast.keyword]]:
        """Build param_names and keywords for region block delegation.

        Returns (param_names, keywords) where keywords includes both the
        per-param entries and the trailing _outer_ctx / _blocks keywords.
        """
        param_names = [p.name for p in region_node.params]
        n_defaults = len(region_node.defaults)
        n_required = len(param_names) - n_defaults

        keywords: list[ast.keyword] = []
        for i, param_name in enumerate(param_names):
            if i < n_required:
                val = ast.Call(
                    func=ast.Name(id="_lookup", ctx=ast.Load()),
                    args=[
                        ast.Name(id="ctx", ctx=ast.Load()),
                        ast.Constant(value=param_name),
                    ],
                    keywords=[],
                )
            else:
                val = ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="ctx", ctx=ast.Load()),
                        attr="get",
                        ctx=ast.Load(),
                    ),
                    args=[
                        ast.Constant(value=param_name),
                        ast.Name(id="_REGION_DEFAULT", ctx=ast.Load()),
                    ],
                    keywords=[],
                )
            keywords.append(ast.keyword(arg=param_name, value=val))
        keywords.append(ast.keyword(arg="_outer_ctx", value=ast.Name(id="ctx", ctx=ast.Load())))
        keywords.append(ast.keyword(arg="_blocks", value=ast.Name(id="_blocks", ctx=ast.Load())))
        return param_names, keywords

    def _make_region_block_function(self, name: str, region_node: Region) -> ast.FunctionDef:
        """Generate block wrapper that delegates to region callable with ctx params."""
        _param_names, keywords = self._build_region_keywords(region_node)

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

    # ─────────────────────────────────────────────────────────────────────────
    # Variable caching / common subexpression elimination (CSE)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _has_unconditional_exprs(body: Sequence) -> bool:
        """Fast check: does the body have any nodes that produce unconditional Name refs?

        Returns False when every top-level node is a control-flow node or Data
        (raw text), meaning CSE analysis would find no unconditional refs and
        can be skipped entirely.
        """
        from kida.nodes import Data

        # Node types that never produce unconditional Name refs at their level
        skip = (
            For,
            AsyncFor,
            If,
            While,
            Match,
            Set,
            Let,
            Export,
            Capture,
            With,
            WithConditional,
            Import,
            FromImport,
            Def,
            Block,
            Data,
        )
        return any(not isinstance(n, skip) for n in body)

    def _analyze_for_cse(self, body_nodes: Sequence) -> set[str]:
        """Combined CSE analysis: returns cacheable variable names.

        Performs the fast unconditional-expression guard check followed by
        the full variable reference collection in a single call, deduplicating
        the pattern used across _make_block_function and _make_render_direct_body.
        """
        if not self._has_unconditional_exprs(body_nodes):
            return set()
        ref_counts, mutated = self._collect_var_refs(body_nodes)
        return {
            n
            for n, count in ref_counts.items()
            if count >= 2 and n not in mutated and n not in self._locals
        }

    @staticmethod
    def _collect_var_refs(nodes: Any) -> tuple[dict[str, int], set[str]]:
        """Collect variable reference counts and mutated names from Kida AST nodes.

        Walks the AST recursively, collecting mutations from ALL code but only
        counting Name references in unconditional (non-branching) code paths.
        This ensures eager cache assignments at function entry won't raise
        UndefinedError for variables only referenced inside conditional branches.

        Does NOT recurse into Block or Def bodies (separate compilation scopes).

        Returns:
            (ref_counts, mutated) where ref_counts maps var name to usage count
            in unconditional code, and mutated is the set of names assigned
            anywhere in the body.
        """
        ref_counts: dict[str, int] = {}
        mutated: set[str] = set()

        def _collect_target_names(target: Any) -> None:
            """Collect all variable names from a For loop target (simple or tuple)."""
            if isinstance(target, Name):
                mutated.add(target.name)
            elif hasattr(target, "items"):  # KidaTuple
                for item in target.items:
                    _collect_target_names(item)

        def _walk(node: Any, *, count_refs: bool = True) -> None:
            if node is None:
                return
            if isinstance(node, (list, tuple)):
                for item in node:
                    _walk(item, count_refs=count_refs)
                return
            if isinstance(node, dict):
                for v in node.values():
                    _walk(v, count_refs=count_refs)
                return

            # Count Name references only in unconditional code
            if isinstance(node, Name) and node.ctx == "load":
                if count_refs:
                    ref_counts[node.name] = ref_counts.get(node.name, 0) + 1
                return

            # Track mutations: Set/Let/Export/Capture targets (always, regardless of branch)
            if isinstance(node, Set):
                if isinstance(node.target, Name):
                    mutated.add(node.target.name)
                _walk(node.value, count_refs=count_refs)
                return
            if isinstance(node, Let):
                if isinstance(node.name, Name):
                    mutated.add(node.name.name)
                _walk(node.value, count_refs=count_refs)
                return
            if isinstance(node, Export):
                if isinstance(node.name, Name):
                    mutated.add(node.name.name)
                _walk(node.value, count_refs=count_refs)
                return
            if isinstance(node, Capture):
                mutated.add(node.name)
                _walk(node.body, count_refs=False)
                return

            # ListComp: target is a local within the comprehension scope;
            # elt/ifs reference that local, so they must not be counted for caching.
            # iter is evaluated in the enclosing scope (unconditional).
            if isinstance(node, ListComp):
                _collect_target_names(node.target)
                _walk(node.iter, count_refs=count_refs)
                _walk(node.elt, count_refs=False)
                for if_expr in node.ifs:
                    _walk(if_expr, count_refs=False)
                return

            # Track For/AsyncFor loop targets — loop vars become Python locals
            # at runtime and must not be cached at function entry.
            # Also exclude 'loop' (LoopContext) which is only available inside the body.
            # For iter expression is unconditional; body/empty are conditional.
            if isinstance(node, (For, AsyncFor)):
                _collect_target_names(node.target)
                mutated.add("loop")
                _walk(node.iter, count_refs=count_refs)
                _walk(node.body, count_refs=False)
                _walk(node.empty, count_refs=False)
                return

            # With/WithConditional introduce locally-scoped variables
            if isinstance(node, With):
                for target_name, expr in node.targets:
                    mutated.add(target_name)
                    _walk(expr, count_refs=count_refs)
                _walk(node.body, count_refs=False)
                return
            if isinstance(node, WithConditional):
                if isinstance(node.target, Name):
                    mutated.add(node.target.name)
                _walk(node.expr, count_refs=count_refs)
                _walk(node.body, count_refs=False)
                if node.empty:
                    _walk(node.empty, count_refs=False)
                return

            # Import/FromImport introduce names into ctx mid-function
            if isinstance(node, Import):
                mutated.add(node.target)
                _walk(node.template, count_refs=count_refs)
                return
            if isinstance(node, FromImport):
                for name, alias in node.names:
                    mutated.add(alias or name)
                _walk(node.template, count_refs=count_refs)
                return

            # If/While: test expression is unconditional, bodies are conditional.
            if isinstance(node, If):
                _walk(node.test, count_refs=count_refs)
                _walk(node.body, count_refs=False)
                for elif_test, elif_body in node.elif_:
                    _walk(elif_test, count_refs=False)
                    _walk(elif_body, count_refs=False)
                if node.else_:
                    _walk(node.else_, count_refs=False)
                return
            if isinstance(node, While):
                _walk(node.test, count_refs=count_refs)
                _walk(node.body, count_refs=False)
                return

            # Match: subject is unconditional, case bodies are conditional.
            # Case patterns may bind variables.
            if isinstance(node, Match):
                if node.subject is not None:
                    _walk(node.subject, count_refs=count_refs)
                for pattern, guard, case_body in node.cases:
                    _collect_target_names(pattern)
                    if guard is not None:
                        _walk(guard, count_refs=False)
                    _walk(case_body, count_refs=False)
                return

            # CallBlock slot bodies execute with scoped bindings pushed onto
            # _scope_stack at runtime.  Variables provided via let: params are
            # not available at function entry, so references inside slot bodies
            # must NOT be counted as unconditional — otherwise the CSE cache
            # assignment (_cv_x = _ls(...)) fires before the binding exists.
            # The call expression itself IS unconditional.
            if isinstance(node, CallBlock):
                _walk(node.call, count_refs=count_refs)
                for slot_body in node.slots.values():
                    _walk(slot_body, count_refs=False)
                return

            # Don't recurse into separate compilation scopes.
            # Def names are locally defined mid-function — exclude from caching.
            if isinstance(node, Def):
                mutated.add(node.name)
                return
            if isinstance(node, Block):
                return

            # Skip non-dataclass types
            if not hasattr(node, "__dataclass_fields__"):
                return

            # Recurse into all dataclass fields
            for field_name in node.__dataclass_fields__:
                child = getattr(node, field_name, None)
                if child is not None:
                    _walk(child, count_refs=count_refs)

        _walk(nodes)
        return ref_counts, mutated

    def _emit_cache_assignments(self, names: set[str]) -> list[ast.stmt]:
        """Emit _cv_name = _ls(ctx, _scope_stack, 'name') for each cached variable."""
        return [
            ast.Assign(
                targets=[ast.Name(id=f"_cv_{name}", ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Name(id="_ls", ctx=ast.Load()),
                    args=[
                        ast.Name(id="ctx", ctx=ast.Load()),
                        ast.Name(id="_scope_stack", ctx=ast.Load()),
                        ast.Constant(value=name),
                    ],
                    keywords=[],
                ),
            )
            for name in sorted(names)
        ]

    @staticmethod
    def _is_append_constant(stmt: ast.stmt) -> str | None:
        """If *stmt* is ``_append(<string constant>)``, return the string; else None."""
        if (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Name)
            and stmt.value.func.id == "_append"
            and len(stmt.value.args) == 1
            and not stmt.value.keywords
            and isinstance(stmt.value.args[0], ast.Constant)
            and isinstance(stmt.value.args[0].value, str)
        ):
            return stmt.value.args[0].value
        return None

    @staticmethod
    def _is_line_tracking(stmt: ast.stmt) -> bool:
        """Return True if *stmt* is ``_rc.line = N`` (render-context line tracking)."""
        return (
            isinstance(stmt, ast.Assign)
            and len(stmt.targets) == 1
            and isinstance(stmt.targets[0], ast.Attribute)
            and isinstance(stmt.targets[0].value, ast.Name)
            and stmt.targets[0].value.id == "_rc"
            and stmt.targets[0].attr == "line"
        )

    @staticmethod
    def _is_single_append_expr(stmt: ast.stmt) -> ast.expr | None:
        """If *stmt* is ``_append(expr)``, return *expr*; else None."""
        if (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Name)
            and stmt.value.func.id == "_append"
            and len(stmt.value.args) == 1
            and not stmt.value.keywords
        ):
            return stmt.value.args[0]
        return None

    # Stores compiled stmts from the last _make_block_function call for stream reuse
    _last_block_compiled_stmts: list[ast.stmt] | None

    def _make_block_function(self, name: str, block_node: Block | Region) -> ast.FunctionDef:
        """Generate a block function: _block_name(ctx, _blocks) -> str.

        Also stores the raw compiled stmts in ``_last_block_compiled_stmts``
        so the stream variant can be derived without recompiling the Kida AST.
        """
        self._last_block_compiled_stmts = None
        if isinstance(block_node, Region):
            return self._make_region_block_function(name, block_node)

        # --- CSE: analyse Kida AST before compilation ---
        body_nodes = list(block_node.body)
        self._last_block_body_nodes = body_nodes
        cacheable = self._analyze_for_cse(body_nodes)
        saved_cached = self._cached_vars
        self._cached_vars = cacheable

        # Compile block body with f-string coalescing
        compiled_stmts = self._compile_body_with_coalescing(body_nodes)
        self._cached_vars = saved_cached

        # Save for stream derivation
        self._last_block_compiled_stmts = compiled_stmts

        # --- Single-pass post-compile analysis ---
        # Classify compiled statements in one loop: track constants for the
        # constant-block optimisation, separate line-tracking from meaningful
        # statements for the single-expression optimisation.
        constant_parts: list[str] = []
        all_constant = True
        non_tracking: list[ast.stmt] = []
        tracking: list[ast.stmt] = []

        for stmt in compiled_stmts:
            if self._is_line_tracking(stmt):
                tracking.append(stmt)
                continue
            non_tracking.append(stmt)
            if all_constant:
                part = self._is_append_constant(stmt)
                if part is not None:
                    constant_parts.append(part)
                else:
                    all_constant = False

        # --- Constant block return optimisation ---
        # If every meaningful statement is _append(<string constant>), concatenate
        # them and emit a single ``return "..."`` with no preamble at all.
        if all_constant and constant_parts:
            merged = "".join(constant_parts)
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
                body=[ast.Return(value=ast.Constant(value=merged))],
                decorator_list=[],
                returns=None,
            )

        # --- Single-expression return optimisation ---
        # If there is exactly one _append(expr) (ignoring line-tracking stmts),
        # skip buf/join and return the expression directly with a minimal preamble.
        if len(non_tracking) == 1:
            expr = self._is_single_append_expr(non_tracking[0])
            if expr is not None:
                # Minimal preamble: _e, _s, _ga, _ls, _rc but no buf/_append.
                profiling = self._env.enable_profiling
                preamble = self._make_runtime_preamble(
                    include_scope_stack=True,
                    include_escape_str=True,
                    include_getattr=True,
                    include_lookup_scope=True,
                    include_buf_append=False,
                    include_acc=profiling,
                    include_render_ctx=True,
                )
                cache_stmts = self._emit_cache_assignments(cacheable)
                body: list[ast.stmt] = preamble + cache_stmts + tracking + [ast.Return(value=expr)]
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

        # --- Default path: full buf/join machinery ---
        body = self._make_block_preamble(streaming=False)
        body.extend(self._emit_cache_assignments(cacheable))
        body.extend(compiled_stmts)

        # return _join(buf)  — _join cached in preamble for LOAD_FAST
        body.append(
            ast.Return(
                value=ast.Call(
                    func=ast.Name(id="_join", ctx=ast.Load()),
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
        profiling = self._env.enable_profiling
        return self._make_runtime_preamble(
            include_blocks_guard=True,
            include_scope_stack=True,
            include_getattr=True,
            include_lookup_scope=True,
            include_acc=profiling,
            include_render_ctx=True,
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
        # CSE: analyse Kida AST before compilation
        render_body_nodes = list(node.body)
        cacheable = self._analyze_for_cse(render_body_nodes)
        saved_cached = self._cached_vars
        self._cached_vars = cacheable

        body: list[ast.stmt] = self._make_runtime_preamble(
            include_escape_str=True,
            include_getattr=True,
            include_lookup_scope=True,
            include_buf_append=not streaming,
            include_render_ctx=True,
        )
        body.extend(self._emit_cache_assignments(cacheable))
        body.extend(self._compile_body_with_coalescing(render_body_nodes))
        self._cached_vars = saved_cached
        if streaming:
            body.append(ast.Return(value=None))
            body.append(ast.Expr(value=ast.Yield(value=None)))
        else:
            body.append(
                ast.Return(
                    value=ast.Call(
                        func=ast.Name(id="_join", ctx=ast.Load()),
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
                extends_node = cast("Extends", child)
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

        # Compile block body with streaming yields (reuse cached body_nodes)
        body_nodes = getattr(self, "_last_block_body_nodes", None) or list(block_node.body)
        body.extend(self._compile_body_with_coalescing(body_nodes))

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
                extends_node = cast("Extends", child)
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
        _param_names, keywords = self._build_region_keywords(region_node)
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

        # Reuse cached body_nodes from _make_block_function
        body_nodes = getattr(self, "_last_block_body_nodes", None) or list(block_node.body)
        body.extend(self._compile_body_with_coalescing(body_nodes))

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
                extends_node = cast("Extends", child)
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

        Generates: _rc.line = lineno

        Uses the cached _rc local (set in preamble) instead of calling
        _get_render_ctx() per node, avoiding repeated ContextVar.get() calls.

        RFC: kida-contextvar-patterns
        """
        return ast.Assign(
            targets=[
                ast.Attribute(
                    value=ast.Name(id="_rc", ctx=ast.Load()),
                    attr="line",
                    ctx=ast.Store(),
                )
            ],
            value=ast.Constant(value=lineno),
        )

    @staticmethod
    def _compile_template_context(_node: Node) -> list[ast.stmt]:
        """No-op: TemplateContext is a declaration, not code."""
        return []

    def _compile_node(self, node: Node) -> list[ast.stmt]:
        """Compile a single AST node to Python statements.

        Complexity: O(1) type dispatch using class name lookup.

        For nodes that can cause runtime errors, injects a line marker
        statement (ctx['_line'] = N) before the node's code. This enables
        rich error messages with source line numbers.
        """
        node_type = type(node).__name__

        # Inject line marker for risky nodes
        stmts: list[ast.stmt] = []
        if node_type in self._LINE_TRACKED_NODES:
            stmts.append(self._make_line_marker(node.lineno))

        # Dispatch table — O(1) lookup, unbound functions called with self
        handler = self._node_dispatch.get(node_type)
        if handler:
            stmts.extend(handler(self, node))
        elif self._extension_compilers:
            # Direct node_type→extension dispatch (O(1) lookup)
            ext = self._extension_compilers.get(node_type)
            if ext is not None:
                result = cast("Any", ext).compile(self, node)
                stmts.extend(result)
            else:
                from kida.exceptions import TemplateSyntaxError

                raise TemplateSyntaxError(
                    f"Unknown AST node type '{node_type}' — no compiler registered",
                    lineno=getattr(node, "lineno", None),
                )
        else:
            from kida.exceptions import TemplateSyntaxError

            raise TemplateSyntaxError(
                f"Unknown AST node type '{node_type}' — no compiler registered",
                lineno=getattr(node, "lineno", None),
            )

        return stmts

    def _get_node_dispatch(self) -> dict[str, Callable]:
        """Get node type dispatch table."""
        return self._node_dispatch
