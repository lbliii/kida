"""Compile-time partial evaluation of template AST.

Transforms a Kida AST by evaluating expressions whose values can be
determined from a static context (values known at compile time, not
at render time).  This replaces dynamic lookups with constant data
nodes, enabling more aggressive f-string coalescing and producing
templates where static regions are literal strings in bytecode.

Example:
    Given static_context = {"site": Site(title="My Blog")}:

    Before:  Output(expr=Getattr(Name("site"), "title"))
    After:   Data(value="My Blog")

The evaluator is conservative: if any sub-expression cannot be
resolved, the entire expression is left untouched.  This guarantees
that partial evaluation never changes observable behavior.

Integration:
    Called by ``Environment._compile()`` between parsing and compilation.
    The partially-evaluated AST is then compiled normally by the Compiler,
    which sees more Data/Const nodes and produces better coalesced output.

"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, final

from kida.nodes import (
    BinOp,
    Block,
    BoolOp,
    CallBlock,
    Capture,
    Compare,
    Concat,
    CondExpr,
    Const,
    Data,
    Def,
    Dict,
    Export,
    Expr,
    Filter,
    For,
    FuncCall,
    Getattr,
    Getitem,
    If,
    Let,
    List,
    ListComp,
    MarkSafe,
    Match,
    Name,
    Node,
    NullCoalesce,
    OptionalFilter,
    Output,
    Pipeline,
    Range,
    SafePipeline,
    Set,
    Slot,
    SlotBlock,
    Template,
    Test,
    Tuple,
    UnaryOp,
    With,
)

# Sentinel for "evaluation failed" — distinct from None (which is a valid result)
_UNRESOLVED = object()

# Maximum number of iterations to unroll in a static for-loop
_MAX_UNROLL = 200


# Maximum allowed result size for safe builtins that produce sequences
_MAX_BUILTIN_RESULT = 10_000

# Safe builtins that can be evaluated at compile time.
# Each maps a function name to a callable. Only functions that:
# 1. Have no side effects
# 2. Are deterministic
# 3. Cannot execute arbitrary code
_SAFE_BUILTINS: dict[str, Callable[..., Any]] = {
    "range": range,
    "len": len,
    "sorted": sorted,
    "min": min,
    "max": max,
    "sum": sum,
    "abs": abs,
    "round": round,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "list": list,
    "tuple": tuple,
    "chr": chr,
    "ord": ord,
}

# Safe test predicates for compile-time evaluation.
# Maps test name to a callable(value, *args) -> bool.
# Only tests that are side-effect-free and deterministic.
_SAFE_TESTS: dict[str, Callable[..., bool]] = {
    "none": lambda v: v is None,
    "odd": lambda v: isinstance(v, int) and v % 2 == 1,
    "even": lambda v: isinstance(v, int) and v % 2 == 0,
    "true": lambda v: v is True,
    "false": lambda v: v is False,
    "number": lambda v: isinstance(v, (int, float)),
    "string": lambda v: isinstance(v, str),
    "mapping": lambda v: isinstance(v, dict),
    "sequence": lambda v: isinstance(v, (list, tuple, str)),
    "iterable": lambda v: hasattr(v, "__iter__"),
    "callable": lambda v: callable(v),
    "boolean": lambda v: isinstance(v, bool),
}


@dataclass(frozen=True, slots=True)
class _LoopProperties:
    """Compile-time stand-in for LoopContext properties.

    Provides the same attribute names as the runtime LoopContext so that
    expressions like ``{{ loop.index }}`` resolve during partial evaluation.
    """

    index0: int
    index: int
    first: bool
    last: bool
    length: int
    revindex: int
    revindex0: int


# Expected errors when constant folding fails — fall back to runtime evaluation.
# Narrowing avoids silently swallowing KeyboardInterrupt, SystemExit, etc.
_PARTIAL_EVAL_EXCEPTIONS: tuple[type[BaseException], ...] = (
    TypeError,
    KeyError,
    IndexError,
    AttributeError,
    ValueError,
    OverflowError,
    ZeroDivisionError,
)


# ---------------------------------------------------------------------------
# Dead code elimination (const-only, no static_context)
# ---------------------------------------------------------------------------


def _try_eval_const_only(expr: Expr) -> Any:
    """Evaluate expression using only literals and constant expressions.

    Resolves Const, BinOp, UnaryOp, Compare, BoolOp. No Name/Getattr/Getitem
    (those require static_context). Used for dead code elimination.
    """
    match expr:
        case Const():
            return expr.value

        case BinOp():
            left = _try_eval_const_only(expr.left)
            right = _try_eval_const_only(expr.right)
            if left is _UNRESOLVED or right is _UNRESOLVED:
                return _UNRESOLVED
            try:
                if expr.op == "+":
                    return left + right
                if expr.op == "-":
                    return left - right
                if expr.op == "*":
                    return left * right
                if expr.op == "/":
                    return left / right
                if expr.op == "//":
                    return left // right
                if expr.op == "%":
                    return left % right
                if expr.op == "**":
                    return left**right
                if expr.op == "~":
                    # Compile-time only: operands are constants, never Markup.
                    # Runtime ~ uses _markup_concat for Markup preservation.
                    return str(left) + str(right)
            except _PARTIAL_EVAL_EXCEPTIONS:
                return _UNRESOLVED
            return _UNRESOLVED

        case UnaryOp():
            operand = _try_eval_const_only(expr.operand)
            if operand is _UNRESOLVED:
                return _UNRESOLVED
            try:
                if expr.op == "-":
                    return -operand
                if expr.op == "+":
                    return +operand
                if expr.op == "not":
                    return not operand
            except _PARTIAL_EVAL_EXCEPTIONS:
                return _UNRESOLVED
            return _UNRESOLVED

        case Compare():
            left = _try_eval_const_only(expr.left)
            if left is _UNRESOLVED:
                return _UNRESOLVED
            for op, comp_node in zip(expr.ops, expr.comparators, strict=True):
                right = _try_eval_const_only(comp_node)
                if right is _UNRESOLVED:
                    return _UNRESOLVED
                try:
                    result = _compare_op(op, left, right)
                except _PARTIAL_EVAL_EXCEPTIONS:
                    return _UNRESOLVED
                if not result:
                    return False
                left = right
            return True

        case BoolOp():
            if expr.op == "and":
                for val_node in expr.values:
                    val = _try_eval_const_only(val_node)
                    if val is _UNRESOLVED:
                        return _UNRESOLVED
                    if not val:
                        return val
                return val
            for val_node in expr.values:
                val = _try_eval_const_only(val_node)
                if val is _UNRESOLVED:
                    return _UNRESOLVED
                if val:
                    return val
            return val

        case CondExpr():
            test = _try_eval_const_only(expr.test)
            if test is _UNRESOLVED:
                return _UNRESOLVED
            return _try_eval_const_only(expr.if_true if test else expr.if_false)

        case _:
            return _UNRESOLVED


def _body_has_scoping_nodes(nodes: Sequence[Node]) -> bool:
    """True if body contains Set, Let, Capture, or Export (block-scoped)."""
    for n in nodes:
        if isinstance(n, (Set, Let, Capture, Export)):
            return True
        if isinstance(n, Block) and _body_has_scoping_nodes(n.body):
            return True
    return False


def _dce_transform_if(node: If) -> Node | None:
    """Eliminate dead branches when test is const-only resolvable."""
    test_val = _try_eval_const_only(node.test)
    if test_val is _UNRESOLVED:
        return node

    if test_val:
        if _body_has_scoping_nodes(node.body):
            return node  # Preserve If structure for block scoping
        body = _dce_transform_body(node.body)
        if len(body) == 1:
            return body[0]
        return _InlinedBody(
            lineno=node.lineno,
            col_offset=node.col_offset,
            nodes=body,
        )

    for cond, branch_body in node.elif_:
        cond_val = _try_eval_const_only(cond)
        if cond_val is _UNRESOLVED:
            return node
        if cond_val:
            if _body_has_scoping_nodes(branch_body):
                return node
            body = _dce_transform_body(branch_body)
            if len(body) == 1:
                return body[0]
            return _InlinedBody(
                lineno=node.lineno,
                col_offset=node.col_offset,
                nodes=body,
            )

    if node.else_:
        if _body_has_scoping_nodes(node.else_):
            return node
        body = _dce_transform_body(node.else_)
        if len(body) == 1:
            return body[0]
        return _InlinedBody(
            lineno=node.lineno,
            col_offset=node.col_offset,
            nodes=body,
        )

    return None


def _dce_transform_match(node: Match) -> Node | None:
    """Eliminate dead match/case branches when subject is a const literal."""
    if node.subject is None:
        return node
    subject_val = _try_eval_const_only(node.subject)
    if subject_val is _UNRESOLVED:
        # Recurse into case bodies
        new_cases: list[tuple[Expr, Expr | None, Sequence[Node]]] = []
        changed = False
        for pattern, guard, case_body in node.cases:
            new_body = _dce_transform_body(case_body)
            if new_body is not case_body:
                changed = True
            new_cases.append((pattern, guard, new_body))
        if not changed:
            return node
        return Match(
            lineno=node.lineno,
            col_offset=node.col_offset,
            subject=node.subject,
            cases=tuple(new_cases),
        )

    # Subject is a constant — find the matching case
    for pattern, guard, case_body in node.cases:
        if isinstance(pattern, Name) and pattern.name == "_":
            if guard is not None:
                guard_val = _try_eval_const_only(guard)
                if guard_val is _UNRESOLVED:
                    return node  # Can't resolve guard
                if not guard_val:
                    continue
            if _body_has_scoping_nodes(case_body):
                return node
            body = _dce_transform_body(case_body)
            if len(body) == 1:
                return body[0]
            return _InlinedBody(lineno=node.lineno, col_offset=node.col_offset, nodes=body)

        if isinstance(pattern, Const):
            if subject_val == pattern.value:
                if guard is not None:
                    guard_val = _try_eval_const_only(guard)
                    if guard_val is _UNRESOLVED:
                        return node
                    if not guard_val:
                        continue
                if _body_has_scoping_nodes(case_body):
                    return node
                body = _dce_transform_body(case_body)
                if len(body) == 1:
                    return body[0]
                return _InlinedBody(lineno=node.lineno, col_offset=node.col_offset, nodes=body)
            continue

        # Complex pattern — bail
        return node

    # No match found — remove the node
    return None


def _dce_transform_body(body: Sequence[Node]) -> Sequence[Node]:
    """Transform body, eliminating dead If nodes and flattening _InlinedBody."""
    result: list[Node] = []
    changed = False

    for node in body:
        match node:
            case If():
                transformed = _dce_transform_if(node)
                if transformed is None:
                    changed = True
                    continue
                if isinstance(transformed, _InlinedBody):
                    changed = True
                    result.extend(transformed.nodes)
                else:
                    result.append(transformed)
            case Match():
                transformed = _dce_transform_match(node)
                if transformed is None:
                    changed = True
                    continue
                if isinstance(transformed, _InlinedBody):
                    changed = True
                    result.extend(transformed.nodes)
                else:
                    if transformed is not node:
                        changed = True
                    result.append(transformed)
            case Block():
                new_block_body = _dce_transform_body(node.body)
                if new_block_body is not node.body:
                    changed = True
                    result.append(
                        Block(
                            lineno=node.lineno,
                            col_offset=node.col_offset,
                            name=node.name,
                            body=new_block_body,
                            scoped=node.scoped,
                            required=node.required,
                        )
                    )
                else:
                    result.append(node)
            case Output():
                val = _try_eval_const_only(node.expr)
                if val is not _UNRESOLVED:
                    str_val = "" if val is None else str(val)
                    # Only fold safely: numerics never need escaping,
                    # strings only fold when escape is not required
                    if isinstance(val, (int, float, bool)) or not node.escape:
                        changed = True
                        if str_val:
                            result.append(
                                Data(
                                    lineno=node.lineno,
                                    col_offset=node.col_offset,
                                    value=str_val,
                                )
                            )
                    else:
                        result.append(node)
                else:
                    result.append(node)
            case _:
                result.append(node)

    if not changed:
        return body
    return tuple(result)


def eliminate_dead_code(template: Template) -> Template:
    """Remove branches whose conditions are provably constant.

    Runs without static_context. Eliminates e.g. {% if false %}...{% end %},
    {% if true %}x{% else %}y{% end %}, {% if 1+1==2 %}...{% end %}.
    """
    new_body = _dce_transform_body(template.body)
    if new_body is template.body:
        return template
    result = Template(
        lineno=template.lineno,
        col_offset=template.col_offset,
        body=new_body,
        extends=template.extends,
        context_type=template.context_type,
    )
    return _flatten_inlined(result)


class PartialEvaluator:
    """Evaluate static expressions in a Kida AST at compile time.

    Walks the template AST and replaces expressions that can be fully
    resolved from the static context with their computed values.

    Args:
        static_context: Values known at compile time (e.g., site config,
            navigation data).  Keys are top-level variable names.
        escape_func: HTML escape function for Output nodes.  When None,
            static Output nodes are replaced with unescaped string values.
        pure_filters: Filter names that are safe to evaluate at compile
            time (no side effects, deterministic).
        filter_callables: Map of filter name to callable for compile-time
            Filter/Pipeline evaluation. When provided, pure filters can
            be evaluated (e.g. {{ site.title | default("x") }}).

    """

    __slots__ = (
        "_ctx",
        "_defs",
        "_escape",
        "_filter_callables",
        "_inline_components",
        "_max_depth",
        "_pure_filters",
    )

    def __init__(
        self,
        static_context: dict[str, Any],
        *,
        escape_func: Any | None = None,
        pure_filters: frozenset[str] = frozenset(),
        filter_callables: dict[str, Callable[..., Any]] | None = None,
        max_eval_depth: int = 100,
        inline_components: bool = False,
    ) -> None:
        self._ctx = static_context
        self._escape = escape_func
        self._pure_filters = pure_filters
        self._filter_callables = filter_callables or {}
        self._max_depth = max_eval_depth
        self._inline_components = inline_components
        self._defs: dict[str, Def] = {}

    def evaluate(self, template: Template) -> Template:
        """Transform a template AST by evaluating static expressions.

        Returns a new Template node with static parts replaced by
        constants.  The original template is not modified.

        """
        new_body = self._transform_body(template.body)
        if new_body is template.body:
            return template
        return Template(
            lineno=template.lineno,
            col_offset=template.col_offset,
            body=new_body,
            extends=template.extends,
            context_type=template.context_type,
        )

    # ------------------------------------------------------------------
    # Expression evaluation (try to compute a value)
    # ------------------------------------------------------------------

    def _try_eval(self, expr: Expr, depth: int = 0) -> Any:
        """Try to evaluate an expression against the static context.

        Returns the computed value on success, or ``_UNRESOLVED`` if the
        expression depends on runtime values.

        Depth limit prevents stack overflow from deeply nested attribute chains
        (e.g. a.b.c.d.e... with 500+ levels).
        """
        if depth >= self._max_depth:
            return _UNRESOLVED

        if isinstance(expr, Const):
            return expr.value

        if isinstance(expr, Name):
            if expr.name in self._ctx:
                return self._ctx[expr.name]
            return _UNRESOLVED

        if isinstance(expr, Getattr):
            obj = self._try_eval(expr.obj, depth + 1)
            if obj is _UNRESOLVED:
                return _UNRESOLVED
            try:
                # Support both object attributes and dict-style access
                if isinstance(obj, Mapping):
                    return obj[expr.attr]
                return getattr(obj, expr.attr)
            except AttributeError, KeyError, TypeError:
                return _UNRESOLVED

        if isinstance(expr, Getitem):
            obj = self._try_eval(expr.obj, depth + 1)
            key = self._try_eval(expr.key, depth + 1)
            if obj is _UNRESOLVED or key is _UNRESOLVED:
                return _UNRESOLVED
            try:
                return obj[key]
            except KeyError, IndexError, TypeError:
                return _UNRESOLVED

        if isinstance(expr, BinOp):
            left = self._try_eval(expr.left, depth + 1)
            right = self._try_eval(expr.right, depth + 1)
            if left is _UNRESOLVED or right is _UNRESOLVED:
                return _UNRESOLVED
            return self._eval_binop(expr.op, left, right)

        if isinstance(expr, UnaryOp):
            operand = self._try_eval(expr.operand, depth + 1)
            if operand is _UNRESOLVED:
                return _UNRESOLVED
            return self._eval_unaryop(expr.op, operand)

        if isinstance(expr, Compare):
            return self._eval_compare(expr, depth)

        if isinstance(expr, BoolOp):
            return self._eval_boolop(expr, depth)

        if isinstance(expr, CondExpr):
            test = self._try_eval(expr.test, depth + 1)
            if test is _UNRESOLVED:
                return _UNRESOLVED
            return self._try_eval(expr.if_true if test else expr.if_false, depth + 1)

        if isinstance(expr, Concat):
            # Compile-time only: operands are constants, never Markup.
            # Runtime ~ uses _markup_concat for Markup preservation.
            parts = []
            for node in expr.nodes:
                val = self._try_eval(node, depth + 1)
                if val is _UNRESOLVED:
                    return _UNRESOLVED
                parts.append(str(val))
            return "".join(parts)

        if isinstance(expr, Filter):
            return self._try_eval_filter(expr, depth)

        if isinstance(expr, Pipeline):
            return self._try_eval_pipeline(expr, depth)

        if isinstance(expr, NullCoalesce):
            left = self._try_eval(expr.left, depth + 1)
            if left is _UNRESOLVED:
                return _UNRESOLVED
            if left is not None:
                return left
            return self._try_eval(expr.right, depth + 1)

        if isinstance(expr, MarkSafe):
            return self._try_eval(expr.value, depth + 1)

        if isinstance(expr, List):
            items = []
            for item in expr.items:
                val = self._try_eval(item, depth + 1)
                if val is _UNRESOLVED:
                    return _UNRESOLVED
                items.append(val)
            return items

        if isinstance(expr, Tuple):
            items = []
            for item in expr.items:
                val = self._try_eval(item, depth + 1)
                if val is _UNRESOLVED:
                    return _UNRESOLVED
                items.append(val)
            return tuple(items)

        if isinstance(expr, Dict):
            result: dict[Any, Any] = {}
            for k_expr, v_expr in zip(expr.keys, expr.values, strict=True):
                k = self._try_eval(k_expr, depth + 1)
                v = self._try_eval(v_expr, depth + 1)
                if k is _UNRESOLVED or v is _UNRESOLVED:
                    return _UNRESOLVED
                result[k] = v
            return result

        if isinstance(expr, ListComp):
            return self._try_eval_listcomp(expr, depth)

        if isinstance(expr, FuncCall):
            return self._try_eval_funccall(expr, depth)

        if isinstance(expr, Range):
            return self._try_eval_range(expr, depth)

        if isinstance(expr, Test):
            return self._try_eval_test(expr, depth)

        # Anything else — not resolved
        return _UNRESOLVED

    def _try_eval_filter(self, expr: Filter, depth: int = 0) -> Any:
        """Evaluate a Filter node when value and args are resolvable.

        OptionalFilter (``?|``) returns None when the input value is None.
        """
        if expr.name not in self._pure_filters:
            return _UNRESOLVED
        func = self._filter_callables.get(expr.name)
        if func is None:
            return _UNRESOLVED
        value = self._try_eval(expr.value, depth + 1)
        if value is _UNRESOLVED:
            return _UNRESOLVED
        if isinstance(expr, OptionalFilter) and value is None:
            return None
        args_resolved: list[Any] = []
        for arg in expr.args:
            a = self._try_eval(arg, depth + 1)
            if a is _UNRESOLVED:
                return _UNRESOLVED
            args_resolved.append(a)
        kwargs_resolved: dict[str, Any] = {}
        for k, v in expr.kwargs.items():
            kv = self._try_eval(v, depth + 1)
            if kv is _UNRESOLVED:
                return _UNRESOLVED
            kwargs_resolved[k] = kv
        try:
            return func(value, *args_resolved, **kwargs_resolved)
        except _PARTIAL_EVAL_EXCEPTIONS:
            return _UNRESOLVED

    def _try_eval_pipeline(self, expr: Pipeline, depth: int = 0) -> Any:
        """Evaluate a Pipeline node when value and all steps are resolvable.

        SafePipeline (``?|>``) propagates None through the chain.
        """
        is_safe = isinstance(expr, SafePipeline)
        value = self._try_eval(expr.value, depth + 1)
        if value is _UNRESOLVED:
            return _UNRESOLVED
        for name, args, kwargs in expr.steps:
            if is_safe and value is None:
                return None
            if name not in self._pure_filters:
                return _UNRESOLVED
            func = self._filter_callables.get(name)
            if func is None:
                return _UNRESOLVED
            args_resolved: list[Any] = []
            for arg in args:
                a = self._try_eval(arg, depth + 1)
                if a is _UNRESOLVED:
                    return _UNRESOLVED
                args_resolved.append(a)
            kwargs_resolved: dict[str, Any] = {}
            for k, v in kwargs.items():
                kv = self._try_eval(v, depth + 1)
                if kv is _UNRESOLVED:
                    return _UNRESOLVED
                kwargs_resolved[k] = kv
            try:
                value = func(value, *args_resolved, **kwargs_resolved)
            except _PARTIAL_EVAL_EXCEPTIONS:
                return _UNRESOLVED
        return value

    def _try_eval_listcomp(self, expr: ListComp, depth: int = 0) -> Any:
        """Evaluate a list comprehension when iterable and all parts resolve."""
        iter_val = self._try_eval(expr.iter, depth + 1)
        if iter_val is _UNRESOLVED:
            return _UNRESOLVED
        try:
            items = list(iter_val)
        except _PARTIAL_EVAL_EXCEPTIONS:
            return _UNRESOLVED
        if len(items) > _MAX_UNROLL:
            return _UNRESOLVED

        target = expr.target
        if isinstance(target, Name):
            target_names: tuple[str, ...] = (target.name,)
            unpack = False
        elif isinstance(target, Tuple) and all(isinstance(e, Name) for e in target.items):
            target_names = tuple(e.name for e in target.items)  # type: ignore[union-attr]
            unpack = True
        else:
            return _UNRESOLVED

        result = []
        for item in items:
            if unpack:
                try:
                    unpacked = tuple(item)
                except _PARTIAL_EVAL_EXCEPTIONS:
                    return _UNRESOLVED
                if len(unpacked) != len(target_names):
                    return _UNRESOLVED
                sub_ctx = {**self._ctx, **dict(zip(target_names, unpacked, strict=True))}
            else:
                sub_ctx = {**self._ctx, target_names[0]: item}
            sub_eval = PartialEvaluator(
                sub_ctx,
                escape_func=self._escape,
                pure_filters=self._pure_filters,
                filter_callables=self._filter_callables,
                max_eval_depth=self._max_depth,
            )
            # Check filter conditions
            skip = False
            for cond in expr.ifs:
                cond_val = sub_eval._try_eval(cond, depth + 1)
                if cond_val is _UNRESOLVED:
                    return _UNRESOLVED
                if not cond_val:
                    skip = True
                    break
            if skip:
                continue
            elt_val = sub_eval._try_eval(expr.elt, depth + 1)
            if elt_val is _UNRESOLVED:
                return _UNRESOLVED
            result.append(elt_val)
        return result

    def _try_eval_funccall(self, expr: FuncCall, depth: int = 0) -> Any:
        """Evaluate a FuncCall when it targets a safe builtin and all args resolve."""
        # Only handle simple Name calls (not method calls or complex expressions)
        if not isinstance(expr.func, Name):
            return _UNRESOLVED
        # No dynamic args/kwargs
        if expr.dyn_args is not None or expr.dyn_kwargs is not None:
            return _UNRESOLVED

        func_name = expr.func.name
        func = _SAFE_BUILTINS.get(func_name)
        if func is None:
            return _UNRESOLVED

        # Resolve positional args
        args_resolved: list[Any] = []
        for arg in expr.args:
            val = self._try_eval(arg, depth + 1)
            if val is _UNRESOLVED:
                return _UNRESOLVED
            args_resolved.append(val)

        # Resolve keyword args
        kwargs_resolved: dict[str, Any] = {}
        for k, v_expr in expr.kwargs.items():
            val = self._try_eval(v_expr, depth + 1)
            if val is _UNRESOLVED:
                return _UNRESOLVED
            kwargs_resolved[k] = val

        # Guard against DoS: range() with large values
        if func_name == "range":
            try:
                r = range(*args_resolved, **kwargs_resolved)
            except _PARTIAL_EVAL_EXCEPTIONS:
                return _UNRESOLVED
            if len(r) > _MAX_BUILTIN_RESULT:
                return _UNRESOLVED
            return r

        try:
            result = func(*args_resolved, **kwargs_resolved)
        except _PARTIAL_EVAL_EXCEPTIONS:
            return _UNRESOLVED

        # Guard against large sequence results
        if isinstance(result, (list, tuple, set, frozenset)) and len(result) > _MAX_BUILTIN_RESULT:
            return _UNRESOLVED

        return result

    def _try_eval_range(self, expr: Range, depth: int = 0) -> Any:
        """Evaluate a Range literal (start..end or start...end)."""
        start = self._try_eval(expr.start, depth + 1)
        end = self._try_eval(expr.end, depth + 1)
        if start is _UNRESOLVED or end is _UNRESOLVED:
            return _UNRESOLVED

        step_val = 1
        if expr.step is not None:
            step_val = self._try_eval(expr.step, depth + 1)
            if step_val is _UNRESOLVED:
                return _UNRESOLVED

        try:
            r = range(start, end + 1, step_val) if expr.inclusive else range(start, end, step_val)
        except _PARTIAL_EVAL_EXCEPTIONS:
            return _UNRESOLVED

        if len(r) > _MAX_BUILTIN_RESULT:
            return _UNRESOLVED
        return list(r)

    def _try_eval_test(self, expr: Test, depth: int = 0) -> Any:
        """Evaluate a Test node when the value can be resolved.

        Handles ``is defined`` / ``is undefined`` specially (they check
        context membership, not the value itself). All other tests require
        a resolved value.
        """
        # "defined" / "undefined" check context membership, not value
        if expr.name == "defined":
            if isinstance(expr.value, Name):
                result = expr.value.name in self._ctx
                return (not result) if expr.negated else result
            # For non-Name expressions, try to resolve and check for _UNRESOLVED
            val = self._try_eval(expr.value, depth + 1)
            if val is _UNRESOLVED:
                return _UNRESOLVED
            result = True  # If it resolved, it's "defined"
            return (not result) if expr.negated else result

        if expr.name == "undefined":
            if isinstance(expr.value, Name):
                result = expr.value.name not in self._ctx
                return (not result) if expr.negated else result
            val = self._try_eval(expr.value, depth + 1)
            if val is _UNRESOLVED:
                return _UNRESOLVED
            result = False  # If it resolved, it's not "undefined"
            return (not result) if expr.negated else result

        # All other tests require a resolved value
        value = self._try_eval(expr.value, depth + 1)
        if value is _UNRESOLVED:
            return _UNRESOLVED

        test_func = _SAFE_TESTS.get(expr.name)
        if test_func is None:
            return _UNRESOLVED

        # Resolve test arguments
        args_resolved: list[Any] = []
        for arg in expr.args:
            a = self._try_eval(arg, depth + 1)
            if a is _UNRESOLVED:
                return _UNRESOLVED
            args_resolved.append(a)

        try:
            result = test_func(value, *args_resolved)
        except _PARTIAL_EVAL_EXCEPTIONS:
            return _UNRESOLVED

        return (not result) if expr.negated else result

    @staticmethod
    def _eval_binop(op: str, left: Any, right: Any) -> Any:
        """Evaluate a binary operation with known operands."""
        try:
            if op == "+":
                return left + right
            if op == "-":
                return left - right
            if op == "*":
                return left * right
            if op == "/":
                return left / right
            if op == "//":
                return left // right
            if op == "%":
                return left % right
            if op == "**":
                return left**right
            if op == "~":
                # Compile-time only: operands are constants, never Markup.
                # Runtime ~ uses _markup_concat for Markup preservation.
                return str(left) + str(right)
        except _PARTIAL_EVAL_EXCEPTIONS:
            return _UNRESOLVED
        return _UNRESOLVED

    @staticmethod
    def _eval_unaryop(op: str, operand: Any) -> Any:
        """Evaluate a unary operation with a known operand."""
        try:
            if op == "-":
                return -operand
            if op == "+":
                return +operand
            if op == "not":
                return not operand
        except _PARTIAL_EVAL_EXCEPTIONS:
            return _UNRESOLVED
        return _UNRESOLVED

    def _eval_compare(self, expr: Compare, depth: int = 0) -> Any:
        """Evaluate a comparison chain with known operands."""
        left = self._try_eval(expr.left, depth + 1)
        if left is _UNRESOLVED:
            return _UNRESOLVED

        for op, comp_node in zip(expr.ops, expr.comparators, strict=True):
            right = self._try_eval(comp_node, depth + 1)
            if right is _UNRESOLVED:
                return _UNRESOLVED
            try:
                result = _compare_op(op, left, right)
            except _PARTIAL_EVAL_EXCEPTIONS:
                return _UNRESOLVED
            if not result:
                return False
            left = right
        return True

    def _eval_boolop(self, expr: BoolOp, depth: int = 0) -> Any:
        """Evaluate a boolean operation with short-circuit semantics."""
        if expr.op == "and":
            for val_node in expr.values:
                val = self._try_eval(val_node, depth + 1)
                if val is _UNRESOLVED:
                    return _UNRESOLVED
                if not val:
                    return val
            return val
        # "or"
        for val_node in expr.values:
            val = self._try_eval(val_node, depth + 1)
            if val is _UNRESOLVED:
                return _UNRESOLVED
            if val:
                return val
        return val

    # ------------------------------------------------------------------
    # AST transformation (structural rewriting)
    # ------------------------------------------------------------------

    def _transform_body(self, body: Sequence[Node]) -> Sequence[Node]:
        """Transform a sequence of nodes, merging adjacent Data nodes."""
        new_nodes: list[Node] = []
        changed = False

        for node in body:
            transformed = self._transform_node(node)
            if transformed is not node:
                changed = True
            if transformed is None:
                changed = True
                continue
            # Flatten _InlinedBody (from branch elimination / loop unrolling)
            if isinstance(transformed, _InlinedBody):
                changed = True
                for inner in transformed.nodes:
                    self._append_and_merge(new_nodes, inner)
                continue
            self._append_and_merge(new_nodes, transformed)
            if transformed is not node:
                changed = True

        if not changed:
            return body
        return tuple(new_nodes)

    @staticmethod
    def _append_and_merge(nodes: list[Node], new_node: Node) -> None:
        """Append a node, merging adjacent Data nodes."""
        if isinstance(new_node, Data) and nodes and isinstance(nodes[-1], Data):
            prev = nodes[-1]
            nodes[-1] = Data(
                lineno=prev.lineno,
                col_offset=prev.col_offset,
                value=prev.value + new_node.value,
            )
        else:
            nodes.append(new_node)

    def _transform_node(self, node: Node) -> Node | None:
        """Transform a single AST node.

        Returns the transformed node, or None to remove it.

        """
        if isinstance(node, Output):
            return self._transform_output(node)

        if isinstance(node, If):
            return self._transform_if(node)

        if isinstance(node, For):
            return self._transform_for(node)

        if isinstance(node, Block):
            new_body = self._transform_body(node.body)
            if new_body is node.body:
                return node
            return Block(
                lineno=node.lineno,
                col_offset=node.col_offset,
                name=node.name,
                body=new_body,
                scoped=node.scoped,
                required=node.required,
            )

        if isinstance(node, Def):
            # Register def for potential inlining, then recurse into body
            self._defs[node.name] = node
            new_body = self._transform_body(node.body)
            if new_body is node.body:
                return node
            return Def(
                lineno=node.lineno,
                col_offset=node.col_offset,
                name=node.name,
                params=node.params,
                body=new_body,
                defaults=node.defaults,
                vararg=node.vararg,
                kwarg=node.kwarg,
            )

        if isinstance(node, CallBlock):
            inlined = self._try_inline_call(node) if self._inline_components else None
            if inlined is not None:
                return inlined
            new_slots = {k: self._transform_body(v) for k, v in node.slots.items()}
            if all(new_slots[k] is node.slots[k] for k in node.slots):
                return node
            return CallBlock(
                lineno=node.lineno,
                col_offset=node.col_offset,
                call=node.call,
                slots=new_slots,
                args=node.args,
            )

        if isinstance(node, SlotBlock):
            new_body = self._transform_body(node.body)
            if new_body is node.body:
                return node
            return SlotBlock(
                lineno=node.lineno,
                col_offset=node.col_offset,
                name=node.name,
                body=new_body,
            )

        if isinstance(node, With):
            return self._transform_with(node)

        if isinstance(node, Match):
            return self._transform_match(node)

        if isinstance(node, (Set, Let)):
            return self._transform_assignment(node)

        # Data, Raw, and other nodes pass through unchanged
        return node

    def _transform_output(self, node: Output) -> Node:
        """Try to evaluate an Output node to a Data node."""
        value = self._try_eval(node.expr)
        if value is _UNRESOLVED:
            # Can't resolve — try to partially evaluate the expression
            new_expr = self._transform_expr(node.expr)
            if new_expr is node.expr:
                return node
            return Output(
                lineno=node.lineno,
                col_offset=node.col_offset,
                expr=new_expr,
                escape=node.escape,
            )

        # Fully resolved — replace with Data
        str_value = str(value) if value is not None else ""
        if node.escape:
            if hasattr(value, "__html__"):
                # Value is already marked safe (e.g. Markup from | safe filter)
                # — don't escape again.
                str_value = str(value)
            elif isinstance(value, (int, float, bool)):
                # Numeric/bool types never need escaping.
                pass
            elif self._escape is not None:
                str_value = str(self._escape(str_value))
            else:
                # No escape function available and value is a string —
                # leave as Output so the runtime escape path handles it.
                return node
        return Data(
            lineno=node.lineno,
            col_offset=node.col_offset,
            value=str_value,
        )

    def _transform_if(self, node: If) -> Node | None:
        """Try to evaluate an If node's test at compile time."""
        test_val = self._try_eval(node.test)
        if test_val is _UNRESOLVED:
            # Can't fully resolve test — try partial simplification
            new_test = self._transform_expr(node.test)

            # If partial simplification yielded a Const, we can eliminate branches
            if isinstance(new_test, Const):
                test_val = new_test.value
                # Fall through to branch elimination below
            else:
                # Still unresolved — recurse into branches with simplified test
                new_body = self._transform_body(node.body)
                new_elif = tuple((cond, self._transform_body(body)) for cond, body in node.elif_)
                new_else = self._transform_body(node.else_) if node.else_ else node.else_
                if (
                    new_test is node.test
                    and new_body is node.body
                    and new_elif == node.elif_
                    and new_else is node.else_
                ):
                    return node
                return If(
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                    test=new_test,
                    body=new_body,
                    elif_=new_elif,
                    else_=new_else,
                )

        # Test resolved — eliminate dead branches
        if test_val:
            # True branch wins — inline its body
            body = self._transform_body(node.body)
            if len(body) == 1:
                return body[0]
            # Wrap multiple nodes in a sentinel (return first for simplicity)
            # Actually, _transform_body returns them, and the parent will
            # handle the sequence.  Return a special marker.
            return _InlinedBody(
                lineno=node.lineno,
                col_offset=node.col_offset,
                nodes=body,
            )

        # False — check elif branches
        for cond, branch_body in node.elif_:
            cond_val = self._try_eval(cond)
            if cond_val is _UNRESOLVED:
                # Can't resolve this elif — give up on elimination
                return node
            if cond_val:
                body = self._transform_body(branch_body)
                if len(body) == 1:
                    return body[0]
                return _InlinedBody(
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                    nodes=body,
                )

        # All branches false — use else or remove
        if node.else_:
            body = self._transform_body(node.else_)
            if len(body) == 1:
                return body[0]
            return _InlinedBody(
                lineno=node.lineno,
                col_offset=node.col_offset,
                nodes=body,
            )

        # No else — remove the node entirely
        return None

    def _transform_for(self, node: For) -> Node | None:
        """Unroll for-loop when iterable is statically known, else recurse."""
        iter_val = self._try_eval(node.iter)

        if iter_val is not _UNRESOLVED and not node.recursive:
            # Try to unroll the loop
            unrolled = self._try_unroll_for(node, iter_val)
            if unrolled is not None:
                return unrolled

        # Can't unroll — recurse into body as before
        new_body = self._transform_body(node.body)
        new_empty = self._transform_body(node.empty) if node.empty else node.empty
        if new_body is node.body and new_empty is node.empty:
            return node
        return For(
            lineno=node.lineno,
            col_offset=node.col_offset,
            target=node.target,
            iter=node.iter,
            body=new_body,
            empty=new_empty,
            recursive=node.recursive,
            test=node.test,
        )

    def _transform_with(self, node: With) -> Node:
        """Propagate static values through {% with %} block bindings.

        Evaluates each binding expression against the static context.
        Resolved bindings are added to a sub-evaluator's context so
        that the body can fold expressions referencing them.
        """
        # Evaluate bindings and build augmented context
        aug_ctx = dict(self._ctx)
        new_targets: list[tuple[str, Expr]] = []
        changed = False

        for name, value_expr in node.targets:
            val = self._try_eval(value_expr)
            if val is not _UNRESOLVED:
                # Binding resolved — add to context, replace expr with Const
                aug_ctx[name] = val
                const_expr = Const(
                    lineno=value_expr.lineno,
                    col_offset=value_expr.col_offset,
                    value=val,
                )
                new_targets.append((name, const_expr))
                changed = True
            else:
                # Try partial simplification of the value expression
                new_expr = self._transform_expr(value_expr)
                new_targets.append((name, new_expr))
                if new_expr is not value_expr:
                    changed = True

        # Transform body with augmented context
        sub_eval = self._make_sub_evaluator(aug_ctx)
        sub_eval._defs = dict(self._defs)
        new_body = sub_eval._transform_body(node.body)

        if not changed and new_body is node.body:
            return node

        return With(
            lineno=node.lineno,
            col_offset=node.col_offset,
            targets=tuple(new_targets),
            body=new_body,
        )

    def _transform_match(self, node: Match) -> Node | None:
        """Eliminate dead match/case branches when subject is compile-time-known.

        When the subject resolves, iterate cases and match:
        - Const patterns: exact equality check
        - Name("_") wildcard: always matches
        - Other patterns: bail (leave Match intact)

        If subject is unresolved, recurse into each case body.
        """
        if node.subject is None:
            return node

        subject_val = self._try_eval(node.subject)

        if subject_val is not _UNRESOLVED:
            # Subject resolved — find the matching case
            for pattern, guard, case_body in node.cases:
                # Wildcard: Name("_") always matches
                if isinstance(pattern, Name) and pattern.name == "_":
                    if guard is not None:
                        guard_val = self._try_eval(guard)
                        if guard_val is _UNRESOLVED:
                            break  # Can't resolve guard — bail
                        if not guard_val:
                            continue  # Guard failed, try next case
                    body = self._transform_body(case_body)
                    if len(body) == 1:
                        return body[0]
                    return _InlinedBody(
                        lineno=node.lineno,
                        col_offset=node.col_offset,
                        nodes=body,
                    )

                # Const pattern: exact equality check
                if isinstance(pattern, Const):
                    if subject_val == pattern.value:
                        if guard is not None:
                            guard_val = self._try_eval(guard)
                            if guard_val is _UNRESOLVED:
                                break  # Can't resolve guard — bail
                            if not guard_val:
                                continue
                        body = self._transform_body(case_body)
                        if len(body) == 1:
                            return body[0]
                        return _InlinedBody(
                            lineno=node.lineno,
                            col_offset=node.col_offset,
                            nodes=body,
                        )
                    continue  # Pattern didn't match, try next case

                # Complex pattern — bail out, preserve entire Match
                break

            # Fall through: no match found or bailed — preserve with recursion

        # Subject unresolved or no match — recurse into case bodies
        new_subject = self._transform_expr(node.subject)
        new_cases: list[tuple[Expr, Expr | None, Sequence[Node]]] = []
        changed = new_subject is not node.subject

        for pattern, guard, case_body in node.cases:
            new_body = self._transform_body(case_body)
            new_guard = self._transform_expr(guard) if guard is not None else guard
            if new_body is not case_body or new_guard is not guard:
                changed = True
            new_cases.append((pattern, new_guard, new_body))

        if not changed:
            return node

        return Match(
            lineno=node.lineno,
            col_offset=node.col_offset,
            subject=new_subject,
            cases=tuple(new_cases),
        )

    def _try_unroll_for(self, node: For, iter_val: Any) -> Node | None:
        """Attempt to unroll a for-loop with a known iterable.

        Returns an _InlinedBody of unrolled iterations, or None if
        unrolling is not possible (too many items, complex target, etc.).
        """
        try:
            items = list(iter_val)
        except _PARTIAL_EVAL_EXCEPTIONS:
            return None

        if len(items) > _MAX_UNROLL:
            return None

        # Handle empty iterable
        if not items:
            if node.empty:
                body = self._transform_body(node.empty)
                if len(body) == 1:
                    return body[0]
                return _InlinedBody(lineno=node.lineno, col_offset=node.col_offset, nodes=body)
            return _InlinedBody(lineno=node.lineno, col_offset=node.col_offset, nodes=())

        # Determine target variable name(s)
        target = node.target
        if isinstance(target, Name):
            target_names: tuple[str, ...] = (target.name,)
        elif isinstance(target, Tuple):
            names = []
            for item in target.items:
                if not isinstance(item, Name):
                    return None  # Complex target — bail
                names.append(item.name)
            target_names = tuple(names)
        else:
            return None

        # Unroll each iteration
        total_items = len(items)
        all_nodes: list[Node] = []

        for idx, item in enumerate(items):
            # Apply loop test filter if present
            if node.test is not None:
                sub_ctx = self._build_iter_context(target_names, item)
                sub_eval = self._make_sub_evaluator(sub_ctx)
                test_val = sub_eval._try_eval(node.test)
                if test_val is _UNRESOLVED:
                    return None  # Can't determine filter — bail
                if not test_val:
                    continue

            # Build context with loop variable(s) + loop.* properties
            iter_ctx = self._build_iter_context(target_names, item)
            iter_ctx["loop"] = _LoopProperties(
                index0=idx,
                index=idx + 1,
                first=idx == 0,
                last=idx == total_items - 1,
                length=total_items,
                revindex=total_items - idx,
                revindex0=total_items - idx - 1,
            )

            sub_eval = self._make_sub_evaluator(iter_ctx)
            sub_eval._defs = dict(self._defs)
            transformed = sub_eval._transform_body(node.body)
            all_nodes.extend(transformed)

        if len(all_nodes) == 1:
            return all_nodes[0]
        return _InlinedBody(lineno=node.lineno, col_offset=node.col_offset, nodes=tuple(all_nodes))

    def _build_iter_context(self, target_names: tuple[str, ...], item: Any) -> dict[str, Any]:
        """Build a sub-context mapping target variable(s) to the current item."""
        ctx = dict(self._ctx)
        if len(target_names) == 1:
            ctx[target_names[0]] = item
        else:
            try:
                values = list(item)
            except _PARTIAL_EVAL_EXCEPTIONS:
                return ctx
            ctx.update(dict(zip(target_names, values, strict=False)))
        return ctx

    def _make_sub_evaluator(self, ctx: dict[str, Any]) -> PartialEvaluator:
        """Create a sub-evaluator with a merged context."""
        return PartialEvaluator(
            ctx,
            escape_func=self._escape,
            pure_filters=self._pure_filters,
            filter_callables=self._filter_callables,
            max_eval_depth=self._max_depth,
            inline_components=self._inline_components,
        )

    # ------------------------------------------------------------------
    # Assignment propagation (Set/Let)
    # ------------------------------------------------------------------

    def _transform_assignment(self, node: Set | Let) -> Node:
        """Track Set/Let bindings so downstream expressions resolve.

        When the assigned value can be fully evaluated from the static context,
        add it to self._ctx so subsequent expressions referencing this variable
        are also foldable. The value expression is also replaced with a Const
        so the runtime assignment doesn't fail looking up now-unnecessary vars.
        """
        # Get the variable name from the target expression
        target = node.target if isinstance(node, Set) else node.name
        if not isinstance(target, Name):
            return node  # Complex targets (tuple unpacking) — skip

        val = self._try_eval(node.value)
        if val is not _UNRESOLVED:
            # For coalesce assignments (??=), only propagate if the
            # variable is not already in context or is None
            if node.coalesce:
                existing = self._ctx.get(target.name, _UNRESOLVED)
                if existing is not _UNRESOLVED and existing is not None:
                    return node
            self._ctx[target.name] = val

            # Replace the value expression with a Const so the runtime
            # assignment doesn't reference vars only in static_context
            const_value = Const(
                lineno=node.value.lineno,
                col_offset=node.value.col_offset,
                value=val,
            )
            if isinstance(node, Set):
                return Set(
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                    target=node.target,
                    value=const_value,
                    coalesce=node.coalesce,
                )
            return Let(
                lineno=node.lineno,
                col_offset=node.col_offset,
                name=node.name,
                value=const_value,
                coalesce=node.coalesce,
            )
        return node

    # ------------------------------------------------------------------
    # Component inlining
    # ------------------------------------------------------------------

    _MAX_INLINE_NODES = 20

    def _try_inline_call(self, node: CallBlock) -> Node | None:
        """Try to inline a CallBlock by expanding its Def body.

        Returns an _InlinedBody (or single node) on success, None if
        inlining is not possible.

        Requirements for inlining:
        - The call target is a simple FuncCall(Name(def_name))
        - The referenced Def has been seen in this template
        - The Def body is small (< _MAX_INLINE_NODES)
        - The Def has no Slot nodes (no caller injection)
        - No slot content in the CallBlock
        - All arguments resolve to constants
        """
        # Must be a simple call: {{ name(args) }}
        call = node.call
        if not isinstance(call, FuncCall):
            return None
        if not isinstance(call.func, Name):
            return None

        def_name = call.func.name
        defn = self._defs.get(def_name)
        if defn is None:
            return None

        # Size guard
        if self._count_nodes(defn.body) > self._MAX_INLINE_NODES:
            return None

        # No slots in def body
        if self._has_slot(defn.body):
            return None

        # Defs execute with their own local context; inlining bodies that
        # contain scoping/assignment nodes would leak mutations into the
        # caller scope and change semantics.
        if _body_has_scoping_nodes(defn.body):
            return None

        # No meaningful slot content in the call — whitespace-only is OK
        def _slot_body_is_empty(body: Sequence[Node]) -> bool:
            return all(isinstance(child, Data) and not child.value.strip() for child in body)

        if any(not _slot_body_is_empty(body) for body in node.slots.values()):
            return None

        # No vararg/kwarg
        if defn.vararg or defn.kwarg:
            return None

        # Resolve all positional and keyword arguments
        param_names = [p.name for p in defn.params]
        arg_values: dict[str, Any] = {}

        # Positional args from call
        all_args = list(call.args) + list(node.args)
        for i, arg_expr in enumerate(all_args):
            if i >= len(param_names):
                return None  # Too many args
            val = self._try_eval(arg_expr)
            if val is _UNRESOLVED:
                return None
            arg_values[param_names[i]] = val

        # Keyword args from call
        for k, v_expr in call.kwargs.items():
            if k in arg_values:
                return None  # Duplicate
            val = self._try_eval(v_expr)
            if val is _UNRESOLVED:
                return None
            arg_values[k] = val

        # Fill defaults for missing params
        n_required = len(param_names) - len(defn.defaults)
        for i, param_name in enumerate(param_names):
            if param_name in arg_values:
                continue
            default_idx = i - n_required
            if default_idx < 0:
                return None  # Missing required arg
            val = self._try_eval(defn.defaults[default_idx])
            if val is _UNRESOLVED:
                return None
            arg_values[param_name] = val

        # Inline: create a sub-evaluator with merged context
        merged_ctx = {**self._ctx, **arg_values}
        sub_eval = PartialEvaluator(
            merged_ctx,
            escape_func=self._escape,
            pure_filters=self._pure_filters,
            filter_callables=self._filter_callables,
            max_eval_depth=self._max_depth,
            inline_components=self._inline_components,
        )
        sub_eval._defs = dict(self._defs)

        inlined_body = sub_eval._transform_body(defn.body)
        if len(inlined_body) == 1:
            return inlined_body[0]
        return _InlinedBody(
            lineno=node.lineno,
            col_offset=node.col_offset,
            nodes=inlined_body,
        )

    @staticmethod
    def _count_nodes(body: Sequence[Node]) -> int:
        """Count total nodes in a body (shallow — does not recurse into children)."""
        return len(body)

    @staticmethod
    def _has_slot(body: Sequence[Node]) -> bool:
        """Check if body contains any Slot nodes (recursively)."""
        for node in body:
            if isinstance(node, Slot):
                return True
            # Check all child bodies for container nodes
            if isinstance(node, (Block, If, For)):
                child_body = getattr(node, "body", ())
                if PartialEvaluator._has_slot(child_body):
                    return True
                # If: check elif branches and else
                if isinstance(node, If):
                    for _, branch_body in node.elif_:
                        if PartialEvaluator._has_slot(branch_body):
                            return True
                    if node.else_ and PartialEvaluator._has_slot(node.else_):
                        return True
                # For: check empty branch
                if isinstance(node, For) and node.empty and PartialEvaluator._has_slot(node.empty):
                    return True
            # SlotBlock contains a body too
            if isinstance(node, SlotBlock) and PartialEvaluator._has_slot(node.body):
                return True
        return False

    def _transform_expr(self, expr: Expr) -> Expr:
        """Try to partially evaluate an expression.

        If sub-expressions can be resolved, replace them with Const nodes.

        """
        if isinstance(expr, (Const, Name)):
            val = self._try_eval(expr)
            if val is not _UNRESOLVED:
                return Const(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    value=val,
                )
            return expr

        if isinstance(expr, Getattr):
            val = self._try_eval(expr)
            if val is not _UNRESOLVED:
                return Const(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    value=val,
                )
            new_obj = self._transform_expr(expr.obj)
            if new_obj is expr.obj:
                return expr
            return Getattr(
                lineno=expr.lineno,
                col_offset=expr.col_offset,
                obj=new_obj,
                attr=expr.attr,
            )

        if isinstance(expr, Getitem):
            val = self._try_eval(expr)
            if val is not _UNRESOLVED:
                return Const(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    value=val,
                )
            new_obj = self._transform_expr(expr.obj)
            new_key = self._transform_expr(expr.key)
            if new_obj is expr.obj and new_key is expr.key:
                return expr
            return Getitem(
                lineno=expr.lineno,
                col_offset=expr.col_offset,
                obj=new_obj,
                key=new_key,
            )

        if isinstance(expr, BinOp):
            val = self._try_eval(expr)
            if val is not _UNRESOLVED:
                return Const(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    value=val,
                )
            new_left = self._transform_expr(expr.left)
            new_right = self._transform_expr(expr.right)
            if new_left is expr.left and new_right is expr.right:
                return expr
            return BinOp(
                lineno=expr.lineno,
                col_offset=expr.col_offset,
                left=new_left,
                op=expr.op,
                right=new_right,
            )

        if isinstance(expr, NullCoalesce):
            val = self._try_eval(expr)
            if val is not _UNRESOLVED:
                return Const(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    value=val,
                )
            # Try to partially resolve the left side
            new_left = self._transform_expr(expr.left)
            new_right = self._transform_expr(expr.right)
            if new_left is expr.left and new_right is expr.right:
                return expr
            return NullCoalesce(
                lineno=expr.lineno,
                col_offset=expr.col_offset,
                left=new_left,
                right=new_right,
            )

        if isinstance(expr, MarkSafe):
            val = self._try_eval(expr)
            if val is not _UNRESOLVED:
                return Const(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    value=val,
                )
            new_inner = self._transform_expr(expr.value)
            if new_inner is expr.value:
                return expr
            return MarkSafe(
                lineno=expr.lineno,
                col_offset=expr.col_offset,
                value=new_inner,
            )

        if isinstance(expr, Filter):
            val = self._try_eval(expr)
            if val is not _UNRESOLVED:
                return Const(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    value=val,
                )
            new_value = self._transform_expr(expr.value)
            if new_value is expr.value:
                return expr
            return Filter(
                lineno=expr.lineno,
                col_offset=expr.col_offset,
                name=expr.name,
                value=new_value,
                args=expr.args,
                kwargs=expr.kwargs,
            )

        if isinstance(expr, Pipeline):
            val = self._try_eval(expr)
            if val is not _UNRESOLVED:
                return Const(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    value=val,
                )
            new_value = self._transform_expr(expr.value)
            if new_value is expr.value:
                return expr
            return type(expr)(
                lineno=expr.lineno,
                col_offset=expr.col_offset,
                value=new_value,
                steps=expr.steps,
            )

        if isinstance(expr, BoolOp):
            return self._transform_boolop(expr)

        if isinstance(expr, CondExpr):
            return self._transform_condexpr(expr)

        if isinstance(expr, UnaryOp):
            val = self._try_eval(expr)
            if val is not _UNRESOLVED:
                return Const(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    value=val,
                )
            new_operand = self._transform_expr(expr.operand)
            if new_operand is expr.operand:
                return expr
            return UnaryOp(
                lineno=expr.lineno,
                col_offset=expr.col_offset,
                op=expr.op,
                operand=new_operand,
            )

        if isinstance(expr, Compare):
            val = self._try_eval(expr)
            if val is not _UNRESOLVED:
                return Const(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    value=val,
                )
            new_left = self._transform_expr(expr.left)
            new_comps = tuple(self._transform_expr(c) for c in expr.comparators)
            if new_left is expr.left and all(
                n is o for n, o in zip(new_comps, expr.comparators, strict=True)
            ):
                return expr
            return Compare(
                lineno=expr.lineno,
                col_offset=expr.col_offset,
                left=new_left,
                ops=expr.ops,
                comparators=new_comps,
            )

        if isinstance(expr, Concat):
            val = self._try_eval(expr)
            if val is not _UNRESOLVED:
                return Const(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    value=val,
                )
            new_nodes = tuple(self._transform_expr(n) for n in expr.nodes)
            if all(n is o for n, o in zip(new_nodes, expr.nodes, strict=True)):
                return expr
            return Concat(
                lineno=expr.lineno,
                col_offset=expr.col_offset,
                nodes=new_nodes,
            )

        if isinstance(expr, FuncCall):
            val = self._try_eval(expr)
            if val is not _UNRESOLVED:
                return Const(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    value=val,
                )
            new_func = self._transform_expr(expr.func)
            new_args = tuple(self._transform_expr(a) for a in expr.args)
            new_kwargs = {k: self._transform_expr(v) for k, v in expr.kwargs.items()}
            new_dyn_args = self._transform_expr(expr.dyn_args) if expr.dyn_args else expr.dyn_args
            new_dyn_kwargs = (
                self._transform_expr(expr.dyn_kwargs) if expr.dyn_kwargs else expr.dyn_kwargs
            )
            if (
                new_func is expr.func
                and all(n is o for n, o in zip(new_args, expr.args, strict=True))
                and all(new_kwargs[k] is expr.kwargs[k] for k in expr.kwargs)
                and new_dyn_args is expr.dyn_args
                and new_dyn_kwargs is expr.dyn_kwargs
            ):
                return expr
            return FuncCall(
                lineno=expr.lineno,
                col_offset=expr.col_offset,
                func=new_func,
                args=new_args,
                kwargs=new_kwargs,
                dyn_args=new_dyn_args,
                dyn_kwargs=new_dyn_kwargs,
            )

        if isinstance(expr, List):
            val = self._try_eval(expr)
            if val is not _UNRESOLVED:
                return Const(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    value=val,
                )
            new_items = tuple(self._transform_expr(i) for i in expr.items)
            if all(n is o for n, o in zip(new_items, expr.items, strict=True)):
                return expr
            return List(
                lineno=expr.lineno,
                col_offset=expr.col_offset,
                items=new_items,
            )

        if isinstance(expr, Tuple):
            val = self._try_eval(expr)
            if val is not _UNRESOLVED:
                return Const(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    value=val,
                )
            new_items = tuple(self._transform_expr(i) for i in expr.items)
            if all(n is o for n, o in zip(new_items, expr.items, strict=True)):
                return expr
            return Tuple(
                lineno=expr.lineno,
                col_offset=expr.col_offset,
                items=new_items,
                ctx=expr.ctx,
            )

        if isinstance(expr, Dict):
            val = self._try_eval(expr)
            if val is not _UNRESOLVED:
                return Const(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    value=val,
                )
            new_keys = tuple(self._transform_expr(k) for k in expr.keys)
            new_vals = tuple(self._transform_expr(v) for v in expr.values)
            if all(n is o for n, o in zip(new_keys, expr.keys, strict=True)) and all(
                n is o for n, o in zip(new_vals, expr.values, strict=True)
            ):
                return expr
            return Dict(
                lineno=expr.lineno,
                col_offset=expr.col_offset,
                keys=new_keys,
                values=new_vals,
            )

        return expr

    def _transform_boolop(self, expr: BoolOp) -> Expr:
        """Partially simplify BoolOp when some operands are statically known.

        Template expressions have no side effects, so short-circuiting
        is always safe:
        - ``false and X`` → ``False``
        - ``true or X`` → ``True``
        - Mixed: filter out resolved non-terminating operands.
        """
        # First try full evaluation
        val = self._try_eval(expr)
        if val is not _UNRESOLVED:
            return Const(lineno=expr.lineno, col_offset=expr.col_offset, value=val)

        # Partial simplification: walk operands left to right
        remaining: list[Expr] = []
        for val_node in expr.values:
            resolved = self._try_eval(val_node)
            if resolved is _UNRESOLVED:
                remaining.append(self._transform_expr(val_node))
                continue

            if expr.op == "and":
                if not resolved:
                    # Short-circuit: falsy value terminates 'and'
                    return Const(lineno=expr.lineno, col_offset=expr.col_offset, value=resolved)
                # Truthy value in 'and' — skip it (doesn't affect result)
            else:  # "or"
                if resolved:
                    # Short-circuit: truthy value terminates 'or'
                    return Const(lineno=expr.lineno, col_offset=expr.col_offset, value=resolved)
                # Falsy value in 'or' — skip it (doesn't affect result)

        if not remaining:
            # All operands were static and non-terminating — return last value
            return Const(lineno=expr.lineno, col_offset=expr.col_offset, value=resolved)

        if len(remaining) == 1:
            return remaining[0]

        if len(remaining) == len(expr.values):
            return expr  # Nothing changed

        return BoolOp(
            lineno=expr.lineno,
            col_offset=expr.col_offset,
            op=expr.op,
            values=tuple(remaining),
        )

    def _transform_condexpr(self, expr: CondExpr) -> Expr:
        """Collapse CondExpr when the test resolves statically."""
        test_val = self._try_eval(expr.test)
        if test_val is not _UNRESOLVED:
            winner = expr.if_true if test_val else expr.if_false
            # Try to fully resolve the winning branch
            winner_val = self._try_eval(winner)
            if winner_val is not _UNRESOLVED:
                return Const(lineno=expr.lineno, col_offset=expr.col_offset, value=winner_val)
            return self._transform_expr(winner)
        return expr


