"""Kida terminal components.

Provides a FileSystemLoader for terminal component templates, and a convenience
function to create a terminal-configured Environment.

Live rendering::

    from kida.terminal import terminal_env, LiveRenderer, Spinner

    env = terminal_env()
    tpl = env.from_string(template_str, name="live")

    with LiveRenderer(tpl) as live:
        live.update(status="building")
        time.sleep(1)
        live.update(status="done")

Progressive streaming::

    from kida.terminal import terminal_env, stream_to_terminal

    stream_to_terminal(template, context, delay=0.03)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from kida.terminal.live import LiveRenderer, Spinner, stream_to_terminal

if TYPE_CHECKING:
    from kida.environment import Environment


def terminal_env(**kwargs) -> Environment:
    """Create an Environment pre-configured for terminal output.

    Convenience wrapper that sets autoescape="terminal" and adds a
    loader for the built-in terminal component templates.

    All keyword arguments are passed to Environment, including:
        ambiguous_width: Override character width for ambiguous Unicode
            symbols (1=narrow, 2=wide). Auto-detected if not specified.
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
        autoescape="terminal",
        **kwargs,
    )
