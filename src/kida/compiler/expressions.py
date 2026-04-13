"""Expression compilation for Kida compiler.

Provides mixin for compiling Kida expression AST nodes to Python AST expressions.

Uses inline TYPE_CHECKING declarations for host attributes.
See: plan/rfc-mixin-protocol-typing.md
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any, ClassVar

from kida.exceptions import ErrorCode, TemplateSyntaxError
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

# Scalar types that Python's AST compiler accepts directly in ast.Constant nodes.
# Container constants (tuple, frozenset) are only safe when all nested values are
# also constant-safe.
_CONSTANT_SAFE_SCALARS = (str, int, float, complex, bool, type(None), bytes, type(...))


def _is_constant_safe(value: object) -> bool:
    """Return True if *value* can be stored in an ``ast.Constant`` node."""
    if isinstance(value, _CONSTANT_SAFE_SCALARS):
        return True
    if isinstance(value, tuple):
        return all(_is_constant_safe(item) for item in value)
    if isinstance(value, frozenset):
        return all(_is_constant_safe(item) for item in value)
    return False


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

    # Dispatch table: node class __name__ → method name.
    # Keyed by exact type name so subclass ordering is irrelevant
    # (SafePipeline and OptionalFilter get their own entries).
    _EXPR_DISPATCH: ClassVar[dict[str, str]] = {
        "Const": "_compile_const",
        "Name": "_compile_name",
        "Tuple": "_compile_tuple",
        "List": "_compile_list",
        "ListComp": "_compile_list_comp",
        "Dict": "_compile_dict",
        "Getattr": "_compile_getattr",
        "Getitem": "_compile_getitem",
        "Slice": "_compile_slice",
        "Test": "_compile_test",
        "FuncCall": "_compile_func_call",
        "OptionalFilter": "_compile_optional_filter",
        "Filter": "_compile_filter",
        "BinOp": "_compile_binop",
        "UnaryOp": "_compile_unaryop",
        "Compare": "_compile_compare",
        "BoolOp": "_compile_boolop",
        "CondExpr": "_compile_cond_expr",
        "SafePipeline": "_compile_safe_pipeline",
        "Pipeline": "_compile_pipeline",
        "InlinedFilter": "_compile_inlined_filter",
        "NullCoalesce": "_compile_null_coalesce",
        "OptionalGetattr": "_compile_optional_getattr",
        "OptionalGetitem": "_compile_optional_getitem",
        "Range": "_compile_range",
        "Await": "_compile_await",
    }

    # Methods that accept a ``store`` keyword argument (assignment targets).
    _STORE_METHODS: frozenset[str] = frozenset({"_compile_name", "_compile_tuple"})

    def _compile_expr(self, node: Node, store: bool = False) -> ast.expr:
        """Compile expression node to Python AST expression.

        O(1) dict dispatch by ``type(node).__name__``.
        """
        method_name = self._EXPR_DISPATCH.get(type(node).__name__)
        if method_name is None:
            return ast.Constant(value=None)
        method = getattr(self, method_name)
        if store and method_name in self._STORE_METHODS:
            return method(node, store=True)
        return method(node)

    # ------------------------------------------------------------------
    # Per-node-type compilation methods (extracted from _compile_expr)
    # ------------------------------------------------------------------

    def _compile_const(self, node: Node) -> ast.expr:
        """Compile constant literal."""
        if _is_constant_safe(node.value):
            return ast.Constant(value=node.value)
        return self._precomputed_ref(node.value)

    def _compile_name(self, node: Node, *, store: bool = False) -> ast.expr:
        """Compile variable reference."""
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

    def _compile_tuple(self, node: Node, *, store: bool = False) -> ast.expr:
        """Compile tuple expression."""
        ctx = ast.Store() if store else ast.Load()
        return ast.Tuple(
            elts=[self._compile_expr(e, store) for e in node.items],
            ctx=ctx,
        )

    def _compile_list(self, node: Node) -> ast.expr:
        """Compile list expression."""
        return ast.List(
            elts=[self._compile_expr(e) for e in node.items],
            ctx=ast.Load(),
        )

    def _compile_list_comp(self, node: Node) -> ast.expr:
        """Compile list comprehension."""
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

    def _compile_dict(self, node: Node) -> ast.expr:
        """Compile dict expression."""
        return ast.Dict(
            keys=[self._compile_expr(k) for k in node.keys],
            values=[self._compile_expr(v) for v in node.values],
        )

    def _compile_getattr(self, node: Node) -> ast.expr:
        """Compile attribute access (obj.attr)."""
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

    def _compile_getitem(self, node: Node) -> ast.expr:
        """Compile subscript access (obj[key])."""
        return ast.Subscript(
            value=self._compile_expr(node.obj),
            slice=self._compile_expr(node.key),
            ctx=ast.Load(),
        )

    def _compile_slice(self, node: Node) -> ast.expr:
        """Compile slice expression (start:stop:step)."""
        return ast.Slice(
            lower=self._compile_expr(node.start) if node.start else None,
            upper=self._compile_expr(node.stop) if node.stop else None,
            step=self._compile_expr(node.step) if node.step else None,
        )

    def _compile_test(self, node: Node) -> ast.expr:
        """Compile test expression (is defined, is none, etc.)."""
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
            err = TemplateSyntaxError(msg, lineno=getattr(node, "lineno", None))
            err.code = ErrorCode.INVALID_TEST
            raise err

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

    def _compile_func_call(self, node: Node) -> ast.expr:
        """Compile function call expression."""
        from kida.nodes import Name, OptionalGetattr, Region

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
                    ast.keyword(arg=k, value=self._compile_expr(v)) for k, v in node.kwargs.items()
                ],
            )

        keywords = [ast.keyword(arg=k, value=self._compile_expr(v)) for k, v in node.kwargs.items()]
        # Region callables require _outer_ctx=ctx and _blocks (RFC: kida-regions)
        func_name = getattr(node.func, "name", None)
        if (
            func_name
            and func_name in getattr(self, "_blocks", {})
            and isinstance(self._blocks.get(func_name), Region)
        ):
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
        if self._env.enable_profiling and func_name and func_name in self._def_names and not skip:
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

    def _compile_filter(self, node: Node) -> ast.expr:
        """Compile filter expression (value | filter_name)."""
        # Validate filter exists at compile time
        # Special case: 'default' and 'd' are handled specially below but still valid
        if node.name not in self._env._filters:
            suggestion = self._get_filter_suggestion(node.name)
            msg = f"Unknown filter '{node.name}'"
            if suggestion:
                msg += f". Did you mean '{suggestion}'?"
            err = TemplateSyntaxError(msg, lineno=getattr(node, "lineno", None))
            err.code = ErrorCode.INVALID_FILTER
            raise err

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

    def _compile_binop(self, node: Node) -> ast.expr:
        """Compile binary operation."""
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

    def _compile_unaryop(self, node: Node) -> ast.expr:
        """Compile unary operation."""
        return ast.UnaryOp(
            op=self._get_unaryop(node.op),
            operand=self._compile_expr(node.operand),
        )

    def _compile_compare(self, node: Node) -> ast.expr:
        """Compile comparison expression."""
        return ast.Compare(
            left=self._compile_expr(node.left),
            ops=[self._get_cmpop(op) for op in node.ops],
            comparators=[self._compile_expr(c) for c in node.comparators],
        )

    def _compile_boolop(self, node: Node) -> ast.expr:
        """Compile boolean operation (and/or)."""
        op = ast.And() if node.op == "and" else ast.Or()
        return ast.BoolOp(
            op=op,
            values=[self._compile_expr(v) for v in node.values],
        )

    def _compile_cond_expr(self, node: Node) -> ast.expr:
        """Compile conditional (ternary) expression."""
        return ast.IfExp(
            test=self._compile_expr(node.test),
            body=self._compile_expr(node.if_true),
            orelse=self._compile_expr(node.if_false),
        )

    def _compile_await(self, node: Node) -> ast.expr:
        """Compile await expression."""
        # Compile {{ await expr }} to ast.Await(value=compiled_expr)
        # Part of RFC: rfc-async-rendering
        self._has_async = True
        if getattr(self, "_async_mode", False):
            return ast.Await(value=self._compile_expr(node.value))
        # In sync mode, Await can't appear in a regular def.
        # Return a placeholder — the Template guard prevents this path.
        return ast.Constant(value="")

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
        # Warn when right side is a Filter — likely precedence mistake
        # e.g. {{ x ?? [] | length }} parses as {{ x ?? ([] | length) }}
        from kida.nodes.expressions import Filter

        if isinstance(node.right, Filter):
            self._emit_warning(
                ErrorCode.FILTER_PRECEDENCE,
                f"Filter '|' binds tighter than '??' — "
                f"'| {node.right.name}' applies to the fallback, not the full expression",
                lineno=node.lineno,
                suggestion=f"Use (... ?? {{}}) | {node.right.name} to apply "
                f"the filter to the result, or add parentheses to clarify intent.",
            )

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
            err = TemplateSyntaxError(msg, lineno=getattr(node, "lineno", None))
            err.code = ErrorCode.INVALID_FILTER
            raise err

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
                err = TemplateSyntaxError(msg, lineno=getattr(node, "lineno", None))
                err.code = ErrorCode.INVALID_FILTER
                raise err

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
                err = TemplateSyntaxError(msg, lineno=getattr(node, "lineno", None))
                err.code = ErrorCode.INVALID_FILTER
                raise err

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
