from __future__ import annotations

from typing import Any


def build_large_context() -> dict[str, Any]:
    """Large context: 1000 items with nested data."""
    return {
        "items": [
            {
                "id": i,
                "name": f"Item {i}",
                "data": {"x": i, "y": i * 2},
            }
            for i in range(1000)
        ]
    }


LARGE_CONTEXT = build_large_context()
