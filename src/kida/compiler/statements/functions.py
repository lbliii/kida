"""Function statement compilation for Kida compiler.

Provides mixin for compiling function statements (def, call_block, slot).

Uses inline TYPE_CHECKING declarations for host attributes.
See: plan/rfc-mixin-protocol-typing.md
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


class FunctionCompilationMixin:
    """Mixin for compiling function statements.

    Host attributes and cross-mixin dependencies are declared via inline
    TYPE_CHECKING blocks.

    """

    # ─────────────────────────────────────────────────────────────────────────
    # Host attributes and cross-mixin dependencies (type-check only)
    # ─────────────────────────────────────────────────────────────────────────
    if TYPE_CHECKING:
        # Host attributes (from Compiler.__init__)
        _locals: set[str]

        # From ExpressionCompilationMixin
        def _compile_expr(self, node: Any, store: bool = False) -> ast.expr: ...

        # From Compiler core
        def _compile_node(self, node: Any) -> list[ast.stmt]: ...

    def _compile_def(self, node: Any) -> list[ast.stmt]:
        """Compile {% def name(args) %}...{% enddef %.

        Kida functions have true lexical scoping - they can access variables
        from their enclosing scope, unlike Jinja2 macros.

        Generates:
            def _def_name(arg1, arg2=default, *, _caller=None, _outer_ctx=ctx):
                buf = []
                ctx = {**_outer_ctx, 'arg1': arg1, 'arg2': arg2}
                if _caller:
                    ctx['caller'] = _caller
                ... body ...
                return Markup(''.join(buf))
            ctx['name'] = _def_name
        """
        def_name = node.name
        func_name = f"_def_{def_name}"

        # Build function arguments
        args_list = [ast.arg(arg=name) for name in node.args]
        defaults = [self._compile_expr(d) for d in node.defaults]

        # Build vararg and kwarg AST nodes
        vararg_node = ast.arg(arg=node.vararg) if node.vararg else None
        kwarg_node = ast.arg(arg=node.kwarg) if node.kwarg else None

        # Build context dict entries: regular args + vararg + kwarg
        ctx_keys: list[ast.expr | None] = [ast.Constant(value=name) for name in node.args]
        ctx_values: list[ast.expr] = [ast.Name(id=name, ctx=ast.Load()) for name in node.args]

        if node.vararg:
            ctx_keys.append(ast.Constant(value=node.vararg))
            ctx_values.append(ast.Name(id=node.vararg, ctx=ast.Load()))

        if node.kwarg:
            ctx_keys.append(ast.Constant(value=node.kwarg))
            ctx_values.append(ast.Name(id=node.kwarg, ctx=ast.Load()))

        # Build function body
        func_body: list[ast.stmt] = [
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
            # Create local context: ctx = {**_outer_ctx, 'arg1': arg1, ...}
            ast.Assign(
                targets=[ast.Name(id="ctx", ctx=ast.Store())],
                value=ast.Dict(
                    keys=[None, None],  # Spread operators
                    values=[
                        ast.Name(id="_outer_ctx", ctx=ast.Load()),
                        ast.Dict(keys=ctx_keys, values=ctx_values),
                    ],
                ),
            ),
            # if _caller: ctx['caller'] = _caller
            ast.If(
                test=ast.Name(id="_caller", ctx=ast.Load()),
                body=[
                    ast.Assign(
                        targets=[
                            ast.Subscript(
                                value=ast.Name(id="ctx", ctx=ast.Load()),
                                slice=ast.Constant(value="caller"),
                                ctx=ast.Store(),
                            )
                        ],
                        value=ast.Name(id="_caller", ctx=ast.Load()),
                    )
                ],
                orelse=[],
            ),
        ]

        # Add args to locals for direct access
        for arg_name in node.args:
            self._locals.add(arg_name)
        if node.vararg:
            self._locals.add(node.vararg)
        if node.kwarg:
            self._locals.add(node.kwarg)

        # Compile function body
        for child in node.body:
            func_body.extend(self._compile_node(child))

        # Remove args from locals
        for arg_name in node.args:
            self._locals.discard(arg_name)
        if node.vararg:
            self._locals.discard(node.vararg)
        if node.kwarg:
            self._locals.discard(node.kwarg)

        # return _Markup(''.join(buf))
        func_body.append(
            ast.Return(
                value=ast.Call(
                    func=ast.Name(id="_Markup", ctx=ast.Load()),
                    args=[
                        ast.Call(
                            func=ast.Attribute(
                                value=ast.Constant(value=""),
                                attr="join",
                                ctx=ast.Load(),
                            ),
                            args=[ast.Name(id="buf", ctx=ast.Load())],
                            keywords=[],
                        ),
                    ],
                    keywords=[],
                ),
            )
        )

        # Create function with _caller and _outer_ctx as keyword-only args
        # When **kwargs is used, _caller and _outer_ctx must use a different
        # mechanism since Python only allows one **kwarg. We place them as
        # keyword-only args that come before the **kwarg isn't possible in
        # Python syntax. Instead, _caller and _outer_ctx are always
        # keyword-only args, and user **kwargs is separate.
        #
        # Strategy: When **kwargs is present, we use a wrapper that splits
        # the internal kwargs (_caller, _outer_ctx) from user kwargs.
        # When no **kwargs, we use the simple approach.
        kwonlyargs = [
            ast.arg(arg="_caller"),
            ast.arg(arg="_outer_ctx"),
        ]
        kw_defaults: list[ast.expr] = [
            ast.Constant(value=None),  # _caller=None
            ast.Name(id="ctx", ctx=ast.Load()),  # _outer_ctx=ctx
        ]

        func_def = ast.FunctionDef(
            name=func_name,
            args=ast.arguments(
                posonlyargs=[],
                args=args_list,
                vararg=vararg_node,
                kwonlyargs=kwonlyargs,
                kw_defaults=kw_defaults,
                kwarg=kwarg_node,
                defaults=defaults,
            ),
            body=func_body,
            decorator_list=[],
            returns=None,
        )

        # Assign to context: ctx['name'] = _def_name
        assign = ast.Assign(
            targets=[
                ast.Subscript(
                    value=ast.Name(id="ctx", ctx=ast.Load()),
                    slice=ast.Constant(value=def_name),
                    ctx=ast.Store(),
                )
            ],
            value=ast.Name(id=func_name, ctx=ast.Load()),
        )

        return [func_def, assign]

    def _compile_call_block(self, node: Any) -> list[ast.stmt]:
        """Compile {% call func(args) %}body{% endcall %.

        Calls a function with the body content as the caller.

        Generates:
            def _caller():
                buf = []
                ... body ...
                return Markup(''.join(buf))
            _append(func(args, _caller=_caller))
        """
        stmts: list[ast.stmt] = []

        # Create caller function
        caller_body: list[ast.stmt] = [
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
        ]

        # Compile body
        for child in node.body:
            caller_body.extend(self._compile_node(child))

        # return Markup(''.join(buf))
        caller_body.append(
            ast.Return(
                value=ast.Call(
                    func=ast.Name(id="_Markup", ctx=ast.Load()),
                    args=[
                        ast.Call(
                            func=ast.Attribute(
                                value=ast.Constant(value=""),
                                attr="join",
                                ctx=ast.Load(),
                            ),
                            args=[ast.Name(id="buf", ctx=ast.Load())],
                            keywords=[],
                        ),
                    ],
                    keywords=[],
                ),
            )
        )

        # def _caller():
        caller_func = ast.FunctionDef(
            name="_caller",
            args=ast.arguments(
                posonlyargs=[],
                args=[],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            body=caller_body,
            decorator_list=[],
            returns=None,
        )
        stmts.append(caller_func)

        # Compile the call expression and add _caller keyword argument
        call_expr = self._compile_expr(node.call)

        # If it's a function call, add _caller keyword
        if isinstance(call_expr, ast.Call):
            call_expr.keywords.append(
                ast.keyword(arg="_caller", value=ast.Name(id="_caller", ctx=ast.Load()))
            )
        else:
            # Wrap in a call with _caller
            call_expr = ast.Call(
                func=call_expr,
                args=[],
                keywords=[ast.keyword(arg="_caller", value=ast.Name(id="_caller", ctx=ast.Load()))],
            )

        # _append(result)
        stmts.append(
            ast.Expr(
                value=ast.Call(
                    func=ast.Name(id="_append", ctx=ast.Load()),
                    args=[call_expr],
                    keywords=[],
                ),
            )
        )

        return stmts

    def _compile_slot(self, node: Any) -> list[ast.stmt]:
        """Compile {% slot %.

        Renders the caller content inside a {% def %}.

        Generates:
            if ctx.get('caller'):
                _append(ctx['caller']())
        """
        return [
            ast.If(
                test=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="ctx", ctx=ast.Load()),
                        attr="get",
                        ctx=ast.Load(),
                    ),
                    args=[ast.Constant(value="caller")],
                    keywords=[],
                ),
                body=[
                    ast.Expr(
                        value=ast.Call(
                            func=ast.Name(id="_append", ctx=ast.Load()),
                            args=[
                                ast.Call(
                                    func=ast.Subscript(
                                        value=ast.Name(id="ctx", ctx=ast.Load()),
                                        slice=ast.Constant(value="caller"),
                                        ctx=ast.Load(),
                                    ),
                                    args=[],
                                    keywords=[],
                                ),
                            ],
                            keywords=[],
                        ),
                    )
                ],
                orelse=[],
            )
        ]
