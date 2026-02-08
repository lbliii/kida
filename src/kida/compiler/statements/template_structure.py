"""Template structure statement compilation for Kida compiler.

Provides mixin for compiling template structure statements (block, include, from_import).

Uses inline TYPE_CHECKING declarations for host attributes.
See: plan/rfc-mixin-protocol-typing.md
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kida.nodes import Node


class TemplateStructureMixin:
    """Mixin for compiling template structure statements.

    Host attributes and cross-mixin dependencies are declared via inline
    TYPE_CHECKING blocks.

    """

    # ─────────────────────────────────────────────────────────────────────────
    # Cross-mixin dependencies (type-check only)
    # ─────────────────────────────────────────────────────────────────────────
    if TYPE_CHECKING:
        _async_mode: bool
        _streaming: bool

        # From ExpressionCompilationMixin
        def _compile_expr(self, node: Node, store: bool = False) -> ast.expr: ...

        # From Compiler core
        def _emit_output(self, value_expr: ast.expr) -> ast.stmt: ...

    def _yield_from_or_async_for(self, call_expr: ast.expr) -> list[ast.stmt]:
        """Generate yield from (sync) or async for + yield (async).

        In sync streaming mode: yield from call_expr
        In async streaming mode: async for _chunk in call_expr: yield _chunk

        Python doesn't allow yield from inside async def, so async mode
        must use async for + yield instead.
        """
        if getattr(self, "_async_mode", False):
            return [
                ast.AsyncFor(
                    target=ast.Name(id="_chunk", ctx=ast.Store()),
                    iter=call_expr,
                    body=[
                        ast.Expr(
                            value=ast.Yield(
                                value=ast.Name(id="_chunk", ctx=ast.Load()),
                            )
                        ),
                    ],
                    orelse=[],
                )
            ]
        return [ast.Expr(value=ast.YieldFrom(value=call_expr))]

    def _compile_block(self, node: Node) -> list[ast.stmt]:
        """Compile {% block name %} ... {% endblock %.

        StringBuilder: _append(_blocks.get('name', _block_name)(ctx, _blocks))
        Streaming: yield from _blocks.get('name', _block_name_stream)(ctx, _blocks)
        Async streaming: async for _chunk in _blocks.get(...): yield _chunk
        """
        block_name = node.name

        if self._streaming:
            # Determine the default block function suffix based on mode
            async_mode = getattr(self, "_async_mode", False)
            suffix = "_stream_async" if async_mode else "_stream"
            block_call = ast.Call(
                func=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="_blocks", ctx=ast.Load()),
                        attr="get",
                        ctx=ast.Load(),
                    ),
                    args=[
                        ast.Constant(value=block_name),
                        ast.Name(
                            id=f"_block_{block_name}{suffix}",
                            ctx=ast.Load(),
                        ),
                    ],
                    keywords=[],
                ),
                args=[
                    ast.Name(id="ctx", ctx=ast.Load()),
                    ast.Name(id="_blocks", ctx=ast.Load()),
                ],
                keywords=[],
            )
            return self._yield_from_or_async_for(block_call)

        # StringBuilder mode with profiling instrumentation:
        #   if _acc is not None:
        #       _t0 = _perf_counter()
        #       _append(_blocks.get('name', _block_name)(ctx, _blocks))
        #       _acc.record_block('name', (_perf_counter() - _t0) * 1000)
        #   else:
        #       _append(_blocks.get('name', _block_name)(ctx, _blocks))

        def _make_block_append() -> ast.Expr:
            """Generate _append(_blocks.get('name', _block_name)(ctx, _blocks))."""
            return ast.Expr(
                value=ast.Call(
                    func=ast.Name(id="_append", ctx=ast.Load()),
                    args=[
                        ast.Call(
                            func=ast.Call(
                                func=ast.Attribute(
                                    value=ast.Name(id="_blocks", ctx=ast.Load()),
                                    attr="get",
                                    ctx=ast.Load(),
                                ),
                                args=[
                                    ast.Constant(value=block_name),
                                    ast.Name(
                                        id=f"_block_{block_name}", ctx=ast.Load()
                                    ),
                                ],
                                keywords=[],
                            ),
                            args=[
                                ast.Name(id="ctx", ctx=ast.Load()),
                                ast.Name(id="_blocks", ctx=ast.Load()),
                            ],
                            keywords=[],
                        ),
                    ],
                    keywords=[],
                ),
            )

        return [
            ast.If(
                test=ast.Compare(
                    left=ast.Name(id="_acc", ctx=ast.Load()),
                    ops=[ast.IsNot()],
                    comparators=[ast.Constant(value=None)],
                ),
                body=[
                    # _t0 = _perf_counter()
                    ast.Assign(
                        targets=[ast.Name(id="_t0", ctx=ast.Store())],
                        value=ast.Call(
                            func=ast.Name(id="_perf_counter", ctx=ast.Load()),
                            args=[],
                            keywords=[],
                        ),
                    ),
                    _make_block_append(),
                    # _acc.record_block('name', (_perf_counter() - _t0) * 1000)
                    ast.Expr(
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id="_acc", ctx=ast.Load()),
                                attr="record_block",
                                ctx=ast.Load(),
                            ),
                            args=[
                                ast.Constant(value=block_name),
                                ast.BinOp(
                                    left=ast.BinOp(
                                        left=ast.Call(
                                            func=ast.Name(
                                                id="_perf_counter", ctx=ast.Load()
                                            ),
                                            args=[],
                                            keywords=[],
                                        ),
                                        op=ast.Sub(),
                                        right=ast.Name(id="_t0", ctx=ast.Load()),
                                    ),
                                    op=ast.Mult(),
                                    right=ast.Constant(value=1000),
                                ),
                            ],
                            keywords=[],
                        ),
                    ),
                ],
                orelse=[_make_block_append()],
            )
        ]

    def _compile_include(self, node: Node) -> list[ast.stmt]:
        """Compile {% include "template.html" [with context] %.

        StringBuilder: _append(_include(template_name, ctx))
        Streaming: yield from _include_stream(template_name, ctx)
        """
        template_expr = self._compile_expr(node.template)

        # Build args: (template_name, ctx if with_context else {}, ignore_missing)
        args: list[ast.expr] = [template_expr]

        if node.with_context:
            args.append(ast.Name(id="ctx", ctx=ast.Load()))
        else:
            args.append(ast.Dict(keys=[], values=[]))

        args.append(ast.Constant(value=node.ignore_missing))

        if self._streaming:
            # Async mode: async for _chunk in _include_stream_async(...)
            # Sync mode: yield from _include_stream(...)
            async_mode = getattr(self, "_async_mode", False)
            func_name = "_include_stream_async" if async_mode else "_include_stream"
            include_call = ast.Call(
                func=ast.Name(id=func_name, ctx=ast.Load()),
                args=args,
                keywords=[],
            )
            return self._yield_from_or_async_for(include_call)

        # _append(_include(template_name, ctx, ignore_missing))
        include_call = ast.Call(
            func=ast.Name(id="_include", ctx=ast.Load()),
            args=args,
            keywords=[],
        )
        return [
            ast.Expr(
                value=ast.Call(
                    func=ast.Name(id="_append", ctx=ast.Load()),
                    args=[include_call],
                    keywords=[],
                ),
            )
        ]

    def _compile_from_import(self, node: Node) -> list[ast.stmt]:
        """Compile {% from "template.html" import name1, name2 as alias %.

        Generates:
            _imported = _import_macros(template_name, with_context, ctx)
            ctx['name1'] = _imported['name1']
            ctx['alias'] = _imported['name2']
        """
        template_expr = self._compile_expr(node.template)

        stmts: list[ast.stmt] = []

        # _imported = _import_macros(template_name, with_context, ctx)
        stmts.append(
            ast.Assign(
                targets=[ast.Name(id="_imported", ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Name(id="_import_macros", ctx=ast.Load()),
                    args=[
                        template_expr,
                        ast.Constant(value=node.with_context),
                        ast.Name(id="ctx", ctx=ast.Load()),
                    ],
                    keywords=[],
                ),
            )
        )

        # ctx['name'] = _imported['name'] for each imported name
        for name, alias in node.names:
            target_name = alias if alias else name
            stmts.append(
                ast.Assign(
                    targets=[
                        ast.Subscript(
                            value=ast.Name(id="ctx", ctx=ast.Load()),
                            slice=ast.Constant(value=target_name),
                            ctx=ast.Store(),
                        )
                    ],
                    value=ast.Subscript(
                        value=ast.Name(id="_imported", ctx=ast.Load()),
                        slice=ast.Constant(value=name),
                        ctx=ast.Load(),
                    ),
                )
            )

        return stmts

    def _compile_import(self, node: Node) -> list[ast.stmt]:
        """Compile {% import "template.html" as f %.

        Generates: ctx['f'] = _import_macros(template_name, with_context, ctx)
        """
        template_expr = self._compile_expr(node.template)

        return [
            ast.Assign(
                targets=[
                    ast.Subscript(
                        value=ast.Name(id="ctx", ctx=ast.Load()),
                        slice=ast.Constant(value=node.target),
                        ctx=ast.Store(),
                    )
                ],
                value=ast.Call(
                    func=ast.Name(id="_import_macros", ctx=ast.Load()),
                    args=[
                        template_expr,
                        ast.Constant(value=node.with_context),
                        ast.Name(id="ctx", ctx=ast.Load()),
                    ],
                    keywords=[],
                ),
            )
        ]
