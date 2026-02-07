"""Special block statement compilation for Kida compiler.

Provides mixin for compiling special block statements (raw, capture, spaceless, embed).

With-blocks are in with_blocks.py; cache/filter_block are in caching.py.
Uses inline TYPE_CHECKING declarations for host attributes.
See: plan/rfc-mixin-protocol-typing.md
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


class SpecialBlockMixin:
    """Mixin for compiling special block statements.

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
        def _compile_expr(self, node: Any, store: bool = False) -> ast.expr: ...

        # From Compiler core
        def _compile_node(self, node: Any) -> list[ast.stmt]: ...
        def _emit_output(self, value_expr: ast.expr) -> ast.stmt: ...

    def _compile_raw(self, node: Any) -> list[ast.stmt]:
        """Compile {% raw %}...{% endraw %.

        Raw block content is output as literal text.
        """
        if not node.value:
            return []

        return [self._emit_output(ast.Constant(value=node.value))]

    def _compile_capture(self, node: Any) -> list[ast.stmt]:
        """Compile {% capture x %}...{% end %} (Kida) or {% set x %}...{% endset %} (Jinja).

        Captures rendered block content into a variable.
        In streaming mode, body is compiled in StringBuilder mode (captures
        into a buffer, not the output stream), then result is assigned to ctx.
        """
        stmts: list[ast.stmt] = [
            # _capture_buf = []
            ast.Assign(
                targets=[ast.Name(id="_capture_buf", ctx=ast.Store())],
                value=ast.List(elts=[], ctx=ast.Load()),
            ),
            # _capture_append = _capture_buf.append
            ast.Assign(
                targets=[ast.Name(id="_capture_append", ctx=ast.Store())],
                value=ast.Attribute(
                    value=ast.Name(id="_capture_buf", ctx=ast.Load()),
                    attr="append",
                    ctx=ast.Load(),
                ),
            ),
        ]

        if self._streaming:
            # In streaming mode: no outer _append to save/restore.
            # Define _append locally for the body to use.
            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id="_append", ctx=ast.Store())],
                    value=ast.Name(id="_capture_append", ctx=ast.Load()),
                )
            )

            # Compile body in StringBuilder mode so it uses _append
            self._streaming = False
            for child in node.body:
                stmts.extend(self._compile_node(child))
            self._streaming = True
        else:
            # Save/restore outer _append
            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id="_save_append", ctx=ast.Store())],
                    value=ast.Name(id="_append", ctx=ast.Load()),
                )
            )
            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id="_append", ctx=ast.Store())],
                    value=ast.Name(id="_capture_append", ctx=ast.Load()),
                )
            )

            for child in node.body:
                stmts.extend(self._compile_node(child))

            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id="_append", ctx=ast.Store())],
                    value=ast.Name(id="_save_append", ctx=ast.Load()),
                )
            )

        # ctx['name'] = ''.join(_capture_buf)
        stmts.append(
            ast.Assign(
                targets=[
                    ast.Subscript(
                        value=ast.Name(id="ctx", ctx=ast.Load()),
                        slice=ast.Constant(value=node.name),
                        ctx=ast.Store(),
                    )
                ],
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Constant(value=""),
                        attr="join",
                        ctx=ast.Load(),
                    ),
                    args=[ast.Name(id="_capture_buf", ctx=ast.Load())],
                    keywords=[],
                ),
            )
        )

        return stmts

    def _compile_spaceless(self, node: Any) -> list[ast.stmt]:
        """Compile {% spaceless %}...{% end %}.

        Removes whitespace between HTML tags.
        In streaming mode: collect into buffer, transform, yield result.
        """
        self._block_counter += 1
        suffix = str(self._block_counter)
        buf_name = f"_spaceless_buf_{suffix}"
        append_name = f"_spaceless_append_{suffix}"

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

        # Build the transformed result expression
        result_expr = ast.Call(
            func=ast.Name(id="_spaceless", ctx=ast.Load()),
            args=[
                ast.Call(
                    func=ast.Attribute(
                        value=ast.Constant(value=""),
                        attr="join",
                        ctx=ast.Load(),
                    ),
                    args=[ast.Name(id=buf_name, ctx=ast.Load())],
                    keywords=[],
                ),
            ],
            keywords=[],
        )

        if self._streaming:
            # Define _append locally for the body
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
            # yield _spaceless(''.join(buf))
            stmts.append(self._emit_output(result_expr))
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
            # _append(_spaceless(''.join(buf)))
            stmts.append(self._emit_output(result_expr))

        return stmts

    def _compile_embed(self, node: Any) -> list[ast.stmt]:
        """Compile {% embed 'template.html' %}...{% end %}.

        Embed is like include but allows block overrides.
        Part of RFC: kida-modern-syntax-features.

        Generates:
            _saved_blocks_N = _blocks.copy()
            def _block_name(ctx, _blocks): ...  # For each override
            _blocks['name'] = _block_name
            _append(_include(template, ctx, _blocks))
            _blocks = _saved_blocks_N
        """
        # Get unique suffix for this embed
        self._block_counter += 1
        suffix = str(self._block_counter)
        saved_blocks_name = f"_saved_blocks_{suffix}"

        stmts: list[ast.stmt] = []

        # _saved_blocks_N = _blocks.copy()
        stmts.append(
            ast.Assign(
                targets=[ast.Name(id=saved_blocks_name, ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="_blocks", ctx=ast.Load()),
                        attr="copy",
                        ctx=ast.Load(),
                    ),
                    args=[],
                    keywords=[],
                ),
            )
        )

        # Create block override functions
        for name, block in node.blocks.items():
            block_func_name = f"_block_{name}_{suffix}"

            # Build block function body
            block_body: list[ast.stmt] = [
                # _e = _escape
                ast.Assign(
                    targets=[ast.Name(id="_e", ctx=ast.Store())],
                    value=ast.Name(id="_escape", ctx=ast.Load()),
                ),
                # _s = _str
                ast.Assign(
                    targets=[ast.Name(id="_s", ctx=ast.Store())],
                    value=ast.Name(id="_str", ctx=ast.Load()),
                ),
                # buf = []
                ast.Assign(
                    targets=[ast.Name(id="buf", ctx=ast.Store())],
                    value=ast.List(elts=[], ctx=ast.Load()),
                ),
                # _append = buf.append
                ast.Assign(
                    targets=[ast.Name(id="_append", ctx=ast.Store())],
                    value=ast.Attribute(
                        value=ast.Name(id="buf", ctx=ast.Load()),
                        attr="append",
                        ctx=ast.Load(),
                    ),
                ),
            ]

            # Compile block body
            for child in block.body:
                block_body.extend(self._compile_node(child))

            # return ''.join(buf)
            block_body.append(
                ast.Return(
                    value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Constant(value=""),
                            attr="join",
                            ctx=ast.Load(),
                        ),
                        args=[ast.Name(id="buf", ctx=ast.Load())],
                        keywords=[],
                    ),
                )
            )

            # def _block_name_N(ctx, _blocks): ...
            stmts.append(
                ast.FunctionDef(
                    name=block_func_name,
                    args=ast.arguments(
                        posonlyargs=[],
                        args=[ast.arg(arg="ctx"), ast.arg(arg="_blocks")],
                        vararg=None,
                        kwonlyargs=[],
                        kw_defaults=[],
                        kwarg=None,
                        defaults=[],
                    ),
                    body=block_body,
                    decorator_list=[],
                    returns=None,
                )
            )

            # _blocks['name'] = _block_name_N
            stmts.append(
                ast.Assign(
                    targets=[
                        ast.Subscript(
                            value=ast.Name(id="_blocks", ctx=ast.Load()),
                            slice=ast.Constant(value=name),
                            ctx=ast.Store(),
                        )
                    ],
                    value=ast.Name(id=block_func_name, ctx=ast.Load()),
                )
            )

        # Include the embedded template
        if self._streaming:
            # yield from _include_stream(template, ctx, blocks=_blocks)
            stmts.append(
                ast.Expr(
                    value=ast.YieldFrom(
                        value=ast.Call(
                            func=ast.Name(id="_include_stream", ctx=ast.Load()),
                            args=[
                                self._compile_expr(node.template),
                                ast.Name(id="ctx", ctx=ast.Load()),
                            ],
                            keywords=[
                                ast.keyword(
                                    arg="blocks",
                                    value=ast.Name(id="_blocks", ctx=ast.Load()),
                                ),
                            ],
                        ),
                    ),
                )
            )
        else:
            # _append(_include(template, ctx, blocks=_blocks))
            stmts.append(
                ast.Expr(
                    value=ast.Call(
                        func=ast.Name(id="_append", ctx=ast.Load()),
                        args=[
                            ast.Call(
                                func=ast.Name(id="_include", ctx=ast.Load()),
                                args=[
                                    self._compile_expr(node.template),
                                    ast.Name(id="ctx", ctx=ast.Load()),
                                ],
                                keywords=[
                                    ast.keyword(
                                        arg="blocks",
                                        value=ast.Name(id="_blocks", ctx=ast.Load()),
                                    ),
                                ],
                            ),
                        ],
                        keywords=[],
                    ),
                )
            )

        # _blocks = _saved_blocks_N
        stmts.append(
            ast.Assign(
                targets=[ast.Name(id="_blocks", ctx=ast.Store())],
                value=ast.Name(id=saved_blocks_name, ctx=ast.Load()),
            )
        )

        return stmts
