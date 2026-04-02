"""Unified AST Visitor and Transformer base classes.

Provides ``NodeVisitor`` and ``NodeTransformer`` with automatic
``visit_<Type>`` dispatch, eliminating the need for every analysis module
to implement its own traversal logic.

Adding a new AST node type requires zero changes to visitor code —
``generic_visit`` uses ``Node.iter_child_nodes()`` (backed by
``__dataclass_fields__`` introspection) to discover children automatically.

Usage::

    class MyAnalyzer(NodeVisitor):
        def visit_Name(self, node: Name) -> None:
            print(f"Found name: {node.name}")

        def visit_Filter(self, node: Filter) -> None:
            print(f"Found filter: {node.name}")
            self.generic_visit(node)  # visit children too

    class MyOptimizer(NodeTransformer):
        def visit_Const(self, node: Const) -> Node:
            if isinstance(node.value, str):
                return Const(lineno=node.lineno, col_offset=node.col_offset,
                             value=node.value.upper())
            return node

"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar

from kida.nodes.base import Node

if TYPE_CHECKING:
    from collections.abc import Sequence


class NodeVisitor:
    """Walk a Kida AST calling ``visit_<Type>`` methods on each node.

    For every node encountered, ``visit()`` checks for a ``visit_<Type>``
    method (where ``<Type>`` is ``type(node).__name__``) and calls it.
    If no specific method exists, ``generic_visit()`` is called, which
    visits all child nodes.

    Subclasses override ``visit_<Type>`` to handle specific node types.
    Call ``self.generic_visit(node)`` inside a handler to also visit children.
    """

    # Per-class dispatch cache: type → unbound function (from class dict)
    # Stores functions (not bound methods) so all instances share safely.
    _dispatch_cache: ClassVar[dict[type, Any]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Each subclass gets its own dispatch cache
        cls._dispatch_cache = {}

    def visit(self, node: Node) -> Any:
        """Dispatch to ``visit_<Type>`` or ``generic_visit``."""
        node_type = type(node)
        func = self._dispatch_cache.get(node_type)
        if func is None:
            method_name = f"visit_{node_type.__name__}"
            for klass in type(self).__mro__:
                if method_name in klass.__dict__:
                    func = klass.__dict__[method_name]
                    break
            else:
                # Find generic_visit via MRO to honor subclass overrides
                for klass in type(self).__mro__:
                    if "generic_visit" in klass.__dict__:
                        func = klass.__dict__["generic_visit"]
                        break
                else:
                    func = NodeVisitor.generic_visit
            self._dispatch_cache[node_type] = func
        return func(self, node)

    def generic_visit(self, node: Node) -> None:
        """Visit all child nodes (default handler)."""
        for child in node.iter_child_nodes():
            self.visit(child)


class NodeTransformer:
    """Walk a Kida AST and rebuild nodes when ``visit_<Type>`` returns a replacement.

    Similar to ``NodeVisitor`` but each handler returns a (possibly new) node.
    ``generic_visit()`` visits all child fields; if any child changes, the
    parent node is reconstructed via ``dataclasses.replace()``.

    Subclasses override ``visit_<Type>`` to transform specific node types.
    Returning ``None`` from a handler removes the node from its parent's body.
    """

    _dispatch_cache: ClassVar[dict[type, Any]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._dispatch_cache = {}

    def visit(self, node: Node) -> Node | None:
        """Dispatch to ``visit_<Type>`` or ``generic_visit``."""
        node_type = type(node)
        func = self._dispatch_cache.get(node_type)
        if func is None:
            method_name = f"visit_{node_type.__name__}"
            for klass in type(self).__mro__:
                if method_name in klass.__dict__:
                    func = klass.__dict__[method_name]
                    break
            else:
                # Find generic_visit via MRO to honor subclass overrides
                for klass in type(self).__mro__:
                    if "generic_visit" in klass.__dict__:
                        func = klass.__dict__["generic_visit"]
                        break
                else:
                    func = NodeTransformer.generic_visit
            self._dispatch_cache[node_type] = func
        return func(self, node)

    def generic_visit(self, node: Node) -> Node:
        """Rebuild *node* if any child field changed after visiting."""
        changed_fields: dict[str, Any] = {}

        for field_name in node.__dataclass_fields__:
            if field_name in ("lineno", "col_offset"):
                continue
            value = getattr(node, field_name)
            new_value = self._visit_field(value)
            if new_value is not value:
                changed_fields[field_name] = new_value

        if not changed_fields:
            return node
        return dataclasses.replace(node, **changed_fields)

    # ------------------------------------------------------------------
    # Field-level visiting helpers
    # ------------------------------------------------------------------

    def _visit_field(self, value: Any) -> Any:
        """Visit a single field value, returning updated value if changed."""
        match value:
            case None:
                return value
            case Node():
                return self.visit(value)
            case list() | tuple():
                return self._visit_sequence(value)
            case dict():
                return self._visit_dict(value)
            case _:
                # Primitive value (str, int, bool, etc.) — pass through
                return value

    def _visit_sequence(self, seq: Sequence[Any]) -> Sequence[Any]:
        """Visit a sequence, handling nested tuples (elif_, cases, etc.)."""
        new_items: list[Any] = []
        changed = False

        for item in seq:
            if isinstance(item, Node):
                new_item = self.visit(item)
                if new_item is None:
                    changed = True
                    continue  # Remove node
                if new_item is not item:
                    changed = True
                new_items.append(new_item)
            elif isinstance(item, (list, tuple)):
                new_sub = self._visit_sequence(item)
                if new_sub is not item:
                    changed = True
                new_items.append(new_sub)
            else:
                # Primitive (str, int, etc.)
                new_items.append(item)

        if not changed:
            return seq
        return type(seq)(new_items) if isinstance(seq, tuple) else new_items

    def _visit_dict(self, mapping: dict[str, Any]) -> dict[str, Any]:
        """Visit dict values (kwargs, slots, embed blocks, etc.)."""
        new_dict: dict[str, Any] = {}
        changed = False

        for key, value in mapping.items():
            if isinstance(value, Node):
                new_value = self.visit(value)
                if new_value is not value:
                    changed = True
                new_dict[key] = new_value
            elif isinstance(value, (list, tuple)):
                new_value = self._visit_sequence(value)
                if new_value is not value:
                    changed = True
                new_dict[key] = new_value
            else:
                new_dict[key] = value

        if not changed:
            return mapping
        return new_dict
