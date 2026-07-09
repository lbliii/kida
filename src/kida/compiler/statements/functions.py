"""Function statement compilation for Kida compiler.

Provides mixin for compiling function statements (def, call_block, slot).

Uses inline TYPE_CHECKING declarations for host attributes.
See: plan/rfc-mixin-protocol-typing.md
"""

from __future__ import annotations

import ast
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

    from kida.nodes import CallBlock, Def, Node, Region, Slot

logger = logging.getLogger(__name__)


class FunctionCompilationMixin:
    """Mixin for compiling function statements.

    Host attributes and cross-mixin dependencies are declared via inline
    TYPE_CHECKING blocks.

    """

    # ─────────────────────────────────────────────────────────────────────────
    # Host attributes and cross-mixin dependencies (type-check only)
    # ─────────────────────────────────────────────────────────────────────────
    if TYPE_CHECKING:
        from kida.environment import Environment

        # Host attributes (from Compiler.__init__)
        _env: Environment
        _locals: set[str]
        _def_names: set[str]
        _def_caller_stack: list[ast.expr]

        # From ExpressionCompilationMixin
        def _compile_expr(self, node: Node, store: bool = False) -> ast.expr: ...

        # From Compiler core
        def _compile_node(self, node: Node) -> list[ast.stmt]: ...
        def _lowering_mode(
            self,
            *,
            streaming: bool | None = None,
            async_mode: bool | None = None,
        ) -> AbstractContextManager[None]: ...

    @staticmethod
    def _parse_annotation(raw: str) -> ast.expr | None:
        """Convert a raw annotation string to a Python AST expression node.

        Uses ``ast.parse`` in eval mode to parse annotation text like
        ``"str | None"`` into the corresponding AST. Falls back to None
        for malformed annotations.

        Args:
            raw: Annotation text from the template source.

        Returns:
            AST expression node, or None if parsing fails.
        """
        try:
            return ast.parse(raw, mode="eval").body
        except SyntaxError:
            logger.warning("Malformed type annotation in {%% def %%}: %r", raw)
            return None

    def _make_callable_preamble(self, *, include_scope_stack: bool = False) -> list[ast.stmt]:
        """Build common local runtime preamble for callable codegen paths."""
        stmts: list[ast.stmt] = [
            ast.Assign(
                targets=[ast.Name(id="_e", ctx=ast.Store())],
                value=ast.Name(id="_escape", ctx=ast.Load()),
            ),
            ast.Assign(
                targets=[ast.Name(id="_s", ctx=ast.Store())],
                value=ast.Name(id="_str", ctx=ast.Load()),
            ),
            # Cache _lookup_scope as _ls for LOAD_FAST
            ast.Assign(
                targets=[ast.Name(id="_ls", ctx=ast.Store())],
                value=ast.Name(id="_lookup_scope", ctx=ast.Load()),
            ),
            # Cache _getattr as _ga for LOAD_FAST (called on every dot-access)
            ast.Assign(
                targets=[ast.Name(id="_ga", ctx=ast.Store())],
                value=ast.Name(id="_getattr", ctx=ast.Load()),
            ),
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
        # Only emit _acc = _get_accumulator() when profiling is enabled.
        # Eliminates a ContextVar.get() call per function when profiling is off.
        if self._env.enable_profiling:
            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id="_acc", ctx=ast.Store())],
                    value=ast.Call(
                        func=ast.Name(id="_get_accumulator", ctx=ast.Load()),
                        args=[],
                        keywords=[],
                    ),
                ),
            )
        if include_scope_stack:
            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id="_scope_stack", ctx=ast.Store())],
                    value=ast.List(elts=[], ctx=ast.Load()),
                )
            )
        # Cache render context for line tracking (same as _make_runtime_preamble)
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

    def _compile_def(self, node: Def) -> list[ast.stmt]:
        """Compile {% def name(params) %}...{% enddef %.

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
        from kida.compiler.callable_plans import plan_def_signature

        plan = plan_def_signature(node)
        def_name = plan.public_name
        func_name = plan.function_name
        # Track for profiling: FuncCall to this name will be instrumented
        self._def_names.add(def_name)

        # Lower the immutable semantic signature into Python AST.
        args_list = [
            ast.arg(
                arg=parameter.name,
                annotation=(
                    self._parse_annotation(parameter.annotation) if parameter.annotation else None
                ),
            )
            for parameter in plan.parameters
        ]
        ctx_keys: list[ast.expr | None] = [ast.Constant(value=name) for name in plan.bound_names]
        ctx_values: list[ast.expr] = [
            ast.Name(id=name, ctx=ast.Load()) for name in plan.bound_names
        ]
        defaults = [self._compile_expr(d) for d in node.defaults]

        # Build vararg and kwarg AST nodes
        vararg_node = ast.arg(arg=plan.vararg) if plan.vararg else None
        kwarg_node = ast.arg(arg=plan.kwarg) if plan.kwarg else None

        # Build function body
        func_body: list[ast.stmt] = [
            *self._make_callable_preamble(),
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
            # ctx['has_slot'] = (lambda: True) if _caller is not None else (lambda: False)
            # Allows {% if has_slot() %} guards inside def bodies.
            # Uses constant lambdas instead of a closure over _caller to avoid
            # creating a cell object for every def invocation.
            ast.Assign(
                targets=[
                    ast.Subscript(
                        value=ast.Name(id="ctx", ctx=ast.Load()),
                        slice=ast.Constant(value="has_slot"),
                        ctx=ast.Store(),
                    )
                ],
                value=ast.IfExp(
                    test=ast.Compare(
                        left=ast.Name(id="_caller", ctx=ast.Load()),
                        ops=[ast.IsNot()],
                        comparators=[ast.Constant(value=None)],
                    ),
                    body=ast.Lambda(
                        args=ast.arguments(
                            posonlyargs=[],
                            args=[],
                            vararg=None,
                            kwonlyargs=[],
                            kw_defaults=[],
                            kwarg=None,
                            defaults=[],
                        ),
                        body=ast.Constant(value=True),
                    ),
                    orelse=ast.Lambda(
                        args=ast.arguments(
                            posonlyargs=[],
                            args=[],
                            vararg=None,
                            kwonlyargs=[],
                            kw_defaults=[],
                            kwarg=None,
                            defaults=[],
                        ),
                        body=ast.Constant(value=False),
                    ),
                ),
            ),
        ]

        # Add args to locals for direct access
        self._locals.update(plan.bound_names)

        # Compile function body
        # Macros (def) are always sync StringBuilder functions — disable
        # async and streaming modes so surrounding render_stream compilation
        # does not turn the component body into a generator.
        # Lexical caller scoping: capture _caller to _def_caller so slot functions
        # can reference it without shadowing by the inner _caller wrapper.
        func_body.append(
            ast.Assign(
                targets=[ast.Name(id="_def_caller", ctx=ast.Store())],
                value=ast.Name(id="_caller", ctx=ast.Load()),
            )
        )

        # Component call stack: push frame on entry (Sprint 1.3)
        # Imported macro wrappers set component_call_* so this frame points to
        # the caller site while template_name/source still point at the def.
        component_template_expr = ast.BoolOp(
            op=ast.Or(),
            values=[
                ast.Attribute(
                    value=ast.Name(id="_rc", ctx=ast.Load()),
                    attr="component_call_template",
                    ctx=ast.Load(),
                ),
                ast.Attribute(
                    value=ast.Name(id="_rc", ctx=ast.Load()),
                    attr="template_name",
                    ctx=ast.Load(),
                ),
                ast.Constant(value=""),
            ],
        )
        component_line_expr = ast.IfExp(
            test=ast.Compare(
                left=ast.Attribute(
                    value=ast.Name(id="_rc", ctx=ast.Load()),
                    attr="component_call_line",
                    ctx=ast.Load(),
                ),
                ops=[ast.IsNot()],
                comparators=[ast.Constant(value=None)],
            ),
            body=ast.Attribute(
                value=ast.Name(id="_rc", ctx=ast.Load()),
                attr="component_call_line",
                ctx=ast.Load(),
            ),
            orelse=ast.Attribute(
                value=ast.Name(id="_rc", ctx=ast.Load()),
                attr="line",
                ctx=ast.Load(),
            ),
        )
        func_body.append(
            ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Attribute(
                            value=ast.Name(id="_rc", ctx=ast.Load()),
                            attr="component_stack",
                            ctx=ast.Load(),
                        ),
                        attr="append",
                        ctx=ast.Load(),
                    ),
                    args=[
                        ast.Tuple(
                            elts=[
                                component_template_expr,
                                component_line_expr,
                                ast.Constant(value=def_name),
                            ],
                            ctx=ast.Load(),
                        )
                    ],
                    keywords=[],
                ),
            )
        )

        # Compile the body statements
        inner_body: list[ast.stmt] = []
        self._def_caller_stack.append(ast.Name(id="_def_caller", ctx=ast.Load()))
        try:
            with self._lowering_mode(streaming=False, async_mode=False):
                for child in node.body:
                    inner_body.extend(self._compile_node(child))
        finally:
            self._def_caller_stack.pop()
            self._locals.difference_update(plan.bound_names)

        # return _Markup(''.join(buf))
        inner_body.append(
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

        # Wrap body in try/finally to pop component stack on exit
        # _rc.component_stack.pop()
        component_pop = ast.Expr(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Attribute(
                        value=ast.Name(id="_rc", ctx=ast.Load()),
                        attr="component_stack",
                        ctx=ast.Load(),
                    ),
                    attr="pop",
                    ctx=ast.Load(),
                ),
                args=[],
                keywords=[],
            ),
        )
        func_body.append(
            ast.Try(
                body=inner_body,
                handlers=[],
                orelse=[],
                finalbody=[component_pop],
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
        kw_defaults: list[ast.expr | None] = [
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

    def _compile_call_block(self, node: CallBlock) -> list[ast.stmt]:
        """Compile {% call func(args) %}...{% endcall %.

        Builds a caller that supports named slots. Passes _caller(slot="default")
        so both _caller() and _caller("header_actions") work.

        With scoped slots: slot functions accept **_slot_kwargs from the def-side
        bindings and push them onto the scope stack so let: params are available
        as local variables in the slot body.
        """
        from kida.compiler.callable_plans import plan_call_block

        plan = plan_call_block(node)
        stmts: list[ast.stmt] = []

        # Build one function per slot
        for slot in plan.slots:
            slot_name = slot.name
            slot_body = slot.body
            fn_name = slot.function_name

            caller_body: list[ast.stmt] = self._make_callable_preamble()

            # Scoped slots: if this slot has params, push _slot_kwargs onto scope_stack
            # so that let: bindings from the def-side are available as local variables.
            # The **_slot_kwargs parameter is always accepted (no-op when empty).
            # Wrapped in try/finally to ensure scope_stack is popped after use.
            caller_body.append(
                ast.If(
                    test=ast.Name(id="_slot_kwargs", ctx=ast.Load()),
                    body=[
                        ast.Expr(
                            value=ast.Call(
                                func=ast.Attribute(
                                    value=ast.Name(id="_scope_stack", ctx=ast.Load()),
                                    attr="append",
                                    ctx=ast.Load(),
                                ),
                                args=[ast.Name(id="_slot_kwargs", ctx=ast.Load())],
                                keywords=[],
                            ),
                        )
                    ],
                    orelse=[],
                )
            )
            # Record where the scope push ends so we can wrap subsequent
            # statements in try/finally for cleanup.
            _scope_push_idx = len(caller_body)

            outer = self._def_caller_stack[-1] if self._def_caller_stack else None
            # Use _outer_caller param to avoid shadowing by inner _caller wrapper
            if outer is not None:
                self._outer_caller_expr = ast.Name(id="_outer_caller", ctx=ast.Load())
                # Delegate to outer caller when slot body is empty (fixes nested macro slot passthrough)
                if slot.delegates_when_nested:
                    caller_body.append(
                        ast.If(
                            test=ast.Compare(
                                left=ast.Name(id="_outer_caller", ctx=ast.Load()),
                                ops=[ast.IsNot()],
                                comparators=[ast.Constant(value=None)],
                            ),
                            body=[
                                ast.Return(
                                    value=ast.Call(
                                        func=ast.Name(id="_outer_caller", ctx=ast.Load()),
                                        args=[ast.Constant(value=slot_name)],
                                        keywords=[],
                                    )
                                )
                            ],
                            orelse=[],
                        )
                    )
            # Disable CSE cached-var substitution while compiling slot
            # bodies.  Slot bodies run after _slot_kwargs are pushed onto
            # _scope_stack, so they must always resolve names via
            # _lookup_scope — never via a _cv_<name> closure captured at
            # function entry before the push.
            saved_cached_vars = self._cached_vars
            self._cached_vars = set()
            try:
                with self._lowering_mode(async_mode=False):
                    for child in slot_body:
                        caller_body.extend(self._compile_node(child))
            finally:
                self._cached_vars = saved_cached_vars
                if outer is not None:
                    self._outer_caller_expr = None

            return_stmt = ast.Return(
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

            # Wrap the body+return in try/finally to pop _slot_kwargs from scope_stack.
            # Everything after _scope_push_idx was compiled with the scope push active.
            scope_pop = ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="_scope_stack", ctx=ast.Load()),
                        attr="pop",
                        ctx=ast.Load(),
                    ),
                    args=[],
                    keywords=[],
                )
            )
            # Extract body statements after scope push, wrap in try/finally
            inner_body = caller_body[_scope_push_idx:]
            inner_body.append(return_stmt)
            caller_body[_scope_push_idx:] = [
                ast.Try(
                    body=inner_body,
                    handlers=[],
                    orelse=[],
                    finalbody=[
                        ast.If(
                            test=ast.Name(id="_slot_kwargs", ctx=ast.Load()),
                            body=[scope_pop],
                            orelse=[],
                        )
                    ],
                )
            ]

            # _scope_stack required for _lookup_scope; _outer_caller for def nesting
            # **_slot_kwargs accepts scoped slot bindings from the def-side
            slot_args: list[ast.arg] = [ast.arg(arg="_scope_stack")]
            slot_defaults: list[ast.expr] = []
            if outer is not None:
                slot_args.append(ast.arg(arg="_outer_caller"))
                slot_defaults.append(outer)
            stmts.append(
                ast.FunctionDef(
                    name=fn_name,
                    args=ast.arguments(
                        posonlyargs=[],
                        args=slot_args,
                        vararg=None,
                        kwonlyargs=[],
                        kw_defaults=[],
                        kwarg=ast.arg(arg="_slot_kwargs"),
                        defaults=slot_defaults,
                    ),
                    body=caller_body,
                    decorator_list=[],
                    returns=None,
                )
            )

        # Build _caller(slot="default", **kwargs) wrapper
        # def _caller_wrapper(_scope_stack, slot="default", **_slot_kwargs):
        #     f = _caller_slots.get(slot)
        #     return f(_scope_stack, **_slot_kwargs) if f else _Markup("")
        wrapper_call_body: list[ast.stmt] = [
            ast.Assign(
                targets=[ast.Name(id="_f", ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="_caller_slots", ctx=ast.Load()),
                        attr="get",
                        ctx=ast.Load(),
                    ),
                    args=[ast.Name(id="slot", ctx=ast.Load())],
                    keywords=[],
                ),
            ),
            ast.Return(
                value=ast.IfExp(
                    test=ast.Name(id="_f", ctx=ast.Load()),
                    body=ast.Call(
                        func=ast.Name(id="_f", ctx=ast.Load()),
                        args=[ast.Name(id="_scope_stack", ctx=ast.Load())],
                        keywords=[
                            ast.keyword(
                                arg=None,
                                value=ast.Name(id="_slot_kwargs", ctx=ast.Load()),
                            ),
                        ],
                    ),
                    orelse=ast.Call(
                        func=ast.Name(id="_Markup", ctx=ast.Load()),
                        args=[ast.Constant(value="")],
                        keywords=[],
                    ),
                ),
            ),
        ]
        wrapper_body: list[ast.stmt] = [
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
            ),
            ast.Assign(
                targets=[ast.Name(id="_prev_template_name", ctx=ast.Store())],
                value=ast.Attribute(
                    value=ast.Name(id="_rc", ctx=ast.Load()),
                    attr="template_name",
                    ctx=ast.Load(),
                ),
            ),
            ast.Assign(
                targets=[ast.Name(id="_prev_source", ctx=ast.Store())],
                value=ast.Attribute(
                    value=ast.Name(id="_rc", ctx=ast.Load()),
                    attr="source",
                    ctx=ast.Load(),
                ),
            ),
            ast.Assign(
                targets=[ast.Name(id="_prev_line", ctx=ast.Store())],
                value=ast.Attribute(
                    value=ast.Name(id="_rc", ctx=ast.Load()),
                    attr="line",
                    ctx=ast.Load(),
                ),
            ),
            ast.Assign(
                targets=[
                    ast.Attribute(
                        value=ast.Name(id="_rc", ctx=ast.Load()),
                        attr="template_name",
                        ctx=ast.Store(),
                    )
                ],
                value=ast.Name(id="_caller_template_name", ctx=ast.Load()),
            ),
            ast.Assign(
                targets=[
                    ast.Attribute(
                        value=ast.Name(id="_rc", ctx=ast.Load()),
                        attr="source",
                        ctx=ast.Store(),
                    )
                ],
                value=ast.Name(id="_caller_source", ctx=ast.Load()),
            ),
            ast.Assign(
                targets=[
                    ast.Attribute(
                        value=ast.Name(id="_rc", ctx=ast.Load()),
                        attr="line",
                        ctx=ast.Store(),
                    )
                ],
                value=ast.Name(id="_caller_line", ctx=ast.Load()),
            ),
            ast.Try(
                body=wrapper_call_body,
                handlers=[],
                orelse=[],
                finalbody=[
                    ast.Assign(
                        targets=[
                            ast.Attribute(
                                value=ast.Name(id="_rc", ctx=ast.Load()),
                                attr="template_name",
                                ctx=ast.Store(),
                            )
                        ],
                        value=ast.Name(id="_prev_template_name", ctx=ast.Load()),
                    ),
                    ast.Assign(
                        targets=[
                            ast.Attribute(
                                value=ast.Name(id="_rc", ctx=ast.Load()),
                                attr="source",
                                ctx=ast.Store(),
                            )
                        ],
                        value=ast.Name(id="_prev_source", ctx=ast.Load()),
                    ),
                    ast.Assign(
                        targets=[
                            ast.Attribute(
                                value=ast.Name(id="_rc", ctx=ast.Load()),
                                attr="line",
                                ctx=ast.Store(),
                            )
                        ],
                        value=ast.Name(id="_prev_line", ctx=ast.Load()),
                    ),
                ],
            ),
        ]
        stmts.append(
            ast.Assign(
                targets=[ast.Name(id="_caller_slots", ctx=ast.Store())],
                value=ast.Dict(
                    keys=[ast.Constant(value=name) for name, _ in plan.slot_function_items],
                    values=[
                        ast.Name(id=function_name, ctx=ast.Load())
                        for _, function_name in plan.slot_function_items
                    ],
                ),
            )
        )
        for attr, local_name in (
            ("template_name", "_caller_template_name"),
            ("source", "_caller_source"),
            ("line", "_caller_line"),
        ):
            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id=local_name, ctx=ast.Store())],
                    value=ast.Attribute(
                        value=ast.Name(id="_rc", ctx=ast.Load()),
                        attr=attr,
                        ctx=ast.Load(),
                    ),
                )
            )
        # Use _caller_wrapper to avoid shadowing the def's _caller parameter
        # (which would cause UnboundLocalError when _def_caller = _caller runs)
        # Wrapper takes (_scope_stack, slot, **_slot_kwargs) so slot functions get
        # scope for _lookup_scope and scoped bindings via kwargs
        stmts.append(
            ast.FunctionDef(
                name="_caller_wrapper",
                args=ast.arguments(
                    posonlyargs=[],
                    args=[ast.arg(arg="_scope_stack"), ast.arg(arg="slot")],
                    vararg=None,
                    kwonlyargs=[],
                    kw_defaults=[],
                    kwarg=ast.arg(arg="_slot_kwargs"),
                    defaults=[ast.Constant(value="default")],
                ),
                body=wrapper_body,
                decorator_list=[],
                returns=None,
            )
        )
        # Lambda captures _scope_stack from render scope; macro calls _caller() or _caller(slot)
        # **_slot_kwargs passes scoped bindings through the chain
        stmts.append(
            ast.Assign(
                targets=[ast.Name(id="_caller_with_scope", ctx=ast.Store())],
                value=ast.Lambda(
                    args=ast.arguments(
                        posonlyargs=[],
                        args=[ast.arg(arg="slot")],
                        vararg=None,
                        kwonlyargs=[],
                        kw_defaults=[],
                        kwarg=ast.arg(arg="_slot_kwargs"),
                        defaults=[ast.Constant(value="default")],
                    ),
                    body=ast.Call(
                        func=ast.Name(id="_caller_wrapper", ctx=ast.Load()),
                        args=[
                            ast.Name(id="_scope_stack", ctx=ast.Load()),
                            ast.Name(id="slot", ctx=ast.Load()),
                        ],
                        keywords=[
                            ast.keyword(
                                arg=None,
                                value=ast.Name(id="_slot_kwargs", ctx=ast.Load()),
                            ),
                        ],
                    ),
                ),
            )
        )

        # Compile the call expression and add _caller keyword argument
        # Suppress macro instrumentation so we get a raw ast.Call back
        saved_skip = getattr(self, "_skip_macro_instrumentation", False)
        self._skip_macro_instrumentation = True
        call_expr = self._compile_expr(plan.call)
        self._skip_macro_instrumentation = saved_skip

        # If it's a function call, add _caller keyword (lambda binds _scope_stack)
        if isinstance(call_expr, ast.Call):
            call_expr.keywords.append(
                ast.keyword(arg="_caller", value=ast.Name(id="_caller_with_scope", ctx=ast.Load()))
            )
        else:
            # Wrap in a call with _caller
            call_expr = ast.Call(
                func=call_expr,
                args=[],
                keywords=[
                    ast.keyword(
                        arg="_caller",
                        value=ast.Name(id="_caller_with_scope", ctx=ast.Load()),
                    )
                ],
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

    def _make_region_function(
        self, name: str, node: Region
    ) -> tuple[list[ast.FunctionDef], ast.FunctionDef]:
        """Generate module-level region callable: _region_name(params, *, _outer_ctx) -> Markup.

        Regions compile to both a callable (this) and a block wrapper.
        No _caller/slots — regions are parameterized renderable units only.
        Returns (thunk_defs, region_func) — thunks must be emitted before the region func.
        """
        from kida.compiler.callable_plans import plan_region_signature

        plan = plan_region_signature(node, emitted_name=name)
        func_name = plan.function_name
        ctx_keys: list[ast.expr | None] = [
            ast.Constant(value=bound_name) for bound_name in plan.bound_names
        ]
        ctx_values: list[ast.expr] = [
            ast.Name(id=bound_name, ctx=ast.Load()) for bound_name in plan.bound_names
        ]

        args_list = [
            ast.arg(
                arg=parameter.name,
                annotation=(
                    self._parse_annotation(parameter.annotation) if parameter.annotation else None
                ),
            )
            for parameter in plan.parameters
        ]
        # Use _REGION_DEFAULT for param defaults: Python evaluates defaults at def time,
        # but region defaults reference ctx/_scope_stack which don't exist during exec().
        # We resolve them at call time in the function body.
        defaults: list[ast.expr] = [
            ast.Name(id="_REGION_DEFAULT", ctx=ast.Load()) for _ in plan.default_parameter_names
        ]
        from kida.nodes.expressions import Name

        default_resolvers: list[tuple[str, str]] = []  # (param_name, lookup_key)
        thunk_resolvers: list[tuple[str, str]] = []  # (param_name, thunk_name)
        thunk_defs: list[ast.FunctionDef] = []
        for i, default_node in enumerate(node.defaults):
            param_name = plan.default_parameter_names[i]
            if isinstance(default_node, Name):
                default_resolvers.append((param_name, default_node.name))
            else:
                # Thunk path: compile expression with context-override
                self._ctx_override = "_thunk_ctx"
                self._scope_override = "_thunk_scope"
                try:
                    compiled = self._compile_expr(default_node)
                finally:
                    self._ctx_override = None
                    self._scope_override = None

                thunk_name = f"_rgn_default_{name}_{i}"
                thunk_def = ast.FunctionDef(
                    name=thunk_name,
                    args=ast.arguments(
                        posonlyargs=[],
                        args=[
                            ast.arg(arg="_thunk_ctx"),
                            ast.arg(arg="_thunk_scope"),
                        ],
                        vararg=None,
                        kwonlyargs=[],
                        kw_defaults=[],
                        kwarg=None,
                        defaults=[],
                    ),
                    body=[ast.Return(value=compiled)],
                    decorator_list=[],
                    returns=None,
                )
                thunk_defs.append(thunk_def)
                thunk_resolvers.append((param_name, thunk_name))

        vararg_node = ast.arg(arg=plan.vararg) if plan.vararg else None
        kwarg_node = ast.arg(arg=plan.kwarg) if plan.kwarg else None

        func_body = list(self._make_callable_preamble(include_scope_stack=True))

        # Resolve param defaults that reference ctx (evaluated at call time, not def time)
        for param_name, lookup_key in default_resolvers:
            func_body.append(
                ast.If(
                    test=ast.Compare(
                        left=ast.Name(id=param_name, ctx=ast.Load()),
                        ops=[ast.Is()],
                        comparators=[ast.Name(id="_REGION_DEFAULT", ctx=ast.Load())],
                    ),
                    body=[
                        ast.Assign(
                            targets=[ast.Name(id=param_name, ctx=ast.Store())],
                            value=ast.Call(
                                func=ast.Name(id="_lookup_scope", ctx=ast.Load()),
                                args=[
                                    ast.Name(id="_outer_ctx", ctx=ast.Load()),
                                    ast.Name(id="_scope_stack", ctx=ast.Load()),
                                    ast.Constant(value=lookup_key),
                                ],
                                keywords=[],
                            ),
                        )
                    ],
                    orelse=[],
                )
            )

        # Resolve complex defaults via thunks
        for param_name, thunk_name in thunk_resolvers:
            func_body.append(
                ast.If(
                    test=ast.Compare(
                        left=ast.Name(id=param_name, ctx=ast.Load()),
                        ops=[ast.Is()],
                        comparators=[ast.Name(id="_REGION_DEFAULT", ctx=ast.Load())],
                    ),
                    body=[
                        ast.Assign(
                            targets=[ast.Name(id=param_name, ctx=ast.Store())],
                            value=ast.Call(
                                func=ast.Name(id=thunk_name, ctx=ast.Load()),
                                args=[
                                    ast.Name(id="_outer_ctx", ctx=ast.Load()),
                                    ast.Name(id="_scope_stack", ctx=ast.Load()),
                                ],
                                keywords=[],
                            ),
                        )
                    ],
                    orelse=[],
                )
            )

        func_body.append(
            ast.Assign(
                targets=[ast.Name(id="ctx", ctx=ast.Store())],
                value=ast.Dict(
                    keys=[None, None],
                    values=[
                        ast.Name(id="_outer_ctx", ctx=ast.Load()),
                        ast.Dict(keys=ctx_keys, values=ctx_values),
                    ],
                ),
            ),
        )

        self._locals.update(plan.bound_names)

        try:
            with self._lowering_mode(streaming=False, async_mode=False):
                for child in node.body:
                    func_body.extend(self._compile_node(child))
        finally:
            self._locals.difference_update(plan.bound_names)

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

        region_func = ast.FunctionDef(
            name=func_name,
            args=ast.arguments(
                posonlyargs=[],
                args=args_list,
                vararg=vararg_node,
                kwonlyargs=[ast.arg(arg="_outer_ctx"), ast.arg(arg="_blocks")],
                kw_defaults=[None, None],
                kwarg=kwarg_node,
                defaults=defaults,
            ),
            body=func_body,
            decorator_list=[],
            returns=None,
        )
        return (thunk_defs, region_func)

    def _compile_region(self, node: Region) -> list[ast.stmt]:
        """Compile {% region name(params) %} for template body — emit ctx assign only."""
        func_name = f"_region_{node.name}"
        return [
            ast.Assign(
                targets=[
                    ast.Subscript(
                        value=ast.Name(id="ctx", ctx=ast.Load()),
                        slice=ast.Constant(value=node.name),
                        ctx=ast.Store(),
                    )
                ],
                value=ast.Name(id=func_name, ctx=ast.Load()),
            ),
        ]

    def _compile_slot(self, node: Slot) -> list[ast.stmt]:
        """Compile {% slot %} or {% slot name %} with optional scoped bindings.

        Renders the caller content for the given slot name.
        _caller(slot="default") supports both _caller() and _caller("name").

        With scoped bindings: {% slot row let:item=item, let:index=loop.index %}
        Passes bindings as keyword arguments to the caller function:
            _caller("row", item=item, index=loop.index)

        With body (default content): renders body when no caller is present.
        """
        from kida.compiler.callable_plans import plan_slot_render

        plan = plan_slot_render(node)
        slot_name = plan.name

        # Build caller() call with optional scoped binding kwargs
        caller_call_keywords = [
            ast.keyword(
                arg=binding.name,
                value=self._compile_expr(binding.expression),
            )
            for binding in plan.bindings
        ]

        # Compile default body content (orelse branch)
        # When bindings exist, push them onto scope_stack so the default body
        # can reference binding names, then pop in a finally block.
        orelse: list[ast.stmt] = []
        if plan.body:
            body_stmts: list[ast.stmt] = []
            for child in plan.body:
                body_stmts.extend(self._compile_node(child))
            if plan.bindings and body_stmts:
                # Push binding values onto scope, wrap body in try/finally pop
                binding_dict = ast.Dict(
                    keys=[ast.Constant(value=name) for name in plan.binding_names],
                    values=[self._compile_expr(binding.expression) for binding in plan.bindings],
                )
                orelse.append(
                    ast.Expr(
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id="_scope_stack", ctx=ast.Load()),
                                attr="append",
                                ctx=ast.Load(),
                            ),
                            args=[binding_dict],
                            keywords=[],
                        )
                    )
                )
                orelse.append(
                    ast.Try(
                        body=body_stmts,
                        handlers=[],
                        orelse=[],
                        finalbody=[
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
                            )
                        ],
                    )
                )
            else:
                orelse.extend(body_stmts)

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
                                    args=[ast.Constant(value=slot_name)],
                                    keywords=caller_call_keywords,
                                ),
                            ],
                            keywords=[],
                        ),
                    )
                ],
                orelse=orelse,
            )
        ]
