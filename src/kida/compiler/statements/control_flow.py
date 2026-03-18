"""Control flow statement compilation for Kida compiler.

Provides mixin for compiling control flow statements (if, for).

Uses inline TYPE_CHECKING declarations for host attributes.
See: plan/rfc-mixin-protocol-typing.md
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kida.nodes import AsyncFor, For, If, Node, While


class ControlFlowMixin:
    """Mixin for compiling control flow statements.

    Host attributes and cross-mixin dependencies are declared via inline
    TYPE_CHECKING blocks.

    """

    # ─────────────────────────────────────────────────────────────────────────
    # Host attributes and cross-mixin dependencies (type-check only)
    # ─────────────────────────────────────────────────────────────────────────
    if TYPE_CHECKING:
        # Host attributes (from Compiler.__init__)
        _locals: set[str]
        _block_counter: int
        _loop_vars: set[str]
        _has_async: bool

        # From ExpressionCompilationMixin
        def _compile_expr(self, node: Node, store: bool = False) -> ast.expr: ...

        # From Compiler core
        def _compile_node(self, node: Node) -> list[ast.stmt]: ...

    def _wrap_with_scope(
        self, body_stmts: list[ast.stmt], source_nodes: Any = None
    ) -> list[ast.stmt]:
        """Wrap statements with scope push/pop for block-scoped variables.

        When source_nodes is provided and contains no Set, Let, Capture, or
        Export nodes, the scope push/pop is skipped entirely — avoiding
        unnecessary dict allocation and list append/pop per block entry.

        Generates (when scoping is needed):
            _scope_stack.append({})
            ... body statements ...
            _scope_stack.pop()
        """
        if not body_stmts:
            return [ast.Pass()]

        # Skip scope push/pop when the body has no block-scoped assignments
        if source_nodes is not None:
            from kida.compiler.partial_eval import _body_has_scoping_nodes

            if not _body_has_scoping_nodes(source_nodes):
                return body_stmts

        return [
            # Push new scope
            ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="_scope_stack", ctx=ast.Load()),
                        attr="append",
                        ctx=ast.Load(),
                    ),
                    args=[ast.Dict(keys=[], values=[])],
                    keywords=[],
                )
            ),
            *body_stmts,
            # Pop scope
            ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="_scope_stack", ctx=ast.Load()),
                        attr="pop",
                        ctx=ast.Load(),
                    ),
                    args=[],
                    keywords=[],
                )
            ),
        ]

    def _compile_break(self, node: Node) -> list[ast.stmt]:
        """Compile {% break %} loop control.

        Part of RFC: kida-modern-syntax-features.
        """
        return [ast.Break()]

    def _compile_continue(self, node: Node) -> list[ast.stmt]:
        """Compile {% continue %} loop control.

        Part of RFC: kida-modern-syntax-features.
        """
        return [ast.Continue()]

    def _compile_while(self, node: While) -> list[ast.stmt]:
        """Compile {% while cond %}...{% end %} loop.

        Generates:
            while condition:
                ... body ...

        Part of RFC: kida-2.0-moonshot (While Loops).

        Example:
            {% let counter = 0 %}
            {% while counter < 5 %}
                {{ counter }}
                {% let counter = counter + 1 %}
            {% end %}
        """
        test = self._compile_expr(node.test)

        body: list[ast.stmt] = []
        for child in node.body:
            body.extend(self._compile_node(child))
        # Wrap body with scope for block-scoped variables
        body = self._wrap_with_scope(body, source_nodes=node.body) if body else [ast.Pass()]

        return [
            ast.While(
                test=test,
                body=body,
                orelse=[],
            )
        ]

    def _compile_if(self, node: If) -> list[ast.stmt]:
        """Compile {% if %} conditional."""
        test = self._compile_expr(node.test)
        body = []
        for child in node.body:
            body.extend(self._compile_node(child))
        # Wrap body with scope for block-scoped variables
        body = self._wrap_with_scope(body, source_nodes=node.body) if body else [ast.Pass()]

        orelse: list[ast.stmt] = []
        innermost_elif: ast.If | None = None

        # Handle elif chains (first elif is innermost; we track it directly)
        for elif_test, elif_body in node.elif_:
            elif_stmts = []
            for child in elif_body:
                elif_stmts.extend(self._compile_node(child))
            # Wrap elif body with scope
            elif_stmts = (
                self._wrap_with_scope(elif_stmts, source_nodes=elif_body)
                if elif_stmts
                else [ast.Pass()]
            )
            if not elif_stmts:
                elif_stmts = [ast.Pass()]
            new_if = ast.If(
                test=self._compile_expr(elif_test),
                body=elif_stmts,
                orelse=orelse,
            )
            if innermost_elif is None:
                innermost_elif = new_if
            orelse = [new_if]

        # Handle else
        if node.else_:
            else_stmts = []
            for child in node.else_:
                else_stmts.extend(self._compile_node(child))
            # Wrap else body with scope
            else_stmts = (
                self._wrap_with_scope(else_stmts, source_nodes=node.else_)
                if else_stmts
                else [ast.Pass()]
            )
            if innermost_elif is not None:
                innermost_elif.orelse = else_stmts
            else:
                orelse = else_stmts

        return [
            ast.If(
                test=test,
                body=body,
                orelse=orelse,
            )
        ]

    def _uses_loop_variable(self, nodes: Any) -> bool:
        """Check if any node in the tree references the 'loop' variable.

        This enables lazy LoopContext optimization: when loop.index, loop.first,
        etc. are not used, we can skip creating the LoopContext wrapper and
        iterate directly over the items (1.80x faster per benchmark).

        Args:
            nodes: A node or sequence of nodes to check

        Returns:
            True if 'loop' is referenced anywhere in the tree
        """
        from kida.nodes import Name

        if nodes is None:
            return False

        # Handle sequences (lists, tuples)
        if isinstance(nodes, (list, tuple)):
            return any(self._uses_loop_variable(n) for n in nodes)

        # Handle dicts (kwargs)
        if isinstance(nodes, dict):
            return any(self._uses_loop_variable(v) for v in nodes.values())

        # Check if this is a Name node referencing 'loop'
        if isinstance(nodes, Name) and nodes.name == "loop":
            return True

        # Skip non-node types (strings, ints, bools, etc.)
        if not hasattr(nodes, "__dataclass_fields__"):
            return False

        # Check all dataclass fields for child nodes
        # This catches all node types including FuncCall.func, Getattr.obj, etc.
        for field_name in nodes.__dataclass_fields__:
            child = getattr(nodes, field_name, None)
            if child is not None and self._uses_loop_variable(child):
                return True

        return False

    def _compile_for(self, node: For) -> list[ast.stmt]:
        """Compile {% for %} loop with optional LoopContext.

        Generates one of three forms based on loop.* usage and {% empty %} presence:

        When loop.* IS used (requires materialized list):
            _iter_source = iterable
            _loop_items = list(_iter_source) if _iter_source is not None else []
            if _loop_items:
                loop = _LoopContext(_loop_items)
                for item in loop:
                    ... body ...
            else:
                ... empty block ...

        When loop.* is NOT used and has {% empty %} (sentinel pattern):
            _iter_source = iterable
            _had_items = False
            if _iter_source is not None:
                for item in _iter_source:
                    _had_items = True
                    ... body ...
            if not _had_items:
                ... empty block ...

        When loop.* is NOT used and no {% empty %} (direct iteration):
            _iter_source = iterable
            if _iter_source is not None:
                for item in _iter_source:
                    ... body ...

        Optimization: Loop variables are tracked as locals and accessed
        directly (O(1) LOAD_FAST) instead of through ctx dict lookup.
        """
        # Get the loop variable name(s) and register as locals + loop_vars
        var_names = self._extract_names(node.target)
        for var_name in var_names:
            self._locals.add(var_name)
            self._loop_vars.add(var_name)

        # Check if loop.* properties are used in the body or test
        # This determines whether we need LoopContext or can iterate directly
        uses_loop = self._uses_loop_variable(node.body) or self._uses_loop_variable(node.test)

        # Only register 'loop' as a local if it's actually used
        if uses_loop:
            self._locals.add("loop")
            self._loop_vars.add("loop")

        target = self._compile_expr(node.target, store=True)
        iter_expr = self._compile_expr(node.iter)

        stmts: list[ast.stmt] = []

        # Use unique variable name to avoid conflicts with nested loops
        self._block_counter += 1
        iter_var = f"_iter_source_{self._block_counter}"
        has_empty = bool(node.empty)

        # _iter_source_N = iterable
        stmts.append(
            ast.Assign(
                targets=[ast.Name(id=iter_var, ctx=ast.Store())],
                value=iter_expr,
            )
        )

        # Compile the inner body (shared by all paths)
        body = []
        for child in node.body:
            body.extend(self._compile_node(child))
        # Wrap body with scope for block-scoped variables (each iteration gets its own scope)
        body = self._wrap_with_scope(body, source_nodes=node.body) if body else [ast.Pass()]

        # Handle inline test condition: {% for x in items if x.visible %}
        # Part of RFC: kida-modern-syntax-features
        if node.test:
            body = [
                ast.If(
                    test=self._compile_expr(node.test),
                    body=body,
                    orelse=[],
                )
            ]

        if uses_loop:
            # ── Path A: loop.* used — must materialize list for LoopContext ──
            loop_items_var = f"_loop_items_{self._block_counter}"

            # _loop_items_N = list(_iter_source_N) if _iter_source_N is not None else []
            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id=loop_items_var, ctx=ast.Store())],
                    value=ast.IfExp(
                        test=ast.Compare(
                            left=ast.Name(id=iter_var, ctx=ast.Load()),
                            ops=[ast.IsNot()],
                            comparators=[ast.Constant(value=None)],
                        ),
                        body=ast.Call(
                            func=ast.Name(id="_list", ctx=ast.Load()),
                            args=[ast.Name(id=iter_var, ctx=ast.Load())],
                            keywords=[],
                        ),
                        orelse=ast.List(elts=[], ctx=ast.Load()),
                    ),
                )
            )

            loop_body_stmts: list[ast.stmt] = [
                # loop = _LoopContext(_loop_items_N)
                ast.Assign(
                    targets=[ast.Name(id="loop", ctx=ast.Store())],
                    value=ast.Call(
                        func=ast.Name(id="_LoopContext", ctx=ast.Load()),
                        args=[ast.Name(id=loop_items_var, ctx=ast.Load())],
                        keywords=[],
                    ),
                ),
                # for item in loop:
                ast.For(
                    target=target,
                    iter=ast.Name(id="loop", ctx=ast.Load()),
                    body=body,
                    orelse=[],
                ),
            ]

            # Compile the empty block
            orelse = []
            for child in node.empty:
                orelse.extend(self._compile_node(child))

            stmts.append(
                ast.If(
                    test=ast.Name(id=loop_items_var, ctx=ast.Load()),
                    body=loop_body_stmts,
                    orelse=orelse,
                )
            )
        elif has_empty:
            # ── Path B: no loop.*, has {% empty %} — sentinel pattern ──
            # Avoids list() materialization; uses _had_items flag like async for.
            had_items_var = f"_had_items_{self._block_counter}"

            # _had_items_N = False
            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id=had_items_var, ctx=ast.Store())],
                    value=ast.Constant(value=False),
                )
            )

            # Prepend _had_items_N = True to loop body
            sentinel_body = [
                ast.Assign(
                    targets=[ast.Name(id=had_items_var, ctx=ast.Store())],
                    value=ast.Constant(value=True),
                ),
                *body,
            ]

            # if _iter_source_N is not None:
            #     for item in _iter_source_N:
            #         _had_items_N = True
            #         ... body ...
            stmts.append(
                ast.If(
                    test=ast.Compare(
                        left=ast.Name(id=iter_var, ctx=ast.Load()),
                        ops=[ast.IsNot()],
                        comparators=[ast.Constant(value=None)],
                    ),
                    body=[
                        ast.For(
                            target=target,
                            iter=ast.Name(id=iter_var, ctx=ast.Load()),
                            body=sentinel_body,
                            orelse=[],
                        )
                    ],
                    orelse=[],
                )
            )

            # if not _had_items_N: ... empty block ...
            orelse = []
            for child in node.empty:
                orelse.extend(self._compile_node(child))

            stmts.append(
                ast.If(
                    test=ast.UnaryOp(
                        op=ast.Not(),
                        operand=ast.Name(id=had_items_var, ctx=ast.Load()),
                    ),
                    body=orelse,
                    orelse=[],
                )
            )
        else:
            # ── Path C: no loop.*, no {% empty %} — direct iteration ──
            # No list() materialization, no sentinel flag. Simplest path.

            # if _iter_source_N is not None:
            #     for item in _iter_source_N:
            #         ... body ...
            stmts.append(
                ast.If(
                    test=ast.Compare(
                        left=ast.Name(id=iter_var, ctx=ast.Load()),
                        ops=[ast.IsNot()],
                        comparators=[ast.Constant(value=None)],
                    ),
                    body=[
                        ast.For(
                            target=target,
                            iter=ast.Name(id=iter_var, ctx=ast.Load()),
                            body=body,
                            orelse=[],
                        )
                    ],
                    orelse=[],
                )
            )

        # Remove loop variables from locals and loop_vars after the loop
        for var_name in var_names:
            self._locals.discard(var_name)
            self._loop_vars.discard(var_name)
        if uses_loop:
            self._locals.discard("loop")
            self._loop_vars.discard("loop")

        return stmts

    def _compile_async_for(self, node: AsyncFor) -> list[ast.stmt]:
        """Compile {% async for %} loop with AsyncLoopContext.

        Unlike sync _compile_for(), this does NOT call list() on the iterable.
        Instead it generates ast.AsyncFor for native async iteration and uses
        a boolean flag for {% empty %} detection.

        When compiling for sync functions (_async_mode=False), emits a pass
        placeholder. The Template-level guard prevents sync rendering of async
        templates, so this code path is unreachable at runtime.

        Generates (async mode):
            _had_items_N = False
            loop = _AsyncLoopContext()          # if loop.* used
            async for item in iterable:
                _had_items_N = True
                loop.advance(item)              # if loop.* used
                ... body ...
            if not _had_items_N:
                ... empty block ...

        Part of RFC: rfc-async-rendering.
        """
        # Flag template as async (needed even during sync compilation pass
        # so the _is_async flag gets set in the module)
        self._has_async = True

        # During sync compilation passes (render, render_stream), async for
        # cannot appear inside a regular def. Emit a pass placeholder —
        # the Template.render() guard prevents this from being reached.
        if not getattr(self, "_async_mode", False):
            return [ast.Pass()]
        # Get the loop variable name(s) and register as locals + loop_vars
        var_names = self._extract_names(node.target)
        for var_name in var_names:
            self._locals.add(var_name)
            self._loop_vars.add(var_name)

        # Check if loop.* properties are used in the body or test
        uses_loop = self._uses_loop_variable(node.body) or self._uses_loop_variable(node.test)

        if uses_loop:
            self._locals.add("loop")
            self._loop_vars.add("loop")

        target = self._compile_expr(node.target, store=True)
        iter_expr = self._compile_expr(node.iter)

        stmts: list[ast.stmt] = []

        # Use unique variable names to avoid conflicts with nested loops
        self._block_counter += 1
        had_items_var = f"_had_items_{self._block_counter}"

        # _had_items_N = False  (for {% empty %} detection)
        stmts.append(
            ast.Assign(
                targets=[ast.Name(id=had_items_var, ctx=ast.Store())],
                value=ast.Constant(value=False),
            )
        )

        # Build the loop body
        loop_body: list[ast.stmt] = []

        # _had_items_N = True  (first statement in loop body)
        loop_body.append(
            ast.Assign(
                targets=[ast.Name(id=had_items_var, ctx=ast.Store())],
                value=ast.Constant(value=True),
            )
        )

        if uses_loop:
            # loop = _AsyncLoopContext()  (before the async for)
            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id="loop", ctx=ast.Store())],
                    value=ast.Call(
                        func=ast.Name(id="_AsyncLoopContext", ctx=ast.Load()),
                        args=[],
                        keywords=[],
                    ),
                )
            )

            # loop.advance(item)  (inside the loop body, after _had_items = True)
            # Use a Load-context name for the function argument
            advance_arg = ast.Name(id=var_names[0], ctx=ast.Load())
            loop_body.append(
                ast.Expr(
                    value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id="loop", ctx=ast.Load()),
                            attr="advance",
                            ctx=ast.Load(),
                        ),
                        args=[advance_arg],
                        keywords=[],
                    )
                )
            )

        # Compile the inner body
        body = []
        for child in node.body:
            body.extend(self._compile_node(child))
        body = self._wrap_with_scope(body, source_nodes=node.body) if body else [ast.Pass()]

        # Handle inline test condition: {% async for x in items if x.visible %}
        if node.test:
            body = [
                ast.If(
                    test=self._compile_expr(node.test),
                    body=body,
                    orelse=[],
                )
            ]

        loop_body.extend(body)

        # async for item in iterable:
        stmts.append(
            ast.AsyncFor(
                target=target,
                iter=iter_expr,
                body=loop_body,
                orelse=[],
            )
        )

        # Compile the empty block (for empty iterable)
        orelse = []
        for child in node.empty:
            orelse.extend(self._compile_node(child))

        # if not _had_items_N: ... empty block ...
        if orelse:
            stmts.append(
                ast.If(
                    test=ast.UnaryOp(
                        op=ast.Not(),
                        operand=ast.Name(id=had_items_var, ctx=ast.Load()),
                    ),
                    body=orelse,
                    orelse=[],
                )
            )

        # Remove loop variables from locals and loop_vars after the loop
        for var_name in var_names:
            self._locals.discard(var_name)
            self._loop_vars.discard(var_name)
        if uses_loop:
            self._locals.discard("loop")
            self._loop_vars.discard("loop")

        return stmts

    def _extract_names(self, node: Node) -> list[str]:
        """Extract variable names from a target expression."""
        from kida.nodes import Name as KidaName
        from kida.nodes import Tuple as KidaTuple

        if isinstance(node, KidaName):
            return [node.name]
        elif isinstance(node, KidaTuple):
            names = []
            for item in node.items:
                names.extend(self._extract_names(item))
            return names
        return []