@final
@dataclass(frozen=True, slots=True)
class _InlinedBody(Node):
    """Temporary node for inlined If branches.

    Holds multiple nodes that replace a single If node.  The parent's
    ``_transform_body`` flattens these into the body sequence.

    """

    nodes: Sequence[Node] = ()


def _compare_op(op: str, left: Any, right: Any) -> bool:
    """Evaluate a comparison operator."""
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    if op == ">":
        return left > right
    if op == ">=":
        return left >= right
    if op == "in":
        return left in right
    if op == "not in":
        return left not in right
    if op == "is":
        return left is right
    if op == "is not":
        return left is not right
    msg = f"Unknown comparison operator: {op}"
    raise ValueError(msg)


def partial_evaluate(
    template: Template,
    static_context: dict[str, Any],
    *,
    escape_func: Any | None = None,
    pure_filters: frozenset[str] = frozenset(),
    filter_callables: dict[str, Callable[..., Any]] | None = None,
    inline_components: bool = False,
) -> Template:
    """Convenience function: partially evaluate a template AST.

    Args:
        template: Parsed template AST.
        static_context: Values known at compile time.
        escape_func: HTML escape function for static Output nodes.
        pure_filters: Filter names safe for compile-time evaluation.
        filter_callables: Filter name to callable for Filter/Pipeline eval.
        inline_components: When True, small {% def %} calls with all-constant
            arguments are expanded inline at compile time.

    Returns:
        Transformed template AST with static expressions replaced.

    """
    if not static_context:
        return template

    from kida.utils.constants import MAX_PARTIAL_EVAL_DEPTH, PURE_FILTERS_ALL

    all_pure = PURE_FILTERS_ALL | pure_filters

    evaluator = PartialEvaluator(
        static_context,
        escape_func=escape_func,
        pure_filters=all_pure,
        filter_callables=filter_callables or {},
        max_eval_depth=MAX_PARTIAL_EVAL_DEPTH,
        inline_components=inline_components,
    )
    result = evaluator.evaluate(template)

    # Flatten any _InlinedBody nodes
    return _flatten_inlined(result)


