"""Statement compilation for Kida compiler.

Provides mixins for compiling Kida statement AST nodes to Python AST statements.

The statements package is organized into logical modules:
- basic: Basic output (data, output)
- control_flow: Control flow (if, for, while, break, continue)
- pattern_matching: Match/case structural pattern matching
- variables: Variable assignments (set, let, export)
- template_structure: Template structure (block, include, from_import)
- functions: Functions/macros (macro, def, call_block, slot)
- with_blocks: With-block scoped variable bindings
- caching: Cache blocks and filter blocks
- special_blocks: Remaining special blocks (raw, capture, spaceless, embed)

Uses inline TYPE_CHECKING declarations for host attributes.
See: plan/rfc-mixin-protocol-typing.md

"""

from __future__ import annotations

from kida.compiler.statements.basic import BasicStatementMixin
from kida.compiler.statements.caching import CachingMixin
from kida.compiler.statements.control_flow import ControlFlowMixin
from kida.compiler.statements.functions import FunctionCompilationMixin
from kida.compiler.statements.pattern_matching import PatternMatchingMixin
from kida.compiler.statements.special_blocks import SpecialBlockMixin
from kida.compiler.statements.template_structure import TemplateStructureMixin
from kida.compiler.statements.variables import VariableAssignmentMixin
from kida.compiler.statements.with_blocks import WithBlockMixin


class StatementCompilationMixin(
    BasicStatementMixin,
    ControlFlowMixin,
    PatternMatchingMixin,
    VariableAssignmentMixin,
    TemplateStructureMixin,
    FunctionCompilationMixin,
    WithBlockMixin,
    CachingMixin,
    SpecialBlockMixin,
):
    """Combined mixin for compiling all statement types.

    This class combines all statement compilation mixins into a single
    interface that can be inherited by the Compiler class.

    Host attributes and cross-mixin dependencies are declared via inline
    TYPE_CHECKING blocks in each individual mixin.

    """
