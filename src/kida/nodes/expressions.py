"""Expression nodes for Kida AST."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, final

from kida.nodes.base import Node

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True, slots=True)
class Expr(Node):
    """Base class for expressions."""


@final
@dataclass(frozen=True, slots=True)
class Const(Expr):
    """Constant value: string, number, boolean, None."""

    value: str | int | float | bool | None


@final
@dataclass(frozen=True, slots=True)
class Name(Expr):
    """Variable reference: {{ user }}"""

    name: str
    ctx: Literal["load", "store", "del"] = "load"


@final
@dataclass(frozen=True, slots=True)
class Tuple(Expr):
    """Tuple expression: (a, b, c)"""

    items: Sequence[Expr]
    ctx: Literal["load", "store"] = "load"


@final
@dataclass(frozen=True, slots=True)
class List(Expr):
    """List expression: [a, b, c]"""

    items: Sequence[Expr]


@final
@dataclass(frozen=True, slots=True)
class Dict(Expr):
    """Dict expression: {a: b, c: d}"""

    keys: Sequence[Expr]
    values: Sequence[Expr]


@final
@dataclass(frozen=True, slots=True)
class Getattr(Expr):
    """Attribute access: obj.attr"""

    obj: Expr
    attr: str


@final
@dataclass(frozen=True, slots=True)
class OptionalGetattr(Expr):
    """Optional attribute access: obj?.attr"""

    obj: Expr
    attr: str


@final
@dataclass(frozen=True, slots=True)
class Getitem(Expr):
    """Subscript access: obj[key]"""

    obj: Expr
    key: Expr


@final
@dataclass(frozen=True, slots=True)
class OptionalGetitem(Expr):
    """Optional subscript access: obj?[key]"""

    obj: Expr
    key: Expr


@final
@dataclass(frozen=True, slots=True)
class Slice(Expr):
    """Slice expression: [start:stop:step]"""

    start: Expr | None
    stop: Expr | None
    step: Expr | None


@final
@dataclass(frozen=True, slots=True)
class FuncCall(Expr):
    """Function call: func(args, **kwargs)"""

    func: Expr
    args: Sequence[Expr] = ()
    kwargs: dict[str, Expr] = field(default_factory=dict)
    dyn_args: Expr | None = None
    dyn_kwargs: Expr | None = None


@dataclass(frozen=True, slots=True)
class Filter(Expr):
    """Filter application: expr | filter(args)"""

    value: Expr
    name: str
    args: Sequence[Expr] = ()
    kwargs: dict[str, Expr] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Pipeline(Expr):
    """Pipeline operator: expr |> filter1 |> filter2"""

    value: Expr
    steps: Sequence[tuple[str, Sequence[Expr], dict[str, Expr]]]


@final
@dataclass(frozen=True, slots=True)
class SafePipeline(Pipeline):
    """Safe pipeline: expr ?|> filter1 ?|> filter2 (None-propagating)

    Inherits from Pipeline so purity analysis treats it identically.
    """


@final
@dataclass(frozen=True, slots=True)
class OptionalFilter(Filter):
    """Optional filter: expr ?| filter(args) — skips if value is None

    Inherits from Filter so purity analysis treats it identically.
    """


@final
@dataclass(frozen=True, slots=True)
class Test(Expr):
    """Test application: expr is test(args) or expr is not test(args)"""

    value: Expr
    name: str
    args: Sequence[Expr] = ()
    kwargs: dict[str, Expr] = field(default_factory=dict)
    negated: bool = False


@final
@dataclass(frozen=True, slots=True)
class BinOp(Expr):
    """Binary operation: left op right"""

    op: str
    left: Expr
    right: Expr


@final
@dataclass(frozen=True, slots=True)
class UnaryOp(Expr):
    """Unary operation: op operand"""

    op: str
    operand: Expr


@final
@dataclass(frozen=True, slots=True)
class Compare(Expr):
    """Comparison: left op1 right1 op2 right2 ..."""

    left: Expr
    ops: Sequence[str]
    comparators: Sequence[Expr]


@final
@dataclass(frozen=True, slots=True)
class BoolOp(Expr):
    """Boolean operation: expr1 and/or expr2"""

    op: Literal["and", "or"]
    values: Sequence[Expr]


@final
@dataclass(frozen=True, slots=True)
class CondExpr(Expr):
    """Conditional expression: a if cond else b"""

    test: Expr
    if_true: Expr
    if_false: Expr


@final
@dataclass(frozen=True, slots=True)
class NullCoalesce(Expr):
    """Null coalescing: a ?? b"""

    left: Expr
    right: Expr


@final
@dataclass(frozen=True, slots=True)
class Range(Expr):
    """Range literal: start..end or start...end"""

    start: Expr
    end: Expr
    inclusive: bool = True
    step: Expr | None = None


@final
@dataclass(frozen=True, slots=True)
class Await(Expr):
    """Await expression: await expr"""

    value: Expr


@final
@dataclass(frozen=True, slots=True)
class Concat(Expr):
    """String concatenation: a ~ b ~ c"""

    nodes: Sequence[Expr]


@final
@dataclass(frozen=True, slots=True)
class MarkSafe(Expr):
    """Mark expression as safe (no escaping): {{ expr | safe }}"""

    value: Expr


@final
@dataclass(frozen=True, slots=True)
class LoopVar(Expr):
    """Loop variable access: {{ loop.index }}"""

    attr: str


@final
@dataclass(frozen=True, slots=True)
class InlinedFilter(Expr):
    """Inlined filter as direct method call (optimization)."""

    value: Expr
    method: str
    args: Sequence[Expr] = ()


AnyExpr = (
    Const
    | Name
    | Tuple
    | List
    | Dict
    | Getattr
    | OptionalGetattr
    | Getitem
    | OptionalGetitem
    | Slice
    | FuncCall
    | Filter
    | Pipeline
    | Test
    | BinOp
    | UnaryOp
    | Compare
    | BoolOp
    | CondExpr
    | NullCoalesce
    | Range
    | Await
    | Concat
    | MarkSafe
    | LoopVar
    | InlinedFilter
)
