from __future__ import annotations

from typing import Any


def build_medium_context() -> dict[str, Any]:
    """Medium context: ~100 variables with nested structures."""
    context: dict[str, Any] = {
        "items": [{"id": i, "name": f"Item {i}", "price": i * 1.5} for i in range(100)],
        "categories": [f"Category {i}" for i in range(10)],
    }
    # Provide a simple sequence to reference via index in templates
    context["vars"] = [f"value_{i}" for i in range(20)]
    # Add additional scalar variables to reach ~100 entries
    for i in range(80):
        context[f"var_{i}"] = f"value_{i}"
    return context


MEDIUM_CONTEXT = build_medium_context()
