"""Message extraction for i18n support.

Walks the AST and collects translatable strings from ``Trans`` nodes
and ``_()`` / ``_n()`` function calls.  Outputs structured messages
suitable for PO template generation or Babel integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from kida.analysis.node_visitor import NodeVisitor

if TYPE_CHECKING:
    from kida.nodes import FuncCall, Node, Trans


@dataclass(frozen=True, slots=True)
class ExtractedMessage:
    """A translatable message extracted from a template."""

    filename: str
    lineno: int
    function: str  # "gettext" or "ngettext"
    message: str | tuple[str, str]  # singular or (singular, plural)
    comments: tuple[str, ...] = ()


class ExtractMessagesVisitor(NodeVisitor):
    """Walk AST and collect translatable messages.

    Collects messages from:

    - ``Trans`` nodes (``{% trans %}...{% endtrans %}``)
    - ``FuncCall`` nodes calling ``_()`` or ``_n()``
    """

    def __init__(self, filename: str = "<template>") -> None:
        self._filename = filename
        self._messages: list[ExtractedMessage] = []

    def extract(self, node: Node) -> list[ExtractedMessage]:
        """Extract all translatable messages from an AST."""
        self._messages = []
        self.visit(node)
        return list(self._messages)

    def visit_Trans(self, node: Trans) -> None:  # noqa: N802
        """Extract message from ``{% trans %}`` block."""
        if node.plural is not None:
            self._messages.append(
                ExtractedMessage(
                    filename=self._filename,
                    lineno=node.lineno,
                    function="ngettext",
                    message=(node.singular, node.plural),
                )
            )
        else:
            self._messages.append(
                ExtractedMessage(
                    filename=self._filename,
                    lineno=node.lineno,
                    function="gettext",
                    message=node.singular,
                )
            )

    def visit_FuncCall(self, node: FuncCall) -> None:  # noqa: N802
        """Extract message from ``_("literal")`` or ``_n("s", "p", n)`` calls."""
        from kida.nodes import Const, Name

        if not isinstance(node.func, Name):
            self.generic_visit(node)
            return

        if node.func.name == "_" and len(node.args) == 1:
            arg = node.args[0]
            if isinstance(arg, Const) and isinstance(arg.value, str):
                self._messages.append(
                    ExtractedMessage(
                        filename=self._filename,
                        lineno=node.lineno,
                        function="gettext",
                        message=arg.value,
                    )
                )

        elif node.func.name == "_n" and len(node.args) >= 3:
            singular_arg = node.args[0]
            plural_arg = node.args[1]
            if (
                isinstance(singular_arg, Const)
                and isinstance(singular_arg.value, str)
                and isinstance(plural_arg, Const)
                and isinstance(plural_arg.value, str)
            ):
                self._messages.append(
                    ExtractedMessage(
                        filename=self._filename,
                        lineno=node.lineno,
                        function="ngettext",
                        message=(singular_arg.value, plural_arg.value),
                    )
                )

        self.generic_visit(node)
