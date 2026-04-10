"""i18n statement compilation for Kida compiler.

Compiles Trans nodes to gettext/ngettext calls with proper HTML escaping
via Markup %-formatting.

Uses inline TYPE_CHECKING declarations for host attributes.
See: plan/rfc-mixin-protocol-typing.md
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kida.environment.core import Environment
    from kida.nodes import Node
    from kida.nodes.structure import Trans


class I18nStatementMixin:
    """Mixin for compiling {% trans %} blocks.

    Host attributes and cross-mixin dependencies are declared via inline
    TYPE_CHECKING blocks.
    """

    if TYPE_CHECKING:
        _streaming: bool
        _env: Environment

        def _compile_expr(self, node: Node, store: bool = False) -> ast.expr: ...
        def _emit_output(self, value_expr: ast.expr) -> ast.stmt: ...
        def _emit_data(self, text: str) -> ast.stmt: ...

    def _compile_trans(self, node: Trans) -> list[ast.stmt]:
        """Compile {% trans %}...{% endtrans %} to gettext/ngettext calls.

        Singular (no variables):
            _append(_escape(_gettext("Hello, world!")))

        Singular with variables:
            _append(_Markup(_gettext("Hello, %(name)s!")) % {"name": name_value})

        Plural:
            _append(_Markup(_ngettext("One item.", "%(count)s items.", count))
                    % {"count": count_value})

        HTML escaping strategy:
            1. Call gettext/ngettext with raw message ID (no escaping)
            2. Wrap result in Markup() for %-formatting
            3. Markup.__mod__ auto-escapes non-Markup variable values
            4. No-variable case: escape translated string via _escape()

        optimize_translations:
            When enabled and the identity gettext is still installed at compile
            time, constant trans blocks (no variables, no plural) are compiled
            to a pre-escaped string append, bypassing the gettext call.
        """
        # Optimization: constant trans blocks bypass gettext entirely,
        # but only when identity gettext is installed (no real translations).
        if self._env.optimize_translations and not node.variables and node.plural is None:
            from kida.environment.core import _identity_gettext

            if self._env._gettext is _identity_gettext:
                # Preserve escaping semantics: wrap in _escape() like the
                # normal no-variable path does.
                result = ast.Call(
                    func=ast.Name(id="_escape", ctx=ast.Load()),
                    args=[ast.Constant(value=node.singular)],
                    keywords=[],
                )
                return [self._emit_output(result)]

        stmts: list[ast.stmt] = []

        # Build the variable dict: {"name": compiled_expr, ...}
        var_keys: list[ast.expr | None] = []
        var_values: list[ast.expr] = []
        for tv in node.variables:
            var_keys.append(ast.Constant(value=tv.name))
            var_values.append(self._compile_expr(tv.expr))

        # gettext or ngettext call
        if node.plural is not None and node.count_expr is not None:
            # _ngettext(singular, plural, count)
            translate_call = ast.Call(
                func=ast.Name(id="_ngettext", ctx=ast.Load()),
                args=[
                    ast.Constant(value=node.singular),
                    ast.Constant(value=node.plural),
                    self._compile_expr(node.count_expr),
                ],
                keywords=[],
            )
        else:
            # _gettext(singular)
            translate_call = ast.Call(
                func=ast.Name(id="_gettext", ctx=ast.Load()),
                args=[ast.Constant(value=node.singular)],
                keywords=[],
            )

        # If there are variables, apply %-formatting with Markup
        if node.variables:
            # _Markup(translated_string) % {"name": value, ...}
            markup_wrapped = ast.Call(
                func=ast.Name(id="_Markup", ctx=ast.Load()),
                args=[translate_call],
                keywords=[],
            )
            format_dict = ast.Dict(keys=var_keys, values=var_values)
            result_expr = ast.BinOp(
                left=markup_wrapped,
                op=ast.Mod(),
                right=format_dict,
            )
        else:
            # No variables — escape the translated string directly
            result_expr = ast.Call(
                func=ast.Name(id="_escape", ctx=ast.Load()),
                args=[translate_call],
                keywords=[],
            )

        stmts.append(self._emit_output(result_expr))
        return stmts