def _flatten_inlined(template: Template) -> Template:
    """Flatten _InlinedBody nodes from branch elimination."""
    new_body = _flatten_body(template.body)
    if new_body is template.body:
        return template
    return Template(
        lineno=template.lineno,
        col_offset=template.col_offset,
        body=new_body,
        extends=template.extends,
        context_type=template.context_type,
    )


def _flatten_body(body: Sequence[Node]) -> Sequence[Node]:
    """Flatten any _InlinedBody nodes in a body sequence."""
    result: list[Node] = []
    changed = False
    for node in body:
        if isinstance(node, _InlinedBody):
            changed = True
            for inner in node.nodes:
                if isinstance(inner, _InlinedBody):
                    result.extend(inner.nodes)
                else:
                    result.append(inner)
        elif isinstance(node, Block):
            new_block_body = _flatten_body(node.body)
            if new_block_body is not node.body:
                changed = True
                result.append(
                    Block(
                        lineno=node.lineno,
                        col_offset=node.col_offset,
                        name=node.name,
                        body=new_block_body,
                        scoped=node.scoped,
                        required=node.required,
                    )
                )
            else:
                result.append(node)
        elif isinstance(node, CallBlock):
            new_slots = {k: _flatten_body(v) for k, v in node.slots.items()}
            if any(new_slots[k] is not node.slots[k] for k in node.slots):
                changed = True
                result.append(
                    CallBlock(
                        lineno=node.lineno,
                        col_offset=node.col_offset,
                        call=node.call,
                        slots=new_slots,
                        args=node.args,
                    )
                )
            else:
                result.append(node)
        elif isinstance(node, SlotBlock):
            new_body = _flatten_body(node.body)
            if new_body is not node.body:
                changed = True
                result.append(
                    SlotBlock(
                        lineno=node.lineno,
                        col_offset=node.col_offset,
                        name=node.name,
                        body=new_body,
                    )
                )
            else:
                result.append(node)
        else:
            result.append(node)

    if not changed:
        return body
    return tuple(result)
