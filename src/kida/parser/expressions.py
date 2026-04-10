"""Expression parsing for Kida parser.

Provides mixin for parsing expressions (ternary, binary, unary, primary, etc.).

Uses inline TYPE_CHECKING declarations for host attributes and cross-mixin
dependencies. See: plan/rfc-mixin-protocol-typing.md
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kida._types import Token, TokenType
from kida.nodes import (
    Await,
    BinOp,
    BoolOp,
    Compare,
    CondExpr,
    Const,
    Dict,
    Filter,
    FuncCall,
    Getattr,
    Getitem,
    List,
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
    Tuple,
    UnaryOp,
)
from kida.utils.constants import MAX_FILTER_CHAIN_LEN

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from kida.nodes import Expr
    from kida.parser.errors import ParseError

# Python-style boolean/none keywords (canonical)
# Lowercase also accepted for convenience
BOOL_TRUE = frozenset({"True", "true"})
BOOL_FALSE = frozenset({"False", "false"})
BOOL_NONE = frozenset({"None", "none"})
BOOL_KEYWORDS = BOOL_TRUE | BOOL_FALSE | BOOL_NONE


class ExpressionParsingMixin:
    """Mixin for parsing expressions.

    Host attributes accessed via inline TYPE_CHECKING declarations.
    See: plan/rfc-mixin-protocol-typing.md

    """

    # ─────────────────────────────────────────────────────────────────────────
    # Host attributes and cross-mixin dependencies (type-check only)
    # NOTE: Do NOT declare _current as a class variable - it's a property in
    # TokenNavigationMixin and declaring it here causes [override] errors
    # ─────────────────────────────────────────────────────────────────────────
    if TYPE_CHECKING:
        # From host (Parser.__init__)
        _tokens: Sequence[Token]
        _pos: int
        _name: str | None
        _filename: str | None
        _source: str | None
        _autoescape: bool
        _block_stack: list[tuple[str, int, int]]

        # From TokenNavigationMixin (via property)
        @property
        def _current(self) -> Token: ...

        # From TokenNavigationMixin (methods)
        def _advance(self) -> Token: ...
        def _match(self, *types: TokenType) -> bool: ...
        def _expect(self, token_type: TokenType) -> Token: ...
        def _peek(self, offset: int = 0) -> Token: ...
        def _error(
            self,
            message: str,
            token: Token | None = None,
            suggestion: str | None = None,
        ) -> ParseError: ...

        # From StatementParsingMixin
        def _parse_for_target(self) -> Expr: ...

    def _parse_expression(self) -> Expr:
        """Parse expression with ternary and null coalescing.

        Filters are handled at higher precedence (in _parse_unary_postfix).
        Null coalescing (??) has lowest precedence (below or).
        """
        return self._parse_null_coalesce()

    def _parse_null_coalesce(self) -> Expr:
        """Parse null coalescing: a ?? b.

        Returns b if a is None/undefined, otherwise a.
        Right-associative: a ?? b ?? c = a ?? (b ?? c)
        Part of RFC: kida-modern-syntax-features.
        """
        left = self._parse_ternary()

        while self._match(TokenType.NULLISH_COALESCE):
            self._advance()  # consume ??
            # Right-associative: parse right side as full null coalesce
            right = self._parse_null_coalesce()
            left = NullCoalesce(
                lineno=left.lineno,
                col_offset=left.col_offset,
                left=left,
                right=right,
            )

        return left

    def _parse_ternary(self) -> Expr:
        """Parse ternary conditional: a if b else c

        Jinja2 also supports short form: a if b (defaults to '' if false)

        The condition can include filters because filters have higher precedence
        than comparisons: x if y | length > 0 else z
        """
        # Parse the "true" value first
        expr = self._parse_or()

        # Check for "if" keyword
        if self._current.type == TokenType.NAME and self._current.value == "if":
            self._advance()  # consume "if"

            # Parse condition using full expression (filters handled in postfix)
            test = self._parse_or()

            # Check for optional "else" - Jinja2 allows short form: 's' if x (returns '' if false)
            if self._current.type == TokenType.NAME and self._current.value == "else":
                self._advance()  # consume "else"
                # Parse the "false" value (right-associative)
                else_expr = self._parse_ternary()
            else:
                # Short form: return empty string if condition is false
                else_expr = Const(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    value="",
                )

            return CondExpr(
                lineno=expr.lineno,
                col_offset=expr.col_offset,
                test=test,
                if_true=expr,
                if_false=else_expr,
            )

        return expr

    def _parse_null_coalesce_no_ternary(self) -> Expr:
        """Parse null coalescing without ternary support.

        Used in for loops where we need ?? but not ternary (to preserve inline if):
            {% for x in items ?? [] %}           ← works
            {% for x in items if x.visible %}    ← still works

        Part of RFC: kida-modern-syntax-features.
        """
        left = self._parse_or()

        while self._match(TokenType.NULLISH_COALESCE):
            self._advance()  # consume ??
            # Right-associative: parse right side recursively
            right = self._parse_null_coalesce_no_ternary()
            left = NullCoalesce(
                lineno=left.lineno,
                col_offset=left.col_offset,
                left=left,
                right=right,
            )

        return left

    def _parse_or(self) -> Expr:
        """Parse 'or' expression."""
        return self._parse_binary(self._parse_and, TokenType.OR)

    def _parse_and(self) -> Expr:
        """Parse 'and' expression."""
        return self._parse_binary(self._parse_not, TokenType.AND)

    def _parse_not(self) -> Expr:
        """Parse 'not' expression."""
        if self._match(TokenType.NOT):
            token = self._advance()
            operand = self._parse_not()
            return UnaryOp(
                lineno=token.lineno,
                col_offset=token.col_offset,
                op="not",
                operand=operand,
            )
        return self._parse_comparison()

    def _parse_comparison(self) -> Expr:
        """Parse comparison expression."""
        left = self._parse_addition()

        ops = []
        comparators = []

        while self._match(
            TokenType.EQ,
            TokenType.NE,
            TokenType.LT,
            TokenType.LE,
            TokenType.GT,
            TokenType.GE,
            TokenType.IN,
            TokenType.IS,
            TokenType.NOT,  # For 'not in'
        ):
            op_token = self._advance()
            op = op_token.value

            # Handle 'not in': when we see 'not', expect 'in' to follow
            if op == "not":
                if self._match(TokenType.IN):
                    self._advance()
                    op = "not in"
                else:
                    raise self._error(
                        "Expected 'in' after 'not' in comparison",
                        suggestion="Use 'not in' for membership test: {% if item not in items %}",
                    )
            elif op == "is" and self._match(TokenType.NOT):
                self._advance()
                op = "is not"

            # Handle tests: "is defined", "is not mapping", "is sameas false", etc.
            if op in ("is", "is not"):
                # Check if next token is a test name (NAME token, but NOT a boolean keyword)
                # Boolean keywords like True/False/None should be identity comparisons, not tests
                if (
                    self._current.type == TokenType.NAME
                    and self._current.value not in BOOL_KEYWORDS
                ):
                    test_name = self._advance().value

                    # Parse optional arguments
                    # Jinja2 style: is divisibleby(3) OR is sameas false (no parens)
                    test_args: list[Expr] = []
                    test_kwargs: dict[str, Expr] = {}
                    if self._match(TokenType.LPAREN):
                        # Arguments in parentheses: is divisibleby(3)
                        self._advance()
                        test_args, test_kwargs = self._parse_call_args()
                        self._expect(TokenType.RPAREN)
                    elif self._can_start_test_arg():
                        # Single argument without parens: is sameas false, is sameas none
                        # Only parse simple values to avoid ambiguity
                        test_args = [self._parse_primary()]

                    # Create Test node
                    left = Test(
                        lineno=left.lineno,
                        col_offset=left.col_offset,
                        value=left,
                        name=test_name,
                        args=tuple(test_args),
                        kwargs=test_kwargs,
                        negated=(op == "is not"),
                    )
                    continue  # Don't add to ops/comparators
                else:
                    # Regular "is" comparison (identity check)
                    pass

            ops.append(op)
            comparators.append(self._parse_addition())

        if ops:
            return Compare(
                lineno=left.lineno,
                col_offset=left.col_offset,
                left=left,
                ops=tuple(ops),
                comparators=tuple(comparators),
            )

        return left

    def _can_start_test_arg(self) -> bool:
        """Check if current token can start a test argument without parens.

        Used for: is sameas False, is sameas None
        Only allow simple values to avoid ambiguity with following expressions.
        """
        # Allow: True, False, None, numbers, strings
        if self._current.type in (TokenType.INTEGER, TokenType.FLOAT, TokenType.STRING):
            return True
        if self._current.type == TokenType.NAME:
            # Only allow boolean/none keywords as bare args
            return self._current.value in BOOL_KEYWORDS
        return False

    def _parse_addition(self) -> Expr:
        """Parse addition/subtraction/concatenation.

        The ~ operator is string concatenation in Jinja.
        """
        return self._parse_binary(
            self._parse_multiplication_with_filters,
            TokenType.ADD,
            TokenType.SUB,
            TokenType.TILDE,
        )

    def _parse_multiplication_with_filters(self) -> Expr:
        """Parse multiplication/division with filter chain.

        Filters are applied after multiplication but before addition:
        a + b | filter  parses as  a + (b | filter)
        a * b | filter  parses as  (a * b) | filter
        -42 | abs       parses as  (-42) | abs  → 42
        """
        expr = self._parse_multiplication()
        return self._parse_filter_chain(expr)

    def _parse_multiplication(self) -> Expr:
        """Parse multiplication/division."""
        return self._parse_binary(
            self._parse_unary,
            TokenType.MUL,
            TokenType.DIV,
            TokenType.FLOORDIV,
            TokenType.MOD,
        )

    def _parse_unary(self) -> Expr:
        """Parse unary operators.

        Unary operators bind tighter than filters:
        -42|abs  parses as  (-42)|abs  → 42

        Also handles {{ await expr }} — RFC: rfc-async-rendering.
        """
        if self._match(TokenType.SUB, TokenType.ADD):
            token = self._advance()
            operand = self._parse_unary()
            return UnaryOp(
                lineno=token.lineno,
                col_offset=token.col_offset,
                op="-" if token.type == TokenType.SUB else "+",
                operand=operand,
            )

        # Handle {{ await expr }} as a unary prefix (RFC: rfc-async-rendering)
        if self._current.type == TokenType.NAME and self._current.value == "await":
            token = self._advance()  # consume 'await'
            value = self._parse_unary()  # parse the awaitable expression
            return Await(
                lineno=token.lineno,
                col_offset=token.col_offset,
                value=value,
            )

        return self._parse_power()

    def _parse_power(self) -> Expr:
        """Parse power operator."""
        left = self._parse_primary_postfix()

        if self._match(TokenType.POW):
            self._advance()
            right = self._parse_unary()  # Right associative
            return BinOp(
                lineno=left.lineno,
                col_offset=left.col_offset,
                op="**",
                left=left,
                right=right,
            )

        return left

    def _parse_list_comprehension(self, start_token: Token, elt: Expr) -> ListComp:
        """Parse list comprehension after '[expr for ...'.

        Called when _parse_primary() has consumed '[' and the element expression,
        and the current token is NAME 'for'.
        """
        # Consume 'for'
        self._advance()

        # Parse target (reuse from StatementParsingMixin via mixin composition)
        target = self._parse_for_target()

        # Expect 'in'
        self._expect(TokenType.IN)

        # Parse iterable — use _parse_or() to avoid consuming 'if' as ternary
        iter_expr = self._parse_or()

        # Optional 'if' clause
        ifs: list[Expr] = []
        if self._current.type == TokenType.NAME and self._current.value == "if":
            self._advance()
            ifs.append(self._parse_or())

        # Reject nested 'for' clauses (not supported in v1)
        if self._current.type == TokenType.NAME and self._current.value == "for":
            raise self._error(
                "Nested 'for' clauses are not supported in list comprehensions. "
                "Use a {% for %} block instead.",
                suggestion="[expr for x in iterable if condition]",
            )

        # Reject async comprehensions (await in element expression)
        if self._contains_await(elt):
            raise self._error(
                "Async list comprehensions are not supported. "
                "Use a {% for %} block with await instead.",
            )

        # Expect closing ']'
        self._expect(TokenType.RBRACKET)

        return ListComp(
            lineno=start_token.lineno,
            col_offset=start_token.col_offset,
            elt=elt,
            target=target,
            iter=iter_expr,
            ifs=tuple(ifs),
        )

    @staticmethod
    def _contains_await(node: object) -> bool:
        """Check if an expression tree contains an Await node."""
        if isinstance(node, Await):
            return True
        from kida.nodes.base import Node

        if isinstance(node, Node):
            for child in node.iter_child_nodes():
                if ExpressionParsingMixin._contains_await(child):
                    return True
        return False

    def _parse_primary_postfix(self) -> Expr:
        """Parse primary expressions with postfix operators (., [], (), ?., ?[).

        Does NOT include filter operator (|) - filters are parsed at a
        lower precedence level in _parse_filter_chain.

        Supports optional chaining: ?. and ?[ (RFC: kida-modern-syntax-features).
        """
        expr = self._parse_primary()

        while True:
            if self._match(TokenType.DOT):
                self._advance()
                if self._current.type != TokenType.NAME:
                    raise self._error("Expected attribute name")
                attr = self._advance().value
                expr = Getattr(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    obj=expr,
                    attr=attr,
                )
            elif self._match(TokenType.OPTIONAL_DOT):
                # Optional chaining: obj?.attr
                # Part of RFC: kida-modern-syntax-features
                self._advance()
                if self._current.type != TokenType.NAME:
                    raise self._error("Expected attribute name after ?.")
                attr = self._advance().value
                expr = OptionalGetattr(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    obj=expr,
                    attr=attr,
                )
            elif self._match(TokenType.LBRACKET):
                self._advance()
                key = self._parse_subscript()
                self._expect(TokenType.RBRACKET)
                expr = Getitem(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    obj=expr,
                    key=key,
                )
            elif self._match(TokenType.OPTIONAL_BRACKET):
                # Optional subscript: obj?[key]
                # Part of RFC: kida-modern-syntax-features
                self._advance()
                key = self._parse_subscript()
                self._expect(TokenType.RBRACKET)
                expr = OptionalGetitem(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    obj=expr,
                    key=key,
                )
            elif self._match(TokenType.LPAREN):
                self._advance()
                args, kwargs = self._parse_call_args()
                self._expect(TokenType.RPAREN)
                expr = FuncCall(
                    lineno=expr.lineno,
                    col_offset=expr.col_offset,
                    func=expr,
                    args=tuple(args),
                    kwargs=kwargs,
                )
            elif self._match(TokenType.RANGE_INCLUSIVE, TokenType.RANGE_EXCLUSIVE):
                # Range literal: 1..10 or 1...11
                # Part of RFC: kida-modern-syntax-features
                expr = self._parse_range(expr)
            else:
                break

        return expr

    def _parse_range(self, start: Expr) -> Range:
        """Parse range literal after seeing start value.

        Syntax:
            1..10    → inclusive range [1, 10]
            1...11   → exclusive range [1, 11) (like Python range)
            1..10 by 2  → range with step

        Part of RFC: kida-modern-syntax-features.
        """
        inclusive = self._current.type == TokenType.RANGE_INCLUSIVE
        self._advance()  # consume .. or ...

        # Parse end value
        end = self._parse_unary()  # Use unary for precedence

        # Optional step: 'by' keyword
        step: Expr | None = None
        if self._current.type == TokenType.NAME and self._current.value == "by":
            self._advance()  # consume 'by'
            step = self._parse_unary()

        return Range(
            lineno=start.lineno,
            col_offset=start.col_offset,
            start=start,
            end=end,
            inclusive=inclusive,
            step=step,
        )

    def _parse_filter_chain(self, expr: Expr) -> Expr:
        """Parse filter chain: expr | filter1 | filter2(arg).

        Also handles pipeline operator: expr |> filter1 |> filter2(arg).
        Also handles safe pipeline: expr ?|> filter1 ?|> filter2(arg).
        Also handles optional filter: expr ?| filter(args).

        Design: Mixing | and |> in the same expression is not allowed.
        The first operator encountered determines the style for the expression.

        Filters are parsed after unary operators:
        -42|abs  parses as  (-42)|abs  → 42
        """
        # Check for pipeline operators first
        if self._match(TokenType.PIPELINE):
            return self._parse_pipeline(expr)
        if self._match(TokenType.SAFE_PIPELINE):
            return self._parse_safe_pipeline(expr)

        # Standard filter chain with | or optional filter with ?|
        filter_count = 0
        while self._match(TokenType.PIPE, TokenType.OPTIONAL_PIPE):
            is_optional = self._current.type == TokenType.OPTIONAL_PIPE
            self._advance()
            filter_count += 1
            if filter_count > MAX_FILTER_CHAIN_LEN:
                raise self._error(
                    f"Filter chain exceeds maximum length ({MAX_FILTER_CHAIN_LEN})",
                    suggestion="Simplify the expression or split into multiple variables",
                )

            # Error if switching from | to |> mid-expression
            if self._match(TokenType.PIPELINE, TokenType.SAFE_PIPELINE):
                raise self._error(
                    "Cannot mix '|' and '|>' operators in the same expression",
                    suggestion="Use either '|' or '|>' consistently: {{ x | a | b }} or {{ x |> a |> b }}",
                )

            if self._current.type != TokenType.NAME:
                raise self._error("Expected filter name")
            filter_name = self._advance().value

            args: list[Expr] = []
            kwargs: dict[str, Expr] = {}

            # Optional arguments
            if self._match(TokenType.LPAREN):
                self._advance()
                args, kwargs = self._parse_call_args()
                self._expect(TokenType.RPAREN)

            node_cls = OptionalFilter if is_optional else Filter
            expr = node_cls(
                lineno=expr.lineno,
                col_offset=expr.col_offset,
                value=expr,
                name=filter_name,
                args=tuple(args),
                kwargs=kwargs,
            )

        # Error if switching from | to |> after the filter chain
        if self._match(TokenType.PIPELINE, TokenType.SAFE_PIPELINE):
            raise self._error(
                "Cannot mix '|' and '|>' operators in the same expression",
                suggestion="Use either '|' or '|>' consistently: {{ x | a | b }} or {{ x |> a |> b }}",
            )

        return expr

    def _parse_pipeline(self, expr: Expr) -> Expr:
        """Parse pipeline chain: expr |> filter1 |> filter2(arg).

        Pipelines are left-associative: a |> b |> c == (a |> b) |> c

        Each step is a filter application. The pipeline collects all
        steps into a single Pipeline node for potential optimization.

        Design: Mixing | and |> is not allowed. Error on | after |>.
        """
        steps: list[tuple[str, Sequence[Expr], dict[str, Expr]]] = []

        while self._match(TokenType.PIPELINE):
            self._advance()  # consume |>

            if self._current.type != TokenType.NAME:
                raise self._error(
                    "Expected filter name after |>",
                    suggestion="Pipeline syntax: expr |> filter_name or expr |> filter_name(args)",
                )

            filter_name = self._advance().value

            args: list[Expr] = []
            kwargs: dict[str, Expr] = {}

            # Optional arguments
            if self._match(TokenType.LPAREN):
                self._advance()
                args, kwargs = self._parse_call_args()
                self._expect(TokenType.RPAREN)

            steps.append((filter_name, tuple(args), kwargs))
            if len(steps) > MAX_FILTER_CHAIN_LEN:
                raise self._error(
                    f"Pipeline exceeds maximum length ({MAX_FILTER_CHAIN_LEN})",
                    suggestion="Simplify the expression or split into multiple variables",
                )

        # Error if switching from |> to | mid-expression
        if self._match(TokenType.PIPE):
            raise self._error(
                "Cannot mix '|>' and '|' operators in the same expression",
                suggestion="Use either '|>' or '|' consistently: {{ x |> a |> b }} or {{ x | a | b }}",
            )

        if not steps:
            return expr

        return Pipeline(
            lineno=expr.lineno,
            col_offset=expr.col_offset,
            value=expr,
            steps=tuple(steps),
        )

    def _parse_safe_pipeline(self, expr: Expr) -> Expr:
        """Parse safe pipeline: expr ?|> filter1 ?|> filter2(arg).

        None-propagating: if expr is None, the entire pipeline returns None
        without calling any filters. Each step checks for None before applying.
        """
        steps: list[tuple[str, Sequence[Expr], dict[str, Expr]]] = []

        while self._match(TokenType.SAFE_PIPELINE):
            self._advance()  # consume ?|>

            if self._current.type != TokenType.NAME:
                raise self._error(
                    "Expected filter name after ?|>",
                    suggestion="Safe pipeline syntax: expr ?|> filter_name or expr ?|> filter_name(args)",
                )

            filter_name = self._advance().value

            args: list[Expr] = []
            kwargs: dict[str, Expr] = {}

            if self._match(TokenType.LPAREN):
                self._advance()
                args, kwargs = self._parse_call_args()
                self._expect(TokenType.RPAREN)

            steps.append((filter_name, tuple(args), kwargs))
            if len(steps) > MAX_FILTER_CHAIN_LEN:
                raise self._error(
                    f"Safe pipeline exceeds maximum length ({MAX_FILTER_CHAIN_LEN})",
                    suggestion="Simplify the expression or split into multiple variables",
                )

        # Error if mixing operators
        if self._match(TokenType.PIPE, TokenType.PIPELINE, TokenType.OPTIONAL_PIPE):
            raise self._error(
                "Cannot mix '?|>' with '|', '|>', or '?|' operators",
                suggestion="Use ?|> consistently for safe pipelines: {{ x ?|> a ?|> b }}",
            )

        if not steps:
            return expr

        return SafePipeline(
            lineno=expr.lineno,
            col_offset=expr.col_offset,
            value=expr,
            steps=tuple(steps),
        )

    def _parse_subscript(self) -> Expr:
        """Parse subscript: key or slice [start:stop:step]."""
        lineno = self._current.lineno
        col = self._current.col_offset

        # Check if this is a slice (starts with : or has : after first expr)
        start: Expr | None = None
        stop: Expr | None = None
        step: Expr | None = None

        # Parse start (if not starting with :)
        if not self._match(TokenType.COLON):
            start = self._parse_expression()

            # If no colon follows, this is just a regular subscript
            if not self._match(TokenType.COLON):
                return start

        # Consume first colon
        self._advance()

        # Parse stop (if not : or ])
        if not self._match(TokenType.COLON, TokenType.RBRACKET):
            stop = self._parse_expression()

        # Check for step
        if self._match(TokenType.COLON):
            self._advance()
            if not self._match(TokenType.RBRACKET):
                step = self._parse_expression()

        return Slice(
            lineno=lineno,
            col_offset=col,
            start=start,
            stop=stop,
            step=step,
        )

    def _parse_primary(self) -> Expr:
        """Parse primary expression."""
        token = self._current

        # String literal
        if token.type == TokenType.STRING:
            self._advance()
            return Const(
                lineno=token.lineno,
                col_offset=token.col_offset,
                value=token.value,
            )

        # Integer literal
        if token.type == TokenType.INTEGER:
            self._advance()
            return Const(
                lineno=token.lineno,
                col_offset=token.col_offset,
                value=int(token.value),
            )

        # Float literal
        if token.type == TokenType.FLOAT:
            self._advance()
            return Const(
                lineno=token.lineno,
                col_offset=token.col_offset,
                value=float(token.value),
            )

        # Name or keyword constant
        if token.type == TokenType.NAME:
            self._advance()
            if token.value in BOOL_TRUE:
                return Const(token.lineno, token.col_offset, True)
            elif token.value in BOOL_FALSE:
                return Const(token.lineno, token.col_offset, False)
            elif token.value in BOOL_NONE:
                return Const(token.lineno, token.col_offset, None)
            return Name(
                lineno=token.lineno,
                col_offset=token.col_offset,
                name=token.value,
            )

        # Parenthesized expression or tuple
        if token.type == TokenType.LPAREN:
            self._advance()
            if self._match(TokenType.RPAREN):
                self._advance()
                return Tuple(token.lineno, token.col_offset, ())

            expr = self._parse_expression()

            if self._match(TokenType.COMMA):
                # Tuple
                items = [expr]
                while self._match(TokenType.COMMA):
                    self._advance()
                    if self._match(TokenType.RPAREN):
                        break
                    items.append(self._parse_expression())
                self._expect(TokenType.RPAREN)
                return Tuple(token.lineno, token.col_offset, tuple(items))

            self._expect(TokenType.RPAREN)
            return expr

        # List
        if token.type == TokenType.LBRACKET:
            self._advance()
            # Empty list: []
            if self._match(TokenType.RBRACKET):
                self._advance()
                return List(token.lineno, token.col_offset, ())

            # Parse first element
            elt = self._parse_expression()

            # List comprehension: [expr for x in iterable if cond]
            if self._current.type == TokenType.NAME and self._current.value == "for":
                return self._parse_list_comprehension(token, elt)

            # List literal: [a, b, c]
            items = [elt]
            while self._match(TokenType.COMMA):
                self._advance()
                if self._match(TokenType.RBRACKET):
                    break
                items.append(self._parse_expression())
            self._expect(TokenType.RBRACKET)
            return List(token.lineno, token.col_offset, tuple(items))

        # Dict literal: {} or {key: value, ...}
        if token.type == TokenType.LBRACE:
            self._advance()
            keys = []
            values = []
            if not self._match(TokenType.RBRACE):
                # Parse first key:value pair
                key = self._parse_expression()
                self._expect(TokenType.COLON)
                value = self._parse_expression()
                keys.append(key)
                values.append(value)
                # Parse remaining pairs
                while self._match(TokenType.COMMA):
                    self._advance()
                    if self._match(TokenType.RBRACE):
                        break
                    key = self._parse_expression()
                    self._expect(TokenType.COLON)
                    value = self._parse_expression()
                    keys.append(key)
                    values.append(value)
            self._expect(TokenType.RBRACE)
            return Dict(token.lineno, token.col_offset, tuple(keys), tuple(values))

        raise self._error(
            f"Unexpected token: {token.type.value}",
            token=token,
            suggestion="Expected a value (string, number, variable name, list, or dict)",
        )

    def _parse_binary(
        self,
        operand_parser: Callable[[], Expr],
        *op_types: TokenType,
    ) -> Expr:
        """Generic binary expression parser."""
        left = operand_parser()

        while self._match(*op_types):
            op_token = self._advance()
            right = operand_parser()

            if op_token.type in (TokenType.AND, TokenType.OR):
                left = BoolOp(
                    lineno=left.lineno,
                    col_offset=left.col_offset,
                    op="and" if op_token.type == TokenType.AND else "or",
                    values=(left, right),
                )
            else:
                left = BinOp(
                    lineno=left.lineno,
                    col_offset=left.col_offset,
                    op=self._token_to_op(op_token.type),
                    left=left,
                    right=right,
                )

        return left

    def _parse_call_args(self) -> tuple[list[Expr], dict[str, Expr]]:
        """Parse function call arguments."""
        args: list[Expr] = []
        kwargs: dict[str, Expr] = {}

        if self._match(TokenType.RPAREN):
            return args, kwargs

        while True:
            # Check for keyword argument
            if self._current.type == TokenType.NAME and self._peek(1).type == TokenType.ASSIGN:
                name = self._advance().value
                self._advance()  # consume =
                kwargs[name] = self._parse_expression()
            else:
                args.append(self._parse_expression())

            if not self._match(TokenType.COMMA):
                break
            self._advance()

        return args, kwargs

    def _token_to_op(self, token_type: TokenType) -> str:
        """Map token type to operator string."""
        mapping = {
            TokenType.ADD: "+",
            TokenType.SUB: "-",
            TokenType.MUL: "*",
            TokenType.DIV: "/",
            TokenType.FLOORDIV: "//",
            TokenType.MOD: "%",
            TokenType.POW: "**",
            TokenType.TILDE: "~",  # String concatenation
        }
        op = mapping.get(token_type)
        if op is None:
            raise ValueError(f"Unmapped token type for binary operator: {token_type!r}")
        return op
