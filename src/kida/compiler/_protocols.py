"""Type protocols for Kida compiler.

Provides minimal type contracts for compiler mixins to enable
type-safe mixin patterns without exposing implementation details.

See: plan/rfc-mixin-protocol-typing.md
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from kida.environment import Environment


class CompilerCoreProtocol(Protocol):
    """Minimal contract for cross-mixin dependencies in compiler.

    Contains ONLY:
    1. Host class attributes (defined in Compiler.__init__)
    2. Core compilation methods (used by all compilation mixins)
    3. Operator utilities (used by expression compilation)

    Individual mixin methods are NOT included—mixins declare
    their own methods via inline TYPE_CHECKING declarations.
    """

    # ─────────────────────────────────────────────────────────────
    # Host Attributes (from Compiler.__init__)
    # ─────────────────────────────────────────────────────────────
    _env: Environment
    _name: str | None
    _filename: str | None
    _locals: set[str]
    _blocks: dict[str, Any]
    _block_counter: int

    # ─────────────────────────────────────────────────────────────
    # Core Compilation Methods
    # ─────────────────────────────────────────────────────────────
    def _compile_expr(self, node: Any, store: bool = False) -> ast.expr:
        """Compile expression node to Python AST expression."""
        ...

    def _compile_node(self, node: Any) -> list[ast.stmt]:
        """Compile a single AST node to Python statements."""
        ...

    # ─────────────────────────────────────────────────────────────
    # Operator Utilities (from OperatorUtilsMixin)
    # ─────────────────────────────────────────────────────────────
    def _get_binop(self, op: str) -> ast.operator:
        """Map operator string to AST operator."""
        ...

    def _get_unaryop(self, op: str) -> ast.unaryop:
        """Map unary operator string to AST operator."""
        ...

    def _get_cmpop(self, op: str) -> ast.cmpop:
        """Map comparison operator string to AST operator."""
        ...

