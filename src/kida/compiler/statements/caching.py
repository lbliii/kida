"""Caching and filter-block statement compilation for Kida compiler.

Provides mixin for compiling cache blocks and filter blocks -- both
follow the "capture output, transform, emit" pattern.

Extracted from special_blocks.py for module focus (RFC: compiler decomposition).
Uses inline TYPE_CHECKING declarations for host attributes.
See: plan/rfc-mixin-protocol-typing.md
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kida.nodes import Cache, FilterBlock, Node


class CachingMixin:
    """Mixin for compiling cache and filter-block statements.

    Host attributes and cross-mixin dependencies are declared via inline
    TYPE_CHECKING blocks.
    """

    # ─────────────────────────────────────────────────────────────────────────
    # Host attributes and cross-mixin dependencies (type-check only)
    # ─────────────────────────────────────────────────────────────────────────
    if TYPE_CHECKING:
        # Host attributes (from Compiler.__init__)
        _block_counter: int
        _streaming: bool

        # From ExpressionCompilationMixin
        def _compile_expr(self, node: Node, store: bool = False) -> ast.expr: ...

        # From Compiler core
        def _compile_node(self, node: Node) -> list[ast.stmt]: ...
        def _emit_output(self, value_expr: ast.expr) -> ast.stmt: ...

    def _compile_cache(self, node: Cache) -> list[ast.stmt]:
        """Compile {% cache key %}...{% endcache %.

        Fragment caching. In streaming mode: collect into buffer, cache,
        then yield. Body always uses StringBuilder mode for caching.
        """
        stmts: list[ast.stmt] = []

        # _cache_key = str(key)
        stmts.append(
            ast.Assign(
                targets=[ast.Name(id="_cache_key", ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Name(id="_str", ctx=ast.Load()),
                    args=[self._compile_expr(node.key)],
                    keywords=[],
                ),
            )
        )

        # _cached = _cache_get(_cache_key)
        stmts.append(
            ast.Assign(
                targets=[ast.Name(id="_cached", ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Name(id="_cache_get", ctx=ast.Load()),
                    args=[ast.Name(id="_cache_key", ctx=ast.Load())],
                    keywords=[],
                ),
            )
        )

        # Build the else block (cache miss)
        else_body: list[ast.stmt] = [
            ast.Assign(
                targets=[ast.Name(id="_cache_buf", ctx=ast.Store())],
                value=ast.List(elts=[], ctx=ast.Load()),
            ),
            ast.Assign(
                targets=[ast.Name(id="_cache_append", ctx=ast.Store())],
                value=ast.Attribute(
                    value=ast.Name(id="_cache_buf", ctx=ast.Load()),
                    attr="append",
                    ctx=ast.Load(),
                ),
            ),
        ]

        if self._streaming:
            # In streaming mode: define _append locally, no save/restore
            else_body.append(
                ast.Assign(
                    targets=[ast.Name(id="_append", ctx=ast.Store())],
                    value=ast.Name(id="_cache_append", ctx=ast.Load()),
                )
            )
            self._streaming = False
            for child in node.body:
                else_body.extend(self._compile_node(child))
            self._streaming = True
        else:
            else_body.append(
                ast.Assign(
                    targets=[ast.Name(id="_save_append", ctx=ast.Store())],
                    value=ast.Name(id="_append", ctx=ast.Load()),
                )
            )
            else_body.append(
                ast.Assign(
                    targets=[ast.Name(id="_append", ctx=ast.Store())],
                    value=ast.Name(id="_cache_append", ctx=ast.Load()),
                )
            )
            for child in node.body:
                else_body.extend(self._compile_node(child))
            else_body.append(
                ast.Assign(
                    targets=[ast.Name(id="_append", ctx=ast.Store())],
                    value=ast.Name(id="_save_append", ctx=ast.Load()),
                )
            )

        # _cached = ''.join(_cache_buf)
        else_body.append(
            ast.Assign(
                targets=[ast.Name(id="_cached", ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Constant(value=""),
                        attr="join",
                        ctx=ast.Load(),
                    ),
                    args=[ast.Name(id="_cache_buf", ctx=ast.Load())],
                    keywords=[],
                ),
            )
        )

        # _cache_set(_cache_key, _cached, ttl)
        cache_set_args: list[ast.expr] = [
            ast.Name(id="_cache_key", ctx=ast.Load()),
            ast.Name(id="_cached", ctx=ast.Load()),
        ]
        if node.ttl:
            cache_set_args.append(self._compile_expr(node.ttl))
        else:
            cache_set_args.append(ast.Constant(value=None))

        else_body.append(
            ast.Assign(
                targets=[ast.Name(id="_cached", ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Name(id="_cache_set", ctx=ast.Load()),
                    args=cache_set_args,
                    keywords=[],
                ),
            )
        )

        # Emit cached result: _append(_cached) or yield _cached
        else_body.append(self._emit_output(ast.Name(id="_cached", ctx=ast.Load())))

        # if _cached is not None: emit(_cached) else: ...
        stmts.append(
            ast.If(
                test=ast.Compare(
                    left=ast.Name(id="_cached", ctx=ast.Load()),
                    ops=[ast.IsNot()],
                    comparators=[ast.Constant(value=None)],
                ),
                body=[self._emit_output(ast.Name(id="_cached", ctx=ast.Load()))],
                orelse=else_body,
            )
        )

        return stmts

    def _compile_filter_block(self, node: FilterBlock) -> list[ast.stmt]:
        """Compile {% filter name %}...{% endfilter %.

        Apply a filter to an entire block of content.
        In streaming mode: collect into buffer, apply filter, yield result.
        """
        self._block_counter += 1
        suffix = str(self._block_counter)
        buf_name = f"_filter_buf_{suffix}"
        append_name = f"_filter_append_{suffix}"

        stmts: list[ast.stmt] = [
            ast.Assign(
                targets=[ast.Name(id=buf_name, ctx=ast.Store())],
                value=ast.List(elts=[], ctx=ast.Load()),
            ),
            ast.Assign(
                targets=[ast.Name(id=append_name, ctx=ast.Store())],
                value=ast.Attribute(
                    value=ast.Name(id=buf_name, ctx=ast.Load()),
                    attr="append",
                    ctx=ast.Load(),
                ),
            ),
        ]

        if self._streaming:
            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id="_append", ctx=ast.Store())],
                    value=ast.Name(id=append_name, ctx=ast.Load()),
                )
            )
            self._streaming = False
            for child in node.body:
                stmts.extend(self._compile_node(child))
            self._streaming = True
        else:
            save_name = f"_save_append_{suffix}"
            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id=save_name, ctx=ast.Store())],
                    value=ast.Name(id="_append", ctx=ast.Load()),
                )
            )
            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id="_append", ctx=ast.Store())],
                    value=ast.Name(id=append_name, ctx=ast.Load()),
                )
            )
            for child in node.body:
                stmts.extend(self._compile_node(child))
            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id="_append", ctx=ast.Store())],
                    value=ast.Name(id=save_name, ctx=ast.Load()),
                )
            )

        # Build filter call: _filters['name'](''.join(buf), *args, **kwargs)
        filter_args: list[ast.expr] = [
            ast.Call(
                func=ast.Attribute(
                    value=ast.Constant(value=""),
                    attr="join",
                    ctx=ast.Load(),
                ),
                args=[ast.Name(id=buf_name, ctx=ast.Load())],
                keywords=[],
            )
        ]

        filter_node = node.filter
        filter_args.extend([self._compile_expr(a) for a in filter_node.args])
        filter_kwargs = [
            ast.keyword(arg=k, value=self._compile_expr(v))
            for k, v in filter_node.kwargs.items()
        ]

        filter_call = ast.Call(
            func=ast.Subscript(
                value=ast.Name(id="_filters", ctx=ast.Load()),
                slice=ast.Constant(value=filter_node.name),
                ctx=ast.Load(),
            ),
            args=filter_args,
            keywords=filter_kwargs,
        )

        # Profiling: _record_filter(_acc, 'name', filter_result)
        result_expr = ast.Call(
            func=ast.Name(id="_record_filter", ctx=ast.Load()),
            args=[
                ast.Name(id="_acc", ctx=ast.Load()),
                ast.Constant(value=filter_node.name),
                filter_call,
            ],
            keywords=[],
        )

        # _append(result) or yield result
        stmts.append(self._emit_output(result_expr))

        return stmts
