"""Kida markdown components.

Provides a convenience function to create a markdown-configured Environment
and a loader for built-in markdown component templates.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kida.environment import Environment


def markdown_env(**kwargs) -> Environment:
    """Create an Environment pre-configured for markdown output.

    Convenience wrapper that sets autoescape="markdown" and adds a
    loader for the built-in markdown component templates.

    All keyword arguments are passed to Environment.
    """
    from kida.environment import Environment
    from kida.environment.loaders import ChoiceLoader, FileSystemLoader

    # Component templates directory
    components_dir = os.path.dirname(__file__)

    user_loader = kwargs.pop("loader", None)

    # Build loader chain: user loader first, then built-in components
    loaders = []
    if user_loader is not None:
        loaders.append(user_loader)
    loaders.append(FileSystemLoader(components_dir))

    return Environment(
        loader=ChoiceLoader(loaders) if len(loaders) > 1 else loaders[0],
        autoescape="markdown",
        **kwargs,
    )
