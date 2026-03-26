"""Markdown mode initialization for Kida template engine.

Mirrors terminal.py — registers markdown filters and globals when
``autoescape="markdown"`` is set on the Environment.
"""

from __future__ import annotations

from typing import Any


def _init_markdown_mode(env: Any) -> None:
    """Configure Environment for ``autoescape="markdown"`` mode.

    Registers markdown-specific filters and injects globals.
    """
    from kida.environment.filters._markdown import make_markdown_filters

    md_filters = make_markdown_filters()
    env._filters.update(md_filters)

    # Inject markdown globals
    env.globals.update(
        {
            "output_format": "markdown",
        }
    )
