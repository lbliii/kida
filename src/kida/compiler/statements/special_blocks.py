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

        # From ExpressionCompilationMixin
        def _compile_expr(self, node: Any, store: bool = False) -> ast.expr: ...

        # From Compiler core
        def _compile_node(self, node: Any) -> list[ast.stmt]: ...

    def _compile_raw(self, node: Any) -> list[ast.stmt]:
        """Compile {% raw %}...{% endraw %.

        Raw block content is output as literal text.
        """
        if not node.value:
            return []

        return [
            ast.Expr(
                value=ast.Call(
                    func=ast.Name(id="_append", ctx=ast.Load()),
                    args=[ast.Constant(value=node.value)],
                    keywords=[],
                ),
            )
        ]

    def _compile_capture(self, node: Any) -> list[ast.stmt]:
        """Compile {% capture x %}...{% end %} (Kida) or {% set x %}...{% endset %} (Jinja).

        Captures rendered block content into a variable.
        """
        # Create a temporary buffer
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
            # _save_append = _append
            ast.Assign(
                targets=[ast.Name(id="_save_append", ctx=ast.Store())],
                value=ast.Name(id="_append", ctx=ast.Load()),
            ),
            # _append = _capture_append
            ast.Assign(
                targets=[ast.Name(id="_append", ctx=ast.Store())],
                value=ast.Name(id="_capture_append", ctx=ast.Load()),
            ),
        ]

        # Compile body
        for child in node.body:
            stmts.extend(self._compile_node(child))

        # Restore original append and assign result
        stmts.extend(
            [
                # _append = _save_append
                ast.Assign(
                    targets=[ast.Name(id="_append", ctx=ast.Store())],
                    value=ast.Name(id="_save_append", ctx=ast.Load()),
                ),
                # ctx['name'] = ''.join(_capture_buf)
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
                ),
            ]
        )

        return stmts

    def _compile_spaceless(self, node: Any) -> list[ast.stmt]:
        """Compile {% spaceless %}...{% end %}.

        Removes whitespace between HTML tags.
        Part of RFC: kida-modern-syntax-features.

        Generates:
            _spaceless_buf_N = []
            _spaceless_append_N = _spaceless_buf_N.append
            _save_append_N = _append
            _append = _spaceless_append_N
            ... body ...
            _append = _save_append_N
            _append(_spaceless(''.join(_spaceless_buf_N)))
        """
        # Get unique suffix for this spaceless block
        self._block_counter += 1
        suffix = str(self._block_counter)
        buf_name = f"_spaceless_buf_{suffix}"
        append_name = f"_spaceless_append_{suffix}"
        save_name = f"_save_append_{suffix}"

        stmts: list[ast.stmt] = [
            # _spaceless_buf_N = []
            ast.Assign(
                targets=[ast.Name(id=buf_name, ctx=ast.Store())],
                value=ast.List(elts=[], ctx=ast.Load()),
            ),
            # _spaceless_append_N = _spaceless_buf_N.append
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
            # _append = _spaceless_append_N
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

        # _append(_spaceless(''.join(_spaceless_buf_N)))
        stmts.append(
            ast.Expr(
                value=ast.Call(
                    func=ast.Name(id="_append", ctx=ast.Load()),
                    args=[
                        ast.Call(
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
                        ),
                    ],
                    keywords=[],
                ),
            )
        )

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

        # Include the embedded template: _append(_include(template, ctx, blocks=_blocks))
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
