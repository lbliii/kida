"""Shared visitor patterns for Kida AST analysis.

Provides NODE_CHILD_ATTRS and visit_children for generic AST traversal.
Used by DependencyWalker, BlockAnalyzer, and purity analysis.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kida.nodes import Node

# Shared attr lists for generic child traversal
CONTAINER_ATTRS = ("body", "else_", "empty", "elif_")
EXPR_ATTRS = (
    "test",
    "expr",
    "value",
    "iter",
    "left",
    "right",
    "operand",
    "obj",
    "key",
    "func",
    "subject",
    "if_true",
    "if_false",
    "start",
    "end",
    "step",
    "stop",
    "template",
)
SEQUENCE_ATTRS = ("args", "items", "nodes", "comparators", "values", "keys", "defaults", "depends")


def visit_children(node: Node, visit: Callable[[Node | None], None]) -> None:
    """Visit all child nodes of a Kida AST node (generic handler).

    Handles container attrs (body, else_, empty, elif_), expression attrs,
    sequence attrs, kwargs, Pipeline steps, Match cases, With targets, Embed blocks.
    """
    # Container attributes
    for attr in CONTAINER_ATTRS:
        if hasattr(node, attr):
            children = getattr(node, attr)
            if children and isinstance(children, (list, tuple)):
                for child in children:
                    if hasattr(child, "lineno"):
                        visit(child)
                    elif isinstance(child, tuple):
                        test, body = child
                        visit(test)
                        for b in body:
                            visit(b)

    # Expression attributes
    for attr in EXPR_ATTRS:
        if hasattr(node, attr):
            child = getattr(node, attr)
            if child and hasattr(child, "lineno"):
                visit(child)

    # Sequence attributes
    for attr in SEQUENCE_ATTRS:
        if hasattr(node, attr):
            children = getattr(node, attr)
            if children:
                for child in children:
                    if hasattr(child, "lineno"):
                        visit(child)

    # Dict attributes (kwargs)
    if hasattr(node, "kwargs"):
        mapping = getattr(node, "kwargs", None)
        if mapping:
            for child in mapping.values():
                if hasattr(child, "lineno"):
                    visit(child)

    # Pipeline steps
    steps = getattr(node, "steps", None)
    if steps:
        for step in steps:
            if isinstance(step, tuple) and len(step) == 3:
                _name, args, kwargs = step
                for arg in args:
                    if hasattr(arg, "lineno"):
                        visit(arg)
                for val in kwargs.values():
                    if hasattr(val, "lineno"):
                        visit(val)

    # Match cases
    cases = getattr(node, "cases", None)
    if cases:
        for pattern, guard, body in cases:
            visit(pattern)
            if guard:
                visit(guard)
            for child in body:
                visit(child)

    # With targets
    targets = getattr(node, "targets", None)
    if targets and isinstance(targets, (list, tuple)):
        for target in targets:
            if isinstance(target, tuple) and len(target) == 2:
                _name, value = target
                visit(value)

    # Embed blocks
    blocks = getattr(node, "blocks", None)
    if isinstance(blocks, dict):
        for block in blocks.values():
            if hasattr(block, "lineno"):
                visit(block)

    # CallBlock slots
    slots = getattr(node, "slots", None)
    if slots and isinstance(slots, dict):
        for slot_body in slots.values():
            for child in slot_body:
                if hasattr(child, "lineno"):
                    visit(child)
