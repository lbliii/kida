"""Base node class for Kida AST."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Node:
    """Base class for all AST nodes.

    All nodes track their source location for error reporting.
    Nodes are immutable for thread-safety.

    """

    lineno: int
    col_offset: int
