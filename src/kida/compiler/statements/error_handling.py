"""Error boundary compilation for Kida compiler.

Compiles {% try %}...{% fallback %}...{% end %} to Python try/except
with sub-buffer management for streaming safety.

Uses inline TYPE_CHECKING declarations for host attributes.
See: plan/rfc-mixin-protocol-typing.md
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kida.nodes import Node
    from kida.nodes.control_flow import Try


class ErrorHandlingMixin:
    """Mixin for compiling error boundary statements.

    Host attributes and cross-mixin dependencies are declared via inline
    TYPE_CHECKING blocks.
    """

    if TYPE_CHECKING:
        _streaming: bool
        _block_counter: int

        def _compile_node(self, node: Node) -> list[ast.stmt]: ...

    def _compile_try(self, node: Try) -> list[ast.stmt]:
        """Compile {% try %}...{% fallback %}...{% end %} error boundary.

        Both StringBuilder and streaming modes use the same sub-buffer
        strategy for the try body (must buffer to discard on error).

        Generated code (StringBuilder mode):

            _try_buf_N = []
            _try_append_N = _try_buf_N.append
            _saved_append_N = _append
            _append = _try_append_N
            try:
                # body compiled with _append → sub-buffer
                _append = _saved_append_N
                _append(''.join(_try_buf_N))
            except (...) as _err_N:
                _append = _saved_append_N
                # fallback body

        Generated code (streaming mode):

            _try_buf_N = []
            _append = _try_buf_N.append
            try:
                # body compiled in non-streaming mode → _append to buffer
                for _chunk in _try_buf_N: yield _chunk
            except (...) as _err_N:
                # fallback body compiled in streaming mode (yields)
        """
        self._block_counter += 1
        counter = self._block_counter
        buf_name = f"_try_buf_{counter}"
        append_name = f"_try_append_{counter}"
        err_name = f"_err_{counter}"

        stmts: list[ast.stmt] = []
        is_streaming = self._streaming

        # _try_buf_N = []
        stmts.append(
            ast.Assign(
                targets=[ast.Name(id=buf_name, ctx=ast.Store())],
                value=ast.List(elts=[], ctx=ast.Load()),
            )
        )

        # _try_append_N = _try_buf_N.append
        stmts.append(
            ast.Assign(
                targets=[ast.Name(id=append_name, ctx=ast.Store())],
                value=ast.Attribute(
                    value=ast.Name(id=buf_name, ctx=ast.Load()),
                    attr="append",
                    ctx=ast.Load(),
                ),
            )
        )

        if not is_streaming:
            # StringBuilder mode: save and redirect _append
            saved_append = f"_saved_append_{counter}"

            # _saved_append_N = _append
            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id=saved_append, ctx=ast.Store())],
                    value=ast.Name(id="_append", ctx=ast.Load()),
                )
            )

            # _append = _try_append_N
            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id="_append", ctx=ast.Store())],
                    value=ast.Name(id=append_name, ctx=ast.Load()),
                )
            )
        else:
            # Streaming mode: create local _append for the try body
            # _append = _try_append_N
            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id="_append", ctx=ast.Store())],
                    value=ast.Name(id=append_name, ctx=ast.Load()),
                )
            )

        # --- Try body ---
        # In streaming mode, compile body in non-streaming mode so it uses _append
        if is_streaming:
            self._streaming = False
        try_body: list[ast.stmt] = []
        for child in node.body:
            try_body.extend(self._compile_node(child))
        if is_streaming:
            self._streaming = True

        if not is_streaming:
            # Restore _append before flush
            try_body.append(
                ast.Assign(
                    targets=[ast.Name(id="_append", ctx=ast.Store())],
                    value=ast.Name(id=saved_append, ctx=ast.Load()),
                )
            )
            # _append(''.join(_try_buf_N))
            try_body.append(
                ast.Expr(
                    value=ast.Call(
                        func=ast.Name(id="_append", ctx=ast.Load()),
                        args=[
                            ast.Call(
                                func=ast.Attribute(
                                    value=ast.Constant(value=""),
                                    attr="join",
                                    ctx=ast.Load(),
                                ),
                                args=[ast.Name(id=buf_name, ctx=ast.Load())],
                                keywords=[],
                            )
                        ],
                        keywords=[],
                    )
                )
            )
        else:
            # Streaming: yield buffered chunks on success
            # for _chunk in _try_buf_N: yield _chunk
            try_body.append(
                ast.For(
                    target=ast.Name(id="_chunk", ctx=ast.Store()),
                    iter=ast.Name(id=buf_name, ctx=ast.Load()),
                    body=[ast.Expr(value=ast.Yield(value=ast.Name(id="_chunk", ctx=ast.Load())))],
                    orelse=[],
                )
            )

        # --- Except handler ---
        except_body: list[ast.stmt] = []

        if not is_streaming:
            # Restore _append in except path
            except_body.append(
                ast.Assign(
                    targets=[ast.Name(id="_append", ctx=ast.Store())],
                    value=ast.Name(id=saved_append, ctx=ast.Load()),
                )
            )

        # If error_name is set, bind error dict to scope_stack
        if node.error_name:
            # _scope_stack.append({error_name: _make_error_dict(_err_N)})
            except_body.append(
                ast.Expr(
                    value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id="_scope_stack", ctx=ast.Load()),
                            attr="append",
                            ctx=ast.Load(),
                        ),
                        args=[
                            ast.Dict(
                                keys=[ast.Constant(value=node.error_name)],
                                values=[
                                    ast.Call(
                                        func=ast.Name(id="_make_error_dict", ctx=ast.Load()),
                                        args=[ast.Name(id=err_name, ctx=ast.Load())],
                                        keywords=[],
                                    )
                                ],
                            )
                        ],
                        keywords=[],
                    )
                )
            )

        # Compile fallback body (in current mode — _append for SB, yield for streaming)
        for child in node.fallback:
            except_body.extend(self._compile_node(child))

        if not except_body:
            except_body = [ast.Pass()]

        # Exception types to catch
        exc_types = ast.Tuple(
            elts=[
                ast.Name(id="_TemplateRuntimeError", ctx=ast.Load()),
                ast.Name(id="_UndefinedError", ctx=ast.Load()),
                ast.Name(id="_TypeError", ctx=ast.Load()),
                ast.Name(id="_ValueError", ctx=ast.Load()),
            ],
            ctx=ast.Load(),
        )

        # Build the ast.Try
        try_node = ast.Try(
            body=try_body,
            handlers=[
                ast.ExceptHandler(
                    type=exc_types,
                    name=err_name,
                    body=except_body,
                )
            ],
            orelse=[],
            finalbody=[],
        )

        stmts.append(try_node)

        return stmts
