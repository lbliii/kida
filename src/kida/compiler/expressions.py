"""Expression compilation for Kida compiler.

Provides mixin for compiling Kida expression AST nodes to Python AST expressions.

Uses inline TYPE_CHECKING declarations for host attributes.
See: plan/rfc-mixin-protocol-typing.md
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any

from kida.exceptions import TemplateSyntaxError
from kida.utils.typo_suggestions import suggest_closest

if TYPE_CHECKING:
    from collections.abc import Sequence

    from kida.environment import Environment
    from kida.nodes import (
        Block,
        InlinedFilter,
        Node,
        NullCoalesce,
        OptionalGetattr,
        OptionalGetitem,
        Pipeline,
        Range,
        Region,
    )

# Arithmetic operators that require numeric operands (excludes +, which is polymorphic)
_ARITHMETIC_OPS = frozenset({"*", "/", "-", "**", "//", "%"})

# Types that Python's AST compiler accepts in ast.Constant nodes.
_CONSTANT_SAFE = (str, int, float, bool, type(None), bytes, tuple, frozenset, type(...))

# Node types that may produce string values (like Markup from macros)
_POTENTIALLY_STRING_NODES = frozenset({"FuncCall", "Filter"})


class ExpressionCompilationMixin:
    """Mixin for compiling expressions.

    Host attributes and cross-mixin dependencies are declared via inline
    TYPE_CHECKING blocks.

    """

    # ─────────────────────────────────────────────────────────────────────────
    # Host attributes and cross-mixin dependencies (type-check only)
    # ─────────────────────────────────────────────────────────────────────────
    if TYPE_CHECKING:
        # Host attributes (from Compiler.__init__)
        _env: Environment
        _locals: set[str]
        _block_counter: int
        _def_names: set[str]
        _blocks: dict[str, Block | Region]
        _cached_vars: set[str]
        _def_caller_stack: list[ast.expr]
        _precomputed: list[Any]
        _precomputed_ids: dict[int, int]

        # From OperatorUtilsMixin
        def _get_binop(self, op: str) -> ast.operator: ...
        def _get_unaryop(self, op: str) -> ast.unaryop: ...
        def _get_cmpop(self, op: str) -> ast.cmpop: ...

    def _precomputed_ref(self, value: object) -> ast.Name:
        """Return an ``ast.Name`` referencing a precomputed module-level binding.

        Non-constant-safe values (dict, list, set, custom objects) cannot be
        stored in ``ast.Constant`` nodes.  Instead they are collected during
        compilation and injected into the ``exec()`` namespace as ``_pc_N``.
        """
        obj_id = id(value)
        idx = self._precomputed_ids.get(obj_id)
        if idx is None:
            idx = len(self._precomputed)
            self._precomputed.append(value)
            self._precomputed_ids[obj_id] = idx
        return ast.Name(id=f"_pc_{idx}", ctx=ast.Load())

    def _get_filter_suggestion(self, name: str) -> str | None:
        """Find closest matching filter name for typo suggestions."""
        matches = suggest_closest(name, self._env._filters.keys(), limit=1)
        return matches[0] if matches else None

    def _get_test_suggestion(self, name: str) -> str | None:
        """Find closest matching test name for typo suggestions."""
        matches = suggest_closest(name, self._env._tests.keys(), limit=1)
        return matches[0] if matches else None

    def _make_deferred_lambda(self, expr: ast.expr) -> ast.Lambda:
        """Wrap an expression in a zero-arg lambda for deferred evaluation.

        Used by ``_is_defined``, ``_default_safe``, and ``_null_coalesce``
        to catch ``UndefinedError`` at runtime without evaluating the
        expression eagerly.
        """
        return ast.Lambda(
            args=ast.arguments(
                posonlyargs=[],
                args=[],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            body=expr,
        )

    def _is_potentially_string(self, node: Node) -> bool:
        """Check if node could produce a string value (macro call, filter chain).

        Used to determine when numeric coercion is needed for arithmetic operations.
        Recursively checks nested expressions to catch Filter nodes inside parentheses.

        This handles cases like (a | length) + (b | length) where the left/right
        operands are Filter nodes that need numeric coercion.
        """
        from kida.nodes import BinOp, CondExpr, Filter, FuncCall, Pipeline, UnaryOp

        # Direct match: Filter/OptionalFilter or FuncCall nodes
        if isinstance(node, (FuncCall, Filter)):
            return True

        # Pipeline/SafePipeline nodes contain filters, need coercion
        if isinstance(node, Pipeline):
            return True

        # Recursive check for nested expressions that might contain filters
        # This handles cases like (a | length) + (b | length) where
        # the left/right operands are Filter nodes
        if isinstance(node, BinOp):
            # Check both operands recursively
            return self._is_potentially_string(node.left) or self._is_potentially_string(node.right)

        if isinstance(node, UnaryOp):
            # Check the operand recursively
            return self._is_potentially_string(node.operand)

        # For CondExpr (ternary), check all branches
        if isinstance(node, CondExpr):
            return (
                self._is_potentially_string(node.test)
                or self._is_potentially_string(node.if_true)
                or self._is_potentially_string(node.if_false)
            )

        return False

    def _wrap_coerce_numeric(self, expr: ast.expr) -> ast.expr:
        """Wrap expression in _coerce_numeric() call for arithmetic safety.

        Ensures that Markup objects (from macros) are converted to numbers
        before arithmetic operations, preventing string multiplication.
        """
        return ast.Call(
            func=ast.Name(id="_coerce_numeric", ctx=ast.Load()),
            args=[expr],
            keywords=[],
        )

    def _compile_expr(self, node: Node, store: bool = False) -> ast.expr:
        """Compile expression node to Python AST expression.

        Complexity: O(1) dispatch + O(d) for recursive expressions.
        """
        from kida.nodes import (
            Await,
            BinOp,
            BoolOp,
            Compare,
            CondExpr,
            Const,
            Filter,
            FuncCall,
            Getattr,
            Getitem,
            InlinedFilter,
            ListComp,
            Name,
            NullCoalesce,
            OptionalFilter,
            OptionalGetattr,
            OptionalGetitem,
            Pipeline,
            Range,
            SafePipeline,
            Slice,
            Test,
            UnaryOp,
        )
        from kida.nodes import Dict as KidaDict
        from kida.nodes import List as KidaList
        from kida.nodes import Tuple as KidaTuple

        # Fast path for common types
        if isinstance(node, Const):
            if isinstance(node.value, _CONSTANT_SAFE):
                return ast.Constant(value=node.value)
            return self._precomputed_ref(node.value)

        if isinstance(node, Name):
            ctx = ast.Store() if store else ast.Load()
            if store:
                return ast.Name(id=node.name, ctx=ctx)
            # Optimization: check if this is a local variable (loop var, etc.)
            # Locals use O(1) LOAD_FAST instead of O(1) dict lookup + hash
            if node.name in self._locals:
                return ast.Name(id=node.name, ctx=ast.Load())

            # CSE: use cached variable if available (avoids repeated _ls() calls)
            if node.name in self._cached_vars:
                return ast.Name(id=f"_cv_{node.name}", ctx=ast.Load())

            # Strict mode: check scope stack first, then ctx
            # _ls(ctx, _scope_stack, name) checks scopes then ctx
            # _ls is a LOAD_FAST alias for _lookup_scope (cached in preamble)
            # When compiling for thunks, use override names (e.g. _thunk_ctx, _thunk_scope)
            ctx_name = getattr(self, "_ctx_override", None) or "ctx"
            scope_name = getattr(self, "_scope_override", None) or "_scope_stack"
            # Use _ls (cached local) when available, fall back to _lookup_scope for thunks
            lookup_name = "_ls" if ctx_name == "ctx" else "_lookup_scope"
            return ast.Call(
                func=ast.Name(id=lookup_name, ctx=ast.Load()),
                args=[
                    ast.Name(id=ctx_name, ctx=ast.Load()),
                    ast.Name(id=scope_name, ctx=ast.Load()),
                    ast.Constant(value=node.name),
                ],
                keywords=[],
            )

        if isinstance(node, KidaTuple):
            ctx = ast.Store() if store else ast.Load()
            return ast.Tuple(
                elts=[self._compile_expr(e, store) for e in node.items],
                ctx=ctx,
            )

        if isinstance(node, KidaList):
            return ast.List(
                elts=[self._compile_expr(e) for e in node.items],
                ctx=ast.Load(),
            )

        if isinstance(node, ListComp):
            # Register comprehension variables as locals so elt/ifs compile
            # as LOAD_FAST (Name) instead of _ls() context lookups.
            var_names = self._extract_names(node.target)  # type: ignore[attr-defined]
            prev_locals = {v for v in var_names if v in self._locals}
            for v in var_names:
                self._locals.add(v)

            result = ast.ListComp(
                elt=self._compile_expr(node.elt),
                generators=[
                    ast.comprehension(
                        target=self._compile_expr(node.target, store=True),
                        iter=self._compile_expr(node.iter),
                        ifs=[self._compile_expr(c) for c in node.ifs],
                        is_async=0,
                    )
                ],
            )

            # Restore locals — only discard what this comprehension added
            for v in var_names:
                if v not in prev_locals:
                    self._locals.discard(v)

            return result

        if isinstance(node, KidaDict):
            return ast.Dict(
                keys=[self._compile_expr(k) for k in node.keys],
                values=[self._compile_expr(v) for v in node.values],
            )

        if isinstance(node, Getattr):
            # Use _ga (cached _getattr) for LOAD_FAST instead of LOAD_GLOBAL.
            # Thunk mode uses _getattr directly (no preamble in thunk functions).
            ga_name = "_getattr" if getattr(self, "_ctx_override", None) else "_ga"
            return ast.Call(
                func=ast.Name(id=ga_name, ctx=ast.Load()),
                args=[
                    self._compile_expr(node.obj),
                    ast.Constant(value=node.attr),
                ],
                keywords=[],
            )

        if isinstance(node, Getitem):
            return ast.Subscript(
                value=self._compile_expr(node.obj),
                slice=self._compile_expr(node.key),
                ctx=ast.Load(),
            )

        if isinstance(node, Slice):
            # Compile slice to Python slice object
            return ast.Slice(
                lower=self._compile_expr(node.start) if node.start else None,
                upper=self._compile_expr(node.stop) if node.stop else None,
                step=self._compile_expr(node.step) if node.step else None,
            )

        if isinstance(node, Test):
            # Special handling for 'defined' and 'undefined' tests
            # These need to work even when the value is undefined
            if node.name in ("defined", "undefined"):
                # Generate: _is_defined(lambda: <value>) or not _is_defined(lambda: <value>)
                value_lambda = self._make_deferred_lambda(self._compile_expr(node.value))
                test_call = ast.Call(
                    func=ast.Name(id="_is_defined", ctx=ast.Load()),
                    args=[value_lambda],
                    keywords=[],
                )
                # For 'undefined' test, negate the result
                if node.name == "undefined":
                    test_call = ast.UnaryOp(op=ast.Not(), operand=test_call)
                # Handle negated tests (is not defined, is not undefined)
                if node.negated:
                    return ast.UnaryOp(op=ast.Not(), operand=test_call)
                return test_call

            # Validate test exists at compile time
            if node.name not in self._env._tests:
                suggestion = self._get_test_suggestion(node.name)
                msg = f"Unknown test '{node.name}'"
                if suggestion:
                    msg += f". Did you mean '{suggestion}'?"
                raise TemplateSyntaxError(msg, lineno=getattr(node, "lineno", None))

            # Compile test: _tests['name'](value, *args, **kwargs)
            # If negated: not _tests['name'](value, *args, **kwargs)
            value = self._compile_expr(node.value)
            test_call = ast.Call(
                func=ast.Subscript(
                    value=ast.Name(id="_tests", ctx=ast.Load()),
                    slice=ast.Constant(value=node.name),
                    ctx=ast.Load(),
                ),
                args=[value] + [self._compile_expr(a) for a in node.args],
                keywords=[
                    ast.keyword(arg=k, value=self._compile_expr(v)) for k, v in node.kwargs.items()
                ],
            )
            if node.negated:
                return ast.UnaryOp(op=ast.Not(), operand=test_call)
            return test_call

        if isinstance(node, FuncCall):
            # obj?.method() — short-circuit call when obj is None or attr is UNDEFINED
            if isinstance(node.func, OptionalGetattr):
                return self._compile_optional_method_call(node.func, node.args, node.kwargs)

            # Lexical caller scoping: caller() in call body inside def → use enclosing _caller
            outer = getattr(self, "_outer_caller_expr", None)
            if outer is not None and isinstance(node.func, Name) and node.func.name == "caller":
                return ast.Call(
                    func=outer,
                    args=[self._compile_expr(a) for a in node.args],
                    keywords=[
                        ast.keyword(arg=k, value=self._compile_expr(v))
                        for k, v in node.kwargs.items()
                    ],
                )

            keywords = [
                ast.keyword(arg=k, value=self._compile_expr(v)) for k, v in node.kwargs.items()
            ]
            # Region callables require _outer_ctx=ctx and _blocks (RFC: kida-regions)
            func_name = getattr(node.func, "name", None)
            if func_name and func_name in getattr(self, "_blocks", {}):
                from kida.nodes import Region

                if isinstance(self._blocks.get(func_name), Region):
                    keywords.append(
                        ast.keyword(
                            arg="_outer_ctx",
                            value=ast.Name(id="ctx", ctx=ast.Load()),
                        )
                    )
                    blocks_value = (
                        ast.Dict(keys=[], values=[])
                        if self._def_caller_stack
                        else ast.Name(id="_blocks", ctx=ast.Load())
                    )
                    keywords.append(ast.keyword(arg="_blocks", value=blocks_value))
            call_node = ast.Call(
                func=self._compile_expr(node.func),
                args=[self._compile_expr(a) for a in node.args],
                keywords=keywords,
            )
            # Profiling: record macro call when target is a known {% def %} name
            # Skip when inside {% call %} block (needs raw ast.Call for _caller kwarg)
            # Skip entirely when profiling is disabled at compile time
            func_name = getattr(node.func, "name", None)
            skip = getattr(self, "_skip_macro_instrumentation", False)
            if (
                self._env.enable_profiling
                and func_name
                and func_name in self._def_names
                and not skip
            ):
                return ast.Call(
                    func=ast.Name(id="_record_macro", ctx=ast.Load()),
                    args=[
                        ast.Name(id="_acc", ctx=ast.Load()),
                        ast.Constant(value=func_name),
                        call_node,
                    ],
                    keywords=[],
                )
            return call_node

        # OptionalFilter before Filter (subclass before parent)
        if isinstance(node, OptionalFilter):
            return self._compile_optional_filter(node)

        if isinstance(node, Filter):
            # Validate filter exists at compile time
            # Special case: 'default' and 'd' are handled specially below but still valid
            if node.name not in self._env._filters:
                suggestion = self._get_filter_suggestion(node.name)
                msg = f"Unknown filter '{node.name}'"
                if suggestion:
                    msg += f". Did you mean '{suggestion}'?"
                raise TemplateSyntaxError(msg, lineno=getattr(node, "lineno", None))

            # Special handling for 'default' filter
            # The default filter needs to work even when the value is undefined
            if node.name in ("default", "d"):
                # Generate: _default_safe(lambda: <value>, <default>, <boolean>)
                # This catches UndefinedError and returns the default value
                value_lambda = self._make_deferred_lambda(self._compile_expr(node.value))
                # Build args: default_value and boolean flag
                filter_args = [self._compile_expr(a) for a in node.args]
                filter_kwargs = {k: self._compile_expr(v) for k, v in node.kwargs.items()}

                default_call = ast.Call(
                    func=ast.Name(id="_default_safe", ctx=ast.Load()),
                    args=[value_lambda, *filter_args],
                    keywords=[ast.keyword(arg=k, value=v) for k, v in filter_kwargs.items()],
                )
                # Thunk mode or profiling disabled: skip profiling wrapper
                if getattr(self, "_ctx_override", None) or not self._env.enable_profiling:
                    return default_call
                return ast.Call(
                    func=ast.Name(id="_record_filter", ctx=ast.Load()),
                    args=[
                        ast.Name(id="_acc", ctx=ast.Load()),
                        ast.Constant(value="default"),
                        default_call,
                    ],
                    keywords=[],
                )

            value = self._compile_expr(node.value)
            filter_call = ast.Call(
                func=ast.Subscript(
                    value=ast.Name(id="_filters", ctx=ast.Load()),
                    slice=ast.Constant(value=node.name),
                    ctx=ast.Load(),
                ),
                args=[value] + [self._compile_expr(a) for a in node.args],
                keywords=[
                    ast.keyword(arg=k, value=self._compile_expr(v)) for k, v in node.kwargs.items()
                ],
            )
            # Thunk mode or profiling disabled: skip profiling wrapper
            if getattr(self, "_ctx_override", None) or not self._env.enable_profiling:
                return filter_call
            return ast.Call(
                func=ast.Name(id="_record_filter", ctx=ast.Load()),
                args=[
                    ast.Name(id="_acc", ctx=ast.Load()),
                    ast.Constant(value=node.name),
                    filter_call,
                ],
                keywords=[],
            )

        if isinstance(node, BinOp):
            # Special handling for ~ (string concatenation)
            if node.op == "~":
                # _markup_concat(left, right) — preserves Markup safety
                return ast.Call(
                    func=ast.Name(id="_markup_concat", ctx=ast.Load()),
                    args=[
                        self._compile_expr(node.left),
                        self._compile_expr(node.right),
                    ],
                    keywords=[],
                )

            # Polymorphic +: add if both numeric, else string concatenation
            if node.op == "+":
                left = self._compile_expr(node.left)
                right = self._compile_expr(node.right)
                return ast.Call(
                    func=ast.Name(id="_add_polymorphic", ctx=ast.Load()),
                    args=[left, right],
                    keywords=[],
                )

            # For arithmetic ops, coerce potential string operands (from macros) to numeric
            # This prevents string multiplication when macro returns Markup('1')
            if node.op in _ARITHMETIC_OPS:
                left = self._compile_expr(node.left)
                right = self._compile_expr(node.right)

                # Wrap FuncCall/Filter results in numeric coercion
                if self._is_potentially_string(node.left):
                    left = self._wrap_coerce_numeric(left)
                if self._is_potentially_string(node.right):
                    right = self._wrap_coerce_numeric(right)

                return ast.BinOp(
                    left=left,
                    op=self._get_binop(node.op),
                    right=right,
                )

            return ast.BinOp(
                left=self._compile_expr(node.left),
                op=self._get_binop(node.op),
                right=self._compile_expr(node.right),
            )

        if isinstance(node, UnaryOp):
            return ast.UnaryOp(
                op=self._get_unaryop(node.op),
                operand=self._compile_expr(node.operand),
            )

        if isinstance(node, Compare):
            return ast.Compare(
                left=self._compile_expr(node.left),
                ops=[self._get_cmpop(op) for op in node.ops],
                comparators=[self._compile_expr(c) for c in node.comparators],
            )

        if isinstance(node, BoolOp):
            op = ast.And() if node.op == "and" else ast.Or()
            return ast.BoolOp(
                op=op,
                values=[self._compile_expr(v) for v in node.values],
            )

        if isinstance(node, CondExpr):
            return ast.IfExp(
                test=self._compile_expr(node.test),
                body=self._compile_expr(node.if_true),
                orelse=self._compile_expr(node.if_false),
            )

        # SafePipeline before Pipeline (subclass before parent)
        if isinstance(node, SafePipeline):
            return self._compile_safe_pipeline(node)

        if isinstance(node, Pipeline):
            return self._compile_pipeline(node)

        if isinstance(node, InlinedFilter):
            return self._compile_inlined_filter(node)

        if isinstance(node, NullCoalesce):
            return self._compile_null_coalesce(node)

        if isinstance(node, OptionalGetattr):
            return self._compile_optional_getattr(node)

        if isinstance(node, OptionalGetitem):
            return self._compile_optional_getitem(node)

        if isinstance(node, Range):
            return self._compile_range(node)

        if isinstance(node, Await):
            # Compile {{ await expr }} to ast.Await(value=compiled_expr)
            # Part of RFC: rfc-async-rendering
            self._has_async = True
            if getattr(self, "_async_mode", False):
                return ast.Await(value=self._compile_expr(node.value))
            # In sync mode, Await can't appear in a regular def.
            # Return a placeholder — the Template guard prevents this path.
            return ast.Constant(value="")

        # Fallback
        return ast.Constant(value=None)

    def _compile_null_coalesce(self, node: NullCoalesce) -> ast.expr:
        """Compile a ?? b to handle both None and undefined variables.

        Uses _null_coalesce helper to catch UndefinedError for undefined variables.
        Part of RFC: kida-modern-syntax-features.

        The helper is called as:
            _null_coalesce(lambda: a, lambda: b)

        This allows:
        - a ?? b to return b if a is undefined (UndefinedError)
        - a ?? b to return b if a is None
        - a ?? b to return a if a is any other value (including falsy: 0, '', [])
        """
        left = self._compile_expr(node.left)
        right = self._compile_expr(node.right)

        # _null_coalesce(lambda: left, lambda: right)
        return ast.Call(
            func=ast.Name(id="_null_coalesce", ctx=ast.Load()),
            args=[
                self._make_deferred_lambda(left),
                self._make_deferred_lambda(right),
            ],
            keywords=[],
        )

    def _compile_optional_getattr(self, node: OptionalGetattr) -> ast.expr:
        """Compile obj?.attr using walrus operator to avoid double evaluation.

        obj?.attr compiles to:
            '' if (_oc := obj) is None else (_oc_val := _getattr_none(_oc, 'attr')) if _oc_val is not None else ''

        The double check ensures that:
        1. If obj is None, return ''
        2. If obj.attr is None, return '' (for output) but preserve None for ??

        For null coalescing to work, we need a different approach: the optional
        chain preserves None so ?? can check it, but for direct output, None becomes ''.

        Actually, we return None but rely on the caller to handle None → '' conversion.
        For output, the expression is wrapped differently.

        Simplified: Return None when short-circuiting, let output handle conversion.

        Part of RFC: kida-modern-syntax-features.
        """
        self._block_counter += 1
        tmp_name = f"_oc_{self._block_counter}"

        obj = self._compile_expr(node.obj)

        # None if (_oc_N := obj) is None else _getattr_none(_oc_N, 'attr')
        # Uses _getattr_none to preserve None values for null coalescing
        return ast.IfExp(
            test=ast.Compare(
                left=ast.NamedExpr(
                    target=ast.Name(id=tmp_name, ctx=ast.Store()),
                    value=obj,
                ),
                ops=[ast.Is()],
                comparators=[ast.Constant(value=None)],
            ),
            body=ast.Constant(value=None),
            orelse=ast.Call(
                func=ast.Name(id="_getattr_none", ctx=ast.Load()),
                args=[
                    ast.Name(id=tmp_name, ctx=ast.Load()),
                    ast.Constant(value=node.attr),
                ],
                keywords=[],
            ),
        )

    def _compile_optional_getitem(self, node: OptionalGetitem) -> ast.expr:
        """Compile obj?[key] using walrus operator to avoid double evaluation.

        obj?[key] compiles to:
            None if (_oc := obj) is None else _oc[key]

        Part of RFC: kida-modern-syntax-features.
        """
        self._block_counter += 1
        tmp_name = f"_oc_{self._block_counter}"

        obj = self._compile_expr(node.obj)
        key = self._compile_expr(node.key)

        # None if (_oc_N := obj) is None else _oc_N[key]
        return ast.IfExp(
            test=ast.Compare(
                left=ast.NamedExpr(
                    target=ast.Name(id=tmp_name, ctx=ast.Store()),
                    value=obj,
                ),
                ops=[ast.Is()],
                comparators=[ast.Constant(value=None)],
            ),
            body=ast.Constant(value=None),
            orelse=ast.Subscript(
                value=ast.Name(id=tmp_name, ctx=ast.Load()),
                slice=key,
                ctx=ast.Load(),
            ),
        )

    def _compile_optional_method_call(
        self,
        opt_getattr: OptionalGetattr,
        args: Sequence[Any],
        kwargs: dict[str, Any],
    ) -> ast.expr:
        """Compile obj?.method(*args, **kwargs) with short-circuit.

        When obj is None or obj.method is UNDEFINED, return None without calling.
        Uses _optional_call(callee, *args, **kwargs) helper.
        """
        self._block_counter += 1
        tmp_name = f"_oc_{self._block_counter}"

        obj = self._compile_expr(opt_getattr.obj)
        attr_val = ast.IfExp(
            test=ast.Compare(
                left=ast.NamedExpr(
                    target=ast.Name(id=tmp_name, ctx=ast.Store()),
                    value=obj,
                ),
                ops=[ast.Is()],
                comparators=[ast.Constant(value=None)],
            ),
            body=ast.Constant(value=None),
            orelse=ast.Call(
                func=ast.Name(id="_getattr_none", ctx=ast.Load()),
                args=[
                    ast.Name(id=tmp_name, ctx=ast.Load()),
                    ast.Constant(value=opt_getattr.attr),
                ],
                keywords=[],
            ),
        )
        return ast.Call(
            func=ast.Name(id="_optional_call", ctx=ast.Load()),
            args=[attr_val] + [self._compile_expr(a) for a in args],
            keywords=[ast.keyword(arg=k, value=self._compile_expr(v)) for k, v in kwargs.items()],
        )

    def _compile_range(self, node: Range) -> ast.expr:
        """Compile range literal to range() call.

        1..10    → range(1, 11)      # inclusive
        1...11   → range(1, 11)      # exclusive
        1..10 by 2 → range(1, 11, 2)

        Part of RFC: kida-modern-syntax-features.
        """
        start = self._compile_expr(node.start)
        end = self._compile_expr(node.end)

        if node.inclusive:
            # Inclusive: 1..10 → range(1, 11)
            end = ast.BinOp(left=end, op=ast.Add(), right=ast.Constant(value=1))

        args = [start, end]
        if node.step:
            args.append(self._compile_expr(node.step))

        return ast.Call(
            func=ast.Name(id="_range", ctx=ast.Load()),
            args=args,
            keywords=[],
        )

    def _compile_inlined_filter(self, node: InlinedFilter) -> ast.Call:
        """Compile inlined filter to direct method call.

        Generates: _str(value).method(*args)

        This replaces filter dispatch overhead with a direct method call,
        providing ~5-10% speedup for filter-heavy templates.
        """
        # _str(value) - use _str from namespace, not builtin str
        str_call = ast.Call(
            func=ast.Name(id="_str", ctx=ast.Load()),
            args=[self._compile_expr(node.value)],
            keywords=[],
        )

        # str(value).method
        method_attr = ast.Attribute(
            value=str_call,
            attr=node.method,
            ctx=ast.Load(),
        )

        # str(value).method(*args)
        return ast.Call(
            func=method_attr,
            args=[self._compile_expr(arg) for arg in node.args],
            keywords=[],
        )

    def _compile_optional_filter(self, node: Any) -> ast.expr:
        """Compile expr ?| filter — skip filter if value is None.

        expr ?| upper  compiles to:
            None if (_of_N := expr) is None else _filters['upper'](_of_N)
        """
        self._block_counter += 1
        tmp_name = f"_of_{self._block_counter}"

        # Validate filter exists at compile time
        if node.name not in self._env._filters:
            suggestion = self._get_filter_suggestion(node.name)
            msg = f"Unknown filter '{node.name}'"
            if suggestion:
                msg += f". Did you mean '{suggestion}'?"
            raise TemplateSyntaxError(msg, lineno=getattr(node, "lineno", None))

        value = self._compile_expr(node.value)
        compiled_args = [self._compile_expr(arg) for arg in node.args]
        compiled_kwargs = [
            ast.keyword(arg=k, value=self._compile_expr(v)) for k, v in node.kwargs.items()
        ]

        filter_call = ast.Call(
            func=ast.Subscript(
                value=ast.Name(id="_filters", ctx=ast.Load()),
                slice=ast.Constant(value=node.name),
                ctx=ast.Load(),
            ),
            args=[ast.Name(id=tmp_name, ctx=ast.Load()), *compiled_args],
            keywords=compiled_kwargs,
        )

        if self._env.enable_profiling:
            filter_call = ast.Call(
                func=ast.Name(id="_record_filter", ctx=ast.Load()),
                args=[
                    ast.Name(id="_acc", ctx=ast.Load()),
                    ast.Constant(value=node.name),
                    filter_call,
                ],
                keywords=[],
            )

        # None if (_of_N := value) is None else _filters['name'](_of_N, ...)
        return ast.IfExp(
            test=ast.Compare(
                left=ast.NamedExpr(
                    target=ast.Name(id=tmp_name, ctx=ast.Store()),
                    value=value,
                ),
                ops=[ast.Is()],
                comparators=[ast.Constant(value=None)],
            ),
            body=ast.Constant(value=None),
            orelse=filter_call,
        )

    def _compile_pipeline(self, node: Pipeline) -> ast.expr:
        """Compile pipeline: expr |> filter1 |> filter2.

        Pipelines compile to nested filter calls using the _filters dict,
        exactly like regular filter chains. The difference is purely syntactic.

        expr |> a |> b(x)  →  _filters['b'](_filters['a'](expr), x)

        Validates filter existence at compile time (same as Filter nodes).
        """
        result = self._compile_expr(node.value)

        for filter_name, args, kwargs in node.steps:
            # Validate filter exists at compile time
            if filter_name not in self._env._filters:
                suggestion = self._get_filter_suggestion(filter_name)
                msg = f"Unknown filter '{filter_name}'"
                if suggestion:
                    msg += f". Did you mean '{suggestion}'?"
                raise TemplateSyntaxError(msg, lineno=getattr(node, "lineno", None))

            # Compile filter arguments
            compiled_args = [self._compile_expr(arg) for arg in args]
            compiled_kwargs = [
                ast.keyword(arg=k, value=self._compile_expr(v)) for k, v in kwargs.items()
            ]

            # Call: _filters['filter_name'](prev_result, *args, **kwargs)
            filter_call = ast.Call(
                func=ast.Subscript(
                    value=ast.Name(id="_filters", ctx=ast.Load()),
                    slice=ast.Constant(value=filter_name),
                    ctx=ast.Load(),
                ),
                args=[result, *compiled_args],
                keywords=compiled_kwargs,
            )

            # Profiling: _record_filter(_acc, 'name', filter_result)
            if self._env.enable_profiling:
                result = ast.Call(
                    func=ast.Name(id="_record_filter", ctx=ast.Load()),
                    args=[
                        ast.Name(id="_acc", ctx=ast.Load()),
                        ast.Constant(value=filter_name),
                        filter_call,
                    ],
                    keywords=[],
                )
            else:
                result = filter_call

        return result

    def _compile_safe_pipeline(self, node: Any) -> ast.expr:
        """Compile safe pipeline: expr ?|> filter1 ?|> filter2.

        None-propagating: each step checks for None before applying the filter.

        expr ?|> a ?|> b(x)  compiles to:
            _sp_2 = None if (_sp_1 := expr) is None else _filters['a'](_sp_1)
            None if _sp_2 is None else _filters['b'](_sp_2, x)
        """
        result = self._compile_expr(node.value)

        for filter_name, args, kwargs in node.steps:
            # Validate filter exists at compile time
            if filter_name not in self._env._filters:
                suggestion = self._get_filter_suggestion(filter_name)
                msg = f"Unknown filter '{filter_name}'"
                if suggestion:
                    msg += f". Did you mean '{suggestion}'?"
                raise TemplateSyntaxError(msg, lineno=getattr(node, "lineno", None))

            self._block_counter += 1
            tmp_name = f"_sp_{self._block_counter}"

            compiled_args = [self._compile_expr(arg) for arg in args]
            compiled_kwargs = [
                ast.keyword(arg=k, value=self._compile_expr(v)) for k, v in kwargs.items()
            ]

            filter_call = ast.Call(
                func=ast.Subscript(
                    value=ast.Name(id="_filters", ctx=ast.Load()),
                    slice=ast.Constant(value=filter_name),
                    ctx=ast.Load(),
                ),
                args=[ast.Name(id=tmp_name, ctx=ast.Load()), *compiled_args],
                keywords=compiled_kwargs,
            )

            if self._env.enable_profiling:
                filter_call = ast.Call(
                    func=ast.Name(id="_record_filter", ctx=ast.Load()),
                    args=[
                        ast.Name(id="_acc", ctx=ast.Load()),
                        ast.Constant(value=filter_name),
                        filter_call,
                    ],
                    keywords=[],
                )

            # None if (_sp_N := prev) is None else _filters['name'](_sp_N, ...)
            result = ast.IfExp(
                test=ast.Compare(
                    left=ast.NamedExpr(
                        target=ast.Name(id=tmp_name, ctx=ast.Store()),
                        value=result,
                    ),
                    ops=[ast.Is()],
                    comparators=[ast.Constant(value=None)],
                ),
                body=ast.Constant(value=None),
                orelse=filter_call,
            )

        return result
