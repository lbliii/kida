"""Variable assignment statement compilation for Kida compiler.

Provides mixin for compiling variable assignment statements (set, let, export).

Uses inline TYPE_CHECKING declarations for host attributes.
See: plan/rfc-mixin-protocol-typing.md
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kida.nodes import Export, Let, Node, Set


def _collect_target_names(target: Node) -> list[str]:
    """Walk a Set/Let/Export target node, returning all bound names."""
    from kida.nodes import Name as KidaName
    from kida.nodes import Tuple as KidaTuple

    names: list[str] = []
    if isinstance(target, KidaName):
        names.append(target.name)
    elif isinstance(target, KidaTuple):
        for item in target.items:
            names.extend(_collect_target_names(item))
    return names


class VariableAssignmentMixin:
    """Mixin for compiling variable assignment statements.

    Host attributes and cross-mixin dependencies are declared via inline
    TYPE_CHECKING blocks.

    """

    # ─────────────────────────────────────────────────────────────────────────
    # Host attributes and cross-mixin dependencies (type-check only)
    # ─────────────────────────────────────────────────────────────────────────
    if TYPE_CHECKING:
        # Host attributes (from Compiler.__init__)
        _block_counter: int
        _template_scope_names: set[str]

        # From ExpressionCompilationMixin
        def _compile_expr(self, node: Node, store: bool = False) -> ast.expr: ...

    def _compile_set(self, node: Set) -> list[ast.stmt]:
        """Compile {% set %} - block-scoped variable assignment.

        Variables assigned with {% set %} are scoped to the current block
        (if/for/while/etc.) and are not accessible outside the block.

        Handles both single names and structural unpacking:
            {% set x = value %}
            {% set a, b = 1, 2 %}
            {% set (a, b), c = ([1, 2], 3) %}

        With ??=, assigns only if the variable is undefined or None:
            {% set x ??= "default" %}
        """
        if self._scope_depth > 0 and self._env.jinja2_compat_warnings:
            # Narrow to the actual Jinja2 trap: a nested {% set %} that
            # shadows a name already bound template-wide via {% let %} or
            # {% export %}. Fresh names used for genuine block-scoped
            # purposes don't trigger — the two engines behave identically
            # there, so there's nothing to warn about.
            shadowed = [
                n for n in _collect_target_names(node.target) if n in self._template_scope_names
            ]
            if shadowed:
                from kida.exceptions import ErrorCode

                name = shadowed[0]
                self._emit_warning(
                    ErrorCode.JINJA2_SET_SCOPING,
                    f"{{% set %}} assigns to '{name}' which is already bound "
                    f"by {{% let %}} or {{% export %}}. In Kida, this creates "
                    f"a block-scoped shadow that does not leak to outer scope. "
                    f"In Jinja2, {{% set %}} would modify the outer variable.",
                    lineno=node.lineno,
                    suggestion=f"Use {{% export {name} = ... %}} to write to outer scope.",
                )
        stmts = self._compile_block_scoped_assignment(node.target, node.value)
        if node.coalesce:
            return self._wrap_coalesce_guard(node.target, stmts)
        return stmts

    def _compile_let(self, node: Let) -> list[ast.stmt]:
        """Compile {% let %} - template-scoped variable assignment.

        Variables assigned with {% let %} are available throughout the template.
        Supports structural unpacking: {% let a, b = 1, 2 %}

        With ??=, assigns only if the variable is undefined or None:
            {% let x ??= "default" %}
        """
        # Record the name(s) as template-scope-bound so nested {% set %}
        # can detect the Jinja2 shadowing trap.
        self._template_scope_names.update(_collect_target_names(node.name))
        stmts = self._compile_assignment(node.name, node.value)
        if node.coalesce:
            return self._wrap_coalesce_guard(node.name, stmts)
        return stmts

    def _compile_export(self, node: Export) -> list[ast.stmt]:
        """Compile {% export %} - export variable to outer scope.

        Variables assigned with {% export %} are promoted from inner scope
        (e.g., inside a loop) to the outer scope (e.g., outside the loop).

        Supports structural unpacking: {% export a, b = 1, 2 %}

        With ??=, exports only if the variable is undefined or None:
            {% export x ??= "default" %}
        """
        # Record the name(s) as template-scope-bound for trap detection.
        self._template_scope_names.update(_collect_target_names(node.name))
        stmts = self._compile_export_assignment(node.name, node.value)
        if node.coalesce:
            return self._wrap_coalesce_guard(node.name, stmts)
        return stmts

    def _wrap_coalesce_guard(self, target: Node, stmts: list[ast.stmt]) -> list[ast.stmt]:
        """Wrap assignment statements with a nullish coalesce guard.

        Uses _is_defined(lambda: _lookup_scope(ctx, _scope_stack, name)) to match
        kida's scope-aware variable resolution semantics. This correctly handles:
        - Variables defined in block scopes (_scope_stack)
        - Variables defined in template scope (ctx)
        - Truly undefined variables (raises UndefinedError, caught by _is_defined)
        - Explicit None values
        """
        from kida.nodes import Name as KidaName

        if isinstance(target, KidaName):
            # if not _is_defined(lambda: _lookup_scope(ctx, _scope_stack, name)): <assign>
            lookup_call = ast.Call(
                func=ast.Name(id="_lookup_scope", ctx=ast.Load()),
                args=[
                    ast.Name(id="ctx", ctx=ast.Load()),
                    ast.Name(id="_scope_stack", ctx=ast.Load()),
                    ast.Constant(value=target.name),
                ],
                keywords=[],
            )
            return [
                ast.If(
                    test=ast.UnaryOp(
                        op=ast.Not(),
                        operand=ast.Call(
                            func=ast.Name(id="_is_defined", ctx=ast.Load()),
                            args=[self._make_deferred_lambda(lookup_call)],
                            keywords=[],
                        ),
                    ),
                    body=stmts,
                    orelse=[],
                )
            ]
        # For tuple unpacking with ??=, disallowed at parse time
        return stmts

    def _compile_block_scoped_assignment(self, target: Node, value: Node) -> list[ast.stmt]:
        """Compile block-scoped assignment ({% set %}).

        Assigns to current scope: _scope_stack[-1][name] = value
        If no scope exists (top level), falls back to ctx (template-scoped).
        """
        from kida.nodes import Name as KidaName
        from kida.nodes import Tuple as KidaTuple

        compiled_value = self._compile_expr(value)

        if isinstance(target, KidaName):
            # Block-scoped: _scope_stack[-1][name] = value (if scope exists)
            # Fallback to ctx if no scope (top-level set)
            return [
                ast.If(
                    test=ast.Compare(
                        left=ast.Call(
                            func=ast.Name(id="_len", ctx=ast.Load()),
                            args=[ast.Name(id="_scope_stack", ctx=ast.Load())],
                            keywords=[],
                        ),
                        ops=[ast.Gt()],
                        comparators=[ast.Constant(value=0)],
                    ),
                    body=[
                        # _scope_stack[-1][name] = value
                        ast.Assign(
                            targets=[
                                ast.Subscript(
                                    value=ast.Subscript(
                                        value=ast.Name(id="_scope_stack", ctx=ast.Load()),
                                        slice=ast.UnaryOp(
                                            op=ast.USub(),
                                            operand=ast.Constant(value=1),
                                        ),
                                        ctx=ast.Load(),
                                    ),
                                    slice=ast.Constant(value=target.name),
                                    ctx=ast.Store(),
                                )
                            ],
                            value=compiled_value,
                        )
                    ],
                    orelse=[
                        # ctx[name] = value (fallback for top-level)
                        ast.Assign(
                            targets=[
                                ast.Subscript(
                                    value=ast.Name(id="ctx", ctx=ast.Load()),
                                    slice=ast.Constant(value=target.name),
                                    ctx=ast.Store(),
                                )
                            ],
                            value=compiled_value,
                        )
                    ],
                )
            ]
        elif isinstance(target, KidaTuple):
            # Structural unpacking for block-scoped variables
            self._block_counter += 1
            tmp_name = f"_unpack_tmp_{self._block_counter}"

            stmts: list[ast.stmt] = [
                ast.Assign(
                    targets=[ast.Name(id=tmp_name, ctx=ast.Store())],
                    value=compiled_value,
                )
            ]

            def _gen_unpack(
                current_target: Node, current_val_ast: ast.expr, is_block_scoped: bool = True
            ) -> list[ast.stmt]:
                inner_stmts = []
                if isinstance(current_target, KidaName):
                    if is_block_scoped:
                        # Block-scoped unpacking
                        inner_stmts.append(
                            ast.If(
                                test=ast.Compare(
                                    left=ast.Call(
                                        func=ast.Name(id="_len", ctx=ast.Load()),
                                        args=[ast.Name(id="_scope_stack", ctx=ast.Load())],
                                        keywords=[],
                                    ),
                                    ops=[ast.Gt()],
                                    comparators=[ast.Constant(value=0)],
                                ),
                                body=[
                                    ast.Assign(
                                        targets=[
                                            ast.Subscript(
                                                value=ast.Subscript(
                                                    value=ast.Name(
                                                        id="_scope_stack", ctx=ast.Load()
                                                    ),
                                                    slice=ast.UnaryOp(
                                                        op=ast.USub(),
                                                        operand=ast.Constant(value=1),
                                                    ),
                                                    ctx=ast.Load(),
                                                ),
                                                slice=ast.Constant(value=current_target.name),
                                                ctx=ast.Store(),
                                            )
                                        ],
                                        value=current_val_ast,
                                    )
                                ],
                                orelse=[
                                    ast.Assign(
                                        targets=[
                                            ast.Subscript(
                                                value=ast.Name(id="ctx", ctx=ast.Load()),
                                                slice=ast.Constant(value=current_target.name),
                                                ctx=ast.Store(),
                                            )
                                        ],
                                        value=current_val_ast,
                                    )
                                ],
                            )
                        )
                    else:
                        # Template-scoped unpacking
                        inner_stmts.append(
                            ast.Assign(
                                targets=[
                                    ast.Subscript(
                                        value=ast.Name(id="ctx", ctx=ast.Load()),
                                        slice=ast.Constant(value=current_target.name),
                                        ctx=ast.Store(),
                                    )
                                ],
                                value=current_val_ast,
                            )
                        )
                elif isinstance(current_target, KidaTuple):
                    for i, item in enumerate(current_target.items):
                        sub_val = ast.Subscript(
                            value=current_val_ast,
                            slice=ast.Constant(value=i),
                            ctx=ast.Load(),
                        )
                        inner_stmts.extend(_gen_unpack(item, sub_val, is_block_scoped))
                return inner_stmts

            stmts.extend(
                _gen_unpack(target, ast.Name(id=tmp_name, ctx=ast.Load()), is_block_scoped=True)
            )
            return stmts
        else:
            # Fallback
            return [
                ast.Assign(
                    targets=[
                        ast.Subscript(
                            value=ast.Name(id="ctx", ctx=ast.Load()),
                            slice=ast.Constant(value=str(target)),
                            ctx=ast.Store(),
                        )
                    ],
                    value=compiled_value,
                )
            ]

    def _compile_export_assignment(self, target: Node, value: Node) -> list[ast.stmt]:
        """Compile export assignment ({% export %}).

        Export always assigns to ctx (template scope) to ensure the variable
        persists after blocks end. This matches the common use case of
        promoting values from loops/conditionals to template scope.
        """
        from kida.nodes import Name as KidaName
        from kida.nodes import Tuple as KidaTuple

        compiled_value = self._compile_expr(value)

        if isinstance(target, KidaName):
            # Export always goes to ctx (template scope) for persistence
            return [
                ast.Assign(
                    targets=[
                        ast.Subscript(
                            value=ast.Name(id="ctx", ctx=ast.Load()),
                            slice=ast.Constant(value=target.name),
                            ctx=ast.Store(),
                        )
                    ],
                    value=compiled_value,
                )
            ]
        elif isinstance(target, KidaTuple):
            # Structural unpacking for export
            self._block_counter += 1
            tmp_name = f"_unpack_tmp_{self._block_counter}"

            stmts: list[ast.stmt] = [
                ast.Assign(
                    targets=[ast.Name(id=tmp_name, ctx=ast.Store())],
                    value=compiled_value,
                )
            ]

            def _gen_unpack(current_target: Node, current_val_ast: ast.expr) -> list[ast.stmt]:
                inner_stmts = []
                if isinstance(current_target, KidaName):
                    # Export unpacking - always assign to ctx (template scope)
                    inner_stmts.append(
                        ast.Assign(
                            targets=[
                                ast.Subscript(
                                    value=ast.Name(id="ctx", ctx=ast.Load()),
                                    slice=ast.Constant(value=current_target.name),
                                    ctx=ast.Store(),
                                )
                            ],
                            value=current_val_ast,
                        )
                    )
                elif isinstance(current_target, KidaTuple):
                    for i, item in enumerate(current_target.items):
                        sub_val = ast.Subscript(
                            value=current_val_ast,
                            slice=ast.Constant(value=i),
                            ctx=ast.Load(),
                        )
                        inner_stmts.extend(_gen_unpack(item, sub_val))
                return inner_stmts

            stmts.extend(_gen_unpack(target, ast.Name(id=tmp_name, ctx=ast.Load())))
            return stmts
        else:
            # Fallback
            return [
                ast.Assign(
                    targets=[
                        ast.Subscript(
                            value=ast.Name(id="ctx", ctx=ast.Load()),
                            slice=ast.Constant(value=str(target)),
                            ctx=ast.Store(),
                        )
                    ],
                    value=compiled_value,
                )
            ]

    def _compile_assignment(self, target: Node, value: Node) -> list[ast.stmt]:
        """Common logic for template-scoped assignments ({% let %}).

        Handles recursive structural unpacking using ctx dict for all variables.
        """
        from kida.nodes import Name as KidaName
        from kida.nodes import Tuple as KidaTuple

        compiled_value = self._compile_expr(value)

        if isinstance(target, KidaName):
            # Single variable: ctx['name'] = value
            return [
                ast.Assign(
                    targets=[
                        ast.Subscript(
                            value=ast.Name(id="ctx", ctx=ast.Load()),
                            slice=ast.Constant(value=target.name),
                            ctx=ast.Store(),
                        )
                    ],
                    value=compiled_value,
                )
            ]
        elif isinstance(target, KidaTuple):
            # Structural unpacking:
            # _unpack_tmp_N = value
            # _compile_unpacking(_unpack_tmp_N, target)
            self._block_counter += 1
            tmp_name = f"_unpack_tmp_{self._block_counter}"

            stmts: list[ast.stmt] = [
                ast.Assign(
                    targets=[ast.Name(id=tmp_name, ctx=ast.Store())],
                    value=compiled_value,
                )
            ]

            def _gen_unpack(current_target: Node, current_val_ast: ast.expr) -> list[ast.stmt]:
                inner_stmts = []
                if isinstance(current_target, KidaName):
                    inner_stmts.append(
                        ast.Assign(
                            targets=[
                                ast.Subscript(
                                    value=ast.Name(id="ctx", ctx=ast.Load()),
                                    slice=ast.Constant(value=current_target.name),
                                    ctx=ast.Store(),
                                )
                            ],
                            value=current_val_ast,
                        )
                    )
                elif isinstance(current_target, KidaTuple):
                    for i, item in enumerate(current_target.items):
                        sub_val = ast.Subscript(
                            value=current_val_ast,
                            slice=ast.Constant(value=i),
                            ctx=ast.Load(),
                        )
                        inner_stmts.extend(_gen_unpack(item, sub_val))
                return inner_stmts

            stmts.extend(_gen_unpack(target, ast.Name(id=tmp_name, ctx=ast.Load())))
            return stmts
        else:
            # Fallback
            return [
                ast.Assign(
                    targets=[
                        ast.Subscript(
                            value=ast.Name(id="ctx", ctx=ast.Load()),
                            slice=ast.Constant(value=str(target)),
                            ctx=ast.Store(),
                        )
                    ],
                    value=compiled_value,
                )
            ]
