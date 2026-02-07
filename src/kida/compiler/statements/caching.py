"""Caching and filter-block statement compilation for Kida compiler.

Provides mixin for compiling cache blocks and filter blocks -- both
follow the "capture output, transform, emit" pattern.

Extracted from special_blocks.py for module focus (RFC: compiler decomposition).
Uses inline TYPE_CHECKING declarations for host attributes.
See: plan/rfc-mixin-protocol-typing.md
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


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

        # From ExpressionCompilationMixin
        def _compile_expr(self, node: Any, store: bool = False) -> ast.expr: ...

        # From Compiler core
        def _compile_node(self, node: Any) -> list[ast.stmt]: ...

    def _compile_cache(self, node: Any) -> list[ast.stmt]:
        """Compile {% cache key %}...{% endcache %.

        Fragment caching for expensive template sections.

        Generates:
            _cache_key = str(key)
            _cached = _cache_get(_cache_key)
            if _cached is not None:
                _append(_cached)
            else:
                _cache_buf = []
                _cache_append = _cache_buf.append
                _save_append = _append
                _append = _cache_append
                ... body ...
                _append = _save_append
                _cached = ''.join(_cache_buf)
                _cache_set(_cache_key, _cached, ttl)
                _append(_cached)
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
            # _cache_buf = []
            ast.Assign(
                targets=[ast.Name(id="_cache_buf", ctx=ast.Store())],
                value=ast.List(elts=[], ctx=ast.Load()),
            ),
            # _cache_append = _cache_buf.append
            ast.Assign(
                targets=[ast.Name(id="_cache_append", ctx=ast.Store())],
                value=ast.Attribute(
                    value=ast.Name(id="_cache_buf", ctx=ast.Load()),
                    attr="append",
                    ctx=ast.Load(),
                ),
            ),
            # _save_append = _append
            ast.Assign(
                targets=[ast.Name(id="_save_append", ctx=ast.Store())],
                value=ast.Name(id="_append", ctx=ast.Load()),
            ),
            # _append = _cache_append
            ast.Assign(
                targets=[ast.Name(id="_append", ctx=ast.Store())],
                value=ast.Name(id="_cache_append", ctx=ast.Load()),
            ),
        ]

        # Compile body
        for child in node.body:
            else_body.extend(self._compile_node(child))

        # _append = _save_append
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
        cache_set_args = [
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

        # _append(_cached)
        else_body.append(
            ast.Expr(
                value=ast.Call(
                    func=ast.Name(id="_append", ctx=ast.Load()),
                    args=[ast.Name(id="_cached", ctx=ast.Load())],
                    keywords=[],
                ),
            )
        )

        # if _cached is not None: _append(_cached) else: ...
        stmts.append(
            ast.If(
                test=ast.Compare(
                    left=ast.Name(id="_cached", ctx=ast.Load()),
                    ops=[ast.IsNot()],
                    comparators=[ast.Constant(value=None)],
                ),
                body=[
                    ast.Expr(
                        value=ast.Call(
                            func=ast.Name(id="_append", ctx=ast.Load()),
                            args=[ast.Name(id="_cached", ctx=ast.Load())],
                            keywords=[],
                        ),
                    )
                ],
                orelse=else_body,
            )
        )

        return stmts

    def _compile_filter_block(self, node: Any) -> list[ast.stmt]:
        """Compile {% filter name %}...{% endfilter %.

        Apply a filter to an entire block of content.

        Uses unique variable names to support nesting.

        Generates:
            _filter_buf_N = []
            _filter_append_N = _filter_buf_N.append
            _save_append_N = _append
            _append = _filter_append_N
            ... body ...
            _append = _save_append_N
            _append(_filters['name'](''.join(_filter_buf_N), *args, **kwargs))
        """
        # Get unique suffix for this filter block
        self._block_counter += 1
        suffix = str(self._block_counter)
        buf_name = f"_filter_buf_{suffix}"
        append_name = f"_filter_append_{suffix}"
        save_name = f"_save_append_{suffix}"

        stmts: list[ast.stmt] = [
            # _filter_buf_N = []
            ast.Assign(
                targets=[ast.Name(id=buf_name, ctx=ast.Store())],
                value=ast.List(elts=[], ctx=ast.Load()),
            ),
            # _filter_append_N = _filter_buf_N.append
            ast.Assign(
                targets=[ast.Name(id=append_name, ctx=ast.Store())],
                value=ast.Attribute(
                    value=ast.Name(id=buf_name, ctx=ast.Load()),
                    attr="append",
                    ctx=ast.Load(),
                ),
            ),
            # _save_append_N = _append
            ast.Assign(
                targets=[ast.Name(id=save_name, ctx=ast.Store())],
                value=ast.Name(id="_append", ctx=ast.Load()),
            ),
            # _append = _filter_append_N
            ast.Assign(
                targets=[ast.Name(id="_append", ctx=ast.Store())],
                value=ast.Name(id=append_name, ctx=ast.Load()),
            ),
        ]

        # Compile body
        for child in node.body:
            stmts.extend(self._compile_node(child))

        # _append = _save_append_N
        stmts.append(
            ast.Assign(
                targets=[ast.Name(id="_append", ctx=ast.Store())],
                value=ast.Name(id=save_name, ctx=ast.Load()),
            )
        )

        # Build filter call: _filters['name'](''.join(_filter_buf_N), *args, **kwargs)
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

        # Add filter arguments from the Filter node
        filter_node = node.filter
        filter_args.extend([self._compile_expr(a) for a in filter_node.args])
        filter_kwargs = [
            ast.keyword(arg=k, value=self._compile_expr(v)) for k, v in filter_node.kwargs.items()
        ]

        # _append(_filters['name'](content, *args, **kwargs))
        stmts.append(
            ast.Expr(
                value=ast.Call(
                    func=ast.Name(id="_append", ctx=ast.Load()),
                    args=[
                        ast.Call(
                            func=ast.Subscript(
                                value=ast.Name(id="_filters", ctx=ast.Load()),
                                slice=ast.Constant(value=filter_node.name),
                                ctx=ast.Load(),
                            ),
                            args=filter_args,
                            keywords=filter_kwargs,
                        ),
                    ],
                    keywords=[],
                ),
            )
        )

        return stmts
