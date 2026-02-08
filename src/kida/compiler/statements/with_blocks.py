"""With-block statement compilation for Kida compiler.

Provides mixin for compiling with/endwith statements including both the
simple form ({% with var=expr %}) and the conditional form ({% with expr as target %}).

Extracted from special_blocks.py for module focus (RFC: compiler decomposition).
Uses inline TYPE_CHECKING declarations for host attributes.
See: plan/rfc-mixin-protocol-typing.md
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kida.nodes import Node, With, WithConditional


class WithBlockMixin:
    """Mixin for compiling with-block statements.

    Host attributes and cross-mixin dependencies are declared via inline
    TYPE_CHECKING blocks.
    """

    # ─────────────────────────────────────────────────────────────────────────
    # Host attributes and cross-mixin dependencies (type-check only)
    # ─────────────────────────────────────────────────────────────────────────
    if TYPE_CHECKING:
        # Host attributes (from Compiler.__init__)
        _block_counter: int

        # From ExpressionCompilationMixin
        def _compile_expr(self, node: Node, store: bool = False) -> ast.expr: ...

        # From Compiler core
        def _compile_node(self, node: Node) -> list[ast.stmt]: ...

        # From ControlFlowMixin
        def _extract_names(self, node: Node) -> list[str]: ...

    def _compile_with(self, node: With) -> list[ast.stmt]:
        """Compile {% with var=value, ... %}...{% endwith %.

        Creates temporary variable bindings scoped to the with block.
        We store old values and restore them after the block.
        """
        stmts: list[ast.stmt] = []

        # Save old values and set new ones
        old_var_names = []
        for name, value in node.targets:
            old_var_name = f"_with_save_{name}"
            old_var_names.append((name, old_var_name))

            # _with_save_name = ctx.get('name')
            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id=old_var_name, ctx=ast.Store())],
                    value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id="ctx", ctx=ast.Load()),
                            attr="get",
                            ctx=ast.Load(),
                        ),
                        args=[ast.Constant(value=name)],
                        keywords=[],
                    ),
                )
            )

            # ctx['name'] = value
            stmts.append(
                ast.Assign(
                    targets=[
                        ast.Subscript(
                            value=ast.Name(id="ctx", ctx=ast.Load()),
                            slice=ast.Constant(value=name),
                            ctx=ast.Store(),
                        )
                    ],
                    value=self._compile_expr(value),
                )
            )

        # Compile body
        for child in node.body:
            stmts.extend(self._compile_node(child))

        # Restore old values
        for name, old_var_name in old_var_names:
            # if _with_save_name is None: del ctx['name']
            # else: ctx['name'] = _with_save_name
            stmts.append(
                ast.If(
                    test=ast.Compare(
                        left=ast.Name(id=old_var_name, ctx=ast.Load()),
                        ops=[ast.Is()],
                        comparators=[ast.Constant(value=None)],
                    ),
                    body=[
                        ast.Delete(
                            targets=[
                                ast.Subscript(
                                    value=ast.Name(id="ctx", ctx=ast.Load()),
                                    slice=ast.Constant(value=name),
                                    ctx=ast.Del(),
                                )
                            ]
                        )
                    ],
                    orelse=[
                        ast.Assign(
                            targets=[
                                ast.Subscript(
                                    value=ast.Name(id="ctx", ctx=ast.Load()),
                                    slice=ast.Constant(value=name),
                                    ctx=ast.Store(),
                                )
                            ],
                            value=ast.Name(id=old_var_name, ctx=ast.Load()),
                        )
                    ],
                )
            )

        return stmts

    def _compile_with_conditional(self, node: WithConditional) -> list[ast.stmt]:
        """Compile {% with expr as target %}...{% end %} (conditional form).

        Renders body only if expr is truthy. Binds expr result to target.
        Supports multiple bindings and structural unpacking.
        Provides nil-resilience: block is silently skipped when expr is falsy.

        Generates:
            _with_val_N = expr
            if _with_val_N:
                # [save old values]
                # [bind new values]
                ... body ...
                # [restore old values]
        """
        # Get unique suffix for this block
        self._block_counter += 1
        suffix = str(self._block_counter)
        val_name = f"_with_val_{suffix}"

        stmts: list[ast.stmt] = []

        # _with_val_N = expr
        stmts.append(
            ast.Assign(
                targets=[ast.Name(id=val_name, ctx=ast.Store())],
                value=self._compile_expr(node.expr),
            )
        )

        # Build the if body
        if_body: list[ast.stmt] = []

        # Use pattern matching logic for bindings
        # This handles both single names and tuples/unpacking
        from kida.nodes import Name as KidaName
        from kida.nodes import Tuple as KidaTuple

        # 1. Determine truthy check
        # If it's a tuple, we might want to check if all elements are truthy
        # for nil-resilience. But for now, let's stick to Python truthiness
        # of the whole expression result.
        test = ast.Name(id=val_name, ctx=ast.Load())

        # If it's an implicit tuple from multiple 'with' subjects,
        # we check if all elements are truthy for better nil-resilience.
        if isinstance(node.expr, KidaTuple):
            # val_N[0] and val_N[1] and ...
            truth_checks = [
                ast.Subscript(
                    value=ast.Name(id=val_name, ctx=ast.Load()),
                    slice=ast.Constant(value=i),
                    ctx=ast.Load(),
                )
                for i in range(len(node.expr.items))
            ]
            if len(truth_checks) > 1:
                test = ast.BoolOp(op=ast.And(), values=truth_checks)
            elif truth_checks:
                test = truth_checks[0]

        # 2. Track names and handle bindings
        bound_names = self._extract_names(node.target)
        save_restore_stmts: list[tuple[str, str]] = []

        for name in bound_names:
            old_var_name = f"_with_save_{name}_{suffix}"
            save_restore_stmts.append((name, old_var_name))

            # _with_save_name_N = ctx.get('name')
            if_body.append(
                ast.Assign(
                    targets=[ast.Name(id=old_var_name, ctx=ast.Store())],
                    value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id="ctx", ctx=ast.Load()),
                            attr="get",
                            ctx=ast.Load(),
                        ),
                        args=[ast.Constant(value=name)],
                        keywords=[],
                    ),
                )
            )

        # 3. Bind new values
        if isinstance(node.target, KidaName):
            # ctx['name'] = _with_val_N
            if_body.append(
                ast.Assign(
                    targets=[
                        ast.Subscript(
                            value=ast.Name(id="ctx", ctx=ast.Load()),
                            slice=ast.Constant(value=node.target.name),
                            ctx=ast.Store(),
                        )
                    ],
                    value=ast.Name(id=val_name, ctx=ast.Load()),
                )
            )
        elif isinstance(node.target, KidaTuple):
            # Unpack: ctx['x'], (ctx['y'], ctx['z']) = _with_val_N
            # We need to generate a target expression that maps to ctx subscripts
            def _gen_store_target(t: Node) -> ast.expr:
                if isinstance(t, KidaName):
                    return ast.Subscript(
                        value=ast.Name(id="ctx", ctx=ast.Load()),
                        slice=ast.Constant(value=t.name),
                        ctx=ast.Store(),
                    )
                elif isinstance(t, KidaTuple):
                    return ast.Tuple(
                        elts=[_gen_store_target(item) for item in t.items],
                        ctx=ast.Store(),
                    )
                return ast.Constant(value=None)  # Should not happen

            target_ast = _gen_store_target(node.target)
            if target_ast:
                if_body.append(
                    ast.Assign(
                        targets=[target_ast],
                        value=ast.Name(id=val_name, ctx=ast.Load()),
                    )
                )

        # 4. Compile body
        for child in node.body:
            if_body.extend(self._compile_node(child))

        # 5. Restore old values
        for name, old_var_name in reversed(save_restore_stmts):
            # if _with_save_name_N is None: del ctx['name']
            # else: ctx['name'] = _with_save_name_N
            if_body.append(
                ast.If(
                    test=ast.Compare(
                        left=ast.Name(id=old_var_name, ctx=ast.Load()),
                        ops=[ast.Is()],
                        comparators=[ast.Constant(value=None)],
                    ),
                    body=[
                        ast.Delete(
                            targets=[
                                ast.Subscript(
                                    value=ast.Name(id="ctx", ctx=ast.Load()),
                                    slice=ast.Constant(value=name),
                                    ctx=ast.Del(),
                                )
                            ]
                        )
                    ],
                    orelse=[
                        ast.Assign(
                            targets=[
                                ast.Subscript(
                                    value=ast.Name(id="ctx", ctx=ast.Load()),
                                    slice=ast.Constant(value=name),
                                    ctx=ast.Store(),
                                )
                            ],
                            value=ast.Name(id=old_var_name, ctx=ast.Load()),
                        )
                    ],
                )
            )

        # 6. Compile empty block
        orelse = []
        if node.empty:
            for child in node.empty:
                orelse.extend(self._compile_node(child))

        # 7. Build final If node
        stmts.append(
            ast.If(
                test=test,
                body=if_body,
                orelse=orelse,
            )
        )

        return stmts
