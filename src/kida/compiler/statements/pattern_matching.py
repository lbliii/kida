"""Pattern matching statement compilation for Kida compiler.

Provides mixin for compiling match/case statements.

Extracted from control_flow.py for module focus (RFC: compiler decomposition).
Uses inline TYPE_CHECKING declarations for host attributes.
See: plan/rfc-mixin-protocol-typing.md
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kida.nodes import Match, Node


class PatternMatchingMixin:
    """Mixin for compiling match/case statements.

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

        # From ExpressionCompilationMixin
        def _compile_expr(self, node: Node, store: bool = False) -> ast.expr: ...

        # From Compiler core
        def _compile_node(self, node: Node) -> list[ast.stmt]: ...

        # From ControlFlowMixin
        def _extract_names(self, node: Node) -> list[str]: ...

    def _compile_match(self, node: Match) -> list[ast.stmt]:
        """Compile {% match expr %}{% case pattern [if guard] %}...{% end %}.

        Generates chained if/elif comparisons with structural pattern matching
        and variable binding support.

        Example:
            {% match site.logo, site.logo_text %}
                {% case logo, _ if logo %}...
            {% end %}

        Generates:
            _match_subject_N = (site.logo, site.logo_text)
            if isinstance(_match_subject_N, (list, tuple)) and len(_match_subject_N) == 2:
                logo = _match_subject_N[0]
                if logo:
                    ...

        Valueless match (switch-true):
            {% match %}
                {% case _ if user.is_admin %}Admin
                {% case _ %}Member
            {% end %}

        When subject is None, generates pure if/elif/else using guard expressions only.
        """
        # Valueless match: compile as pure if/elif/else chain from guards
        if node.subject is None:
            return self._compile_valueless_match(node)

        stmts: list[ast.stmt] = []

        # Use unique variable name to support nested match blocks
        self._block_counter += 1
        subject_var = f"_match_subject_{self._block_counter}"

        # _match_subject_N = expr
        stmts.append(
            ast.Assign(
                targets=[ast.Name(id=subject_var, ctx=ast.Store())],
                value=self._compile_expr(node.subject),
            )
        )

        if not node.cases:
            return stmts

        # Build if/elif chain from cases
        orelse: list[ast.stmt] = []

        for pattern_expr, guard_expr, case_body in reversed(node.cases):
            # 1. Generate pattern match test and variable bindings
            pattern_test, bindings = self._make_pattern_match(
                pattern_expr, ast.Name(id=subject_var, ctx=ast.Load())
            )

            # 2. Track names for body/guard compilation
            bound_names = [name for name, _ in bindings]
            for name in bound_names:
                self._locals.add(name)

            # 3. Build the test condition, including walrus bindings if needed
            # We use walrus operators (name := value) in the test so that
            # variables are bound before the guard is evaluated.
            test = pattern_test
            if bindings:
                walrus_exprs = []
                for name, value_ast in bindings:
                    # (name := value)
                    walrus = ast.NamedExpr(
                        target=ast.Name(id=name, ctx=ast.Store()),
                        value=value_ast,
                    )
                    # (name := value) or True -- ensures the test continues
                    walrus_or_true = ast.BoolOp(
                        op=ast.Or(),
                        values=[walrus, ast.Constant(value=True)],
                    )
                    walrus_exprs.append(walrus_or_true)

                # Combine with existing test
                if isinstance(test, ast.Constant) and test.value is True:
                    if len(walrus_exprs) == 1:
                        test = walrus_exprs[0]
                    else:
                        test = ast.BoolOp(op=ast.And(), values=walrus_exprs)
                else:
                    test = ast.BoolOp(op=ast.And(), values=[test, *walrus_exprs])

            if guard_expr:
                # Guard can now safely refer to bound names
                compiled_guard = self._compile_expr(guard_expr)
                if isinstance(test, ast.Constant) and test.value is True:
                    test = compiled_guard
                else:
                    # Append guard to the And chain
                    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
                        test.values.append(compiled_guard)
                    else:
                        test = ast.BoolOp(
                            op=ast.And(),
                            values=[test, compiled_guard],
                        )

            # 4. Compile case body
            body_stmts: list[ast.stmt] = []
            # We still prepend assignments for clarity and to ensure locals
            # are defined even if something strange happens with short-circuiting.
            for name, value_ast in bindings:
                body_stmts.append(
                    ast.Assign(
                        targets=[ast.Name(id=name, ctx=ast.Store())],
                        value=value_ast,
                    )
                )

            for child in case_body:
                body_stmts.extend(self._compile_node(child))

            if not body_stmts:
                body_stmts = [ast.Pass()]

            # 5. Build If node
            if_node = ast.If(
                test=test,
                body=body_stmts,
                orelse=orelse,
            )
            orelse = [if_node]

            # 6. Cleanup locals after compiling this case
            for name in bound_names:
                self._locals.discard(name)

        # The first case becomes the outermost if
        if orelse:
            stmts.extend(orelse)

        return stmts

    def _compile_valueless_match(self, node: Match) -> list[ast.stmt]:
        """Compile valueless {% match %} as pure if/elif/else chain.

        Each case must use wildcard pattern (_) with an optional guard.
        Non-wildcard patterns are a compile error since there's no subject.

        {% match %}
            {% case _ if x > 0 %}positive
            {% case _ if x == 0 %}zero
            {% case _ %}negative
        {% end %}

        Generates:
            if x > 0:
                _append('positive')
            elif x == 0:
                _append('zero')
            else:
                _append('negative')
        """
        from kida.nodes import Name as KidaName

        if not node.cases:
            return []

        orelse: list[ast.stmt] = []

        for pattern_expr, guard_expr, case_body in reversed(node.cases):
            # Validate: only wildcard patterns allowed in valueless match
            is_wildcard = isinstance(pattern_expr, KidaName) and pattern_expr.name == "_"
            if not is_wildcard:
                raise RuntimeError(
                    "Valueless {% match %} only allows wildcard (_) patterns. "
                    "Use {% match subject %} for value-based pattern matching."
                )

            # Compile case body
            body_stmts: list[ast.stmt] = []
            for child in case_body:
                body_stmts.extend(self._compile_node(child))
            if not body_stmts:
                body_stmts = [ast.Pass()]

            if guard_expr is None:
                # {% case _ %} with no guard = else branch
                # Just set body as orelse for the previous if
                orelse = body_stmts
            else:
                # {% case _ if guard %} = elif guard
                compiled_guard = self._compile_expr(guard_expr)
                if_node = ast.If(
                    test=compiled_guard,
                    body=body_stmts,
                    orelse=orelse,
                )
                orelse = [if_node]

        return orelse

    def _make_pattern_match(
        self, pattern: Node, subject_ast: ast.expr
    ) -> tuple[ast.expr, list[tuple[str, ast.expr]]]:
        """Generate match test and bindings for a pattern.

        Returns:
            (test_ast, [(name, value_ast), ...])
        """
        from kida.nodes import Const as KidaConst
        from kida.nodes import Name as KidaName
        from kida.nodes import Tuple as KidaTuple

        if isinstance(pattern, KidaName):
            if pattern.name == "_":
                # Wildcard pattern: always matches, no bindings
                return ast.Constant(value=True), []
            else:
                # Variable pattern: bind subject to the pattern name
                # Like Python's match statement, names in patterns capture values
                # e.g., {% case x %} binds subject to x, {% case a, b %} binds elements
                return ast.Constant(value=True), [(pattern.name, subject_ast)]

        if isinstance(pattern, KidaTuple):
            # Match fixed-size tuple/sequence
            n = len(pattern.items)

            # Test: _isinstance(subject, (_list, _tuple)) and _len(subject) == n
            type_check = ast.Call(
                func=ast.Name(id="_isinstance", ctx=ast.Load()),
                args=[
                    subject_ast,
                    ast.Tuple(
                        elts=[
                            ast.Name(id="_list", ctx=ast.Load()),
                            ast.Name(id="_tuple", ctx=ast.Load()),
                        ],
                        ctx=ast.Load(),
                    ),
                ],
                keywords=[],
            )
            len_check = ast.Compare(
                left=ast.Call(
                    func=ast.Name(id="_len", ctx=ast.Load()),
                    args=[subject_ast],
                    keywords=[],
                ),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=n)],
            )

            all_bindings = []
            sub_tests = [type_check, len_check]

            for i, item in enumerate(pattern.items):
                # subject[i]
                item_subject = ast.Subscript(
                    value=subject_ast,
                    slice=ast.Constant(value=i),
                    ctx=ast.Load(),
                )
                sub_test, sub_bindings = self._make_pattern_match(item, item_subject)
                if not (isinstance(sub_test, ast.Constant) and sub_test.value is True):
                    sub_tests.append(sub_test)
                all_bindings.extend(sub_bindings)

            if len(sub_tests) == 1:
                test = sub_tests[0]
            else:
                test = ast.BoolOp(op=ast.And(), values=sub_tests)

            return test, all_bindings

        if isinstance(pattern, KidaConst):
            return (
                ast.Compare(
                    left=subject_ast,
                    ops=[ast.Eq()],
                    comparators=[ast.Constant(value=pattern.value)],
                ),
                [],
            )

        # Default: simple equality match for complex expressions
        test = ast.Compare(
            left=subject_ast,
            ops=[ast.Eq()],
            comparators=[self._compile_expr(pattern)],
        )
        return test, []
