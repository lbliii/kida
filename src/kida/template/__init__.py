"""Kida Template package — compiled template objects ready for rendering.

Re-exports all public symbols so that ``from kida.template import Template``
continues to work after the module-to-package conversion.

"""

from kida.template.cached_blocks import CachedBlocksDict
from kida.template.core import RenderedTemplate, Template
from kida.template.loop_context import AsyncLoopContext, LoopContext
from kida.utils.html import Markup

__all__ = [
    "AsyncLoopContext",
    "CachedBlocksDict",
    "LoopContext",
    "Markup",
    "RenderedTemplate",
    "Template",
]
