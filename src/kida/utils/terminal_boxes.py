"""Box-drawing character sets for Kida terminal templates.

Provides ``BoxChars`` (a frozen dataclass of box-drawing characters) and
``BoxSet`` (a proxy that selects a style by name from templates).

Usage in templates::

    {% set b = box.round %}
    {{ b.tl }}{{ b.h * width }}{{ b.tr }}

Thread-Safety:
    Both ``BoxChars`` and ``BoxSet`` are immutable. Safe for concurrent access.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

# =============================================================================
# BoxChars Dataclass
# =============================================================================


@final
@dataclass(frozen=True, slots=True)
class BoxChars:
    """A complete set of box-drawing characters for one style.

    Fields:
        tl, tr, bl, br: Corner characters (top-left, top-right, etc.)
        h, v: Horizontal and vertical line characters.
        lj, rj, tj, bj: Junction characters (left, right, top, bottom).
        cross: Four-way junction character.
    """

    tl: str
    tr: str
    bl: str
    br: str
    h: str
    v: str
    lj: str
    rj: str
    tj: str
    bj: str
    cross: str


# =============================================================================
# Built-in Styles
# =============================================================================

_STYLES: dict[str, BoxChars] = {
    "light": BoxChars(
        tl="┌",
        tr="┐",
        bl="└",
        br="┘",
        h="─",
        v="│",
        lj="├",
        rj="┤",
        tj="┬",
        bj="┴",
        cross="┼",
    ),
    "heavy": BoxChars(
        tl="┏",
        tr="┓",
        bl="┗",
        br="┛",
        h="━",
        v="┃",
        lj="┣",
        rj="┫",
        tj="┳",
        bj="┻",
        cross="╋",
    ),
    "double": BoxChars(
        tl="╔",
        tr="╗",
        bl="╚",
        br="╝",
        h="═",
        v="║",
        lj="╠",
        rj="╣",
        tj="╦",
        bj="╩",
        cross="╬",
    ),
    "round": BoxChars(
        tl="╭",
        tr="╮",
        bl="╰",
        br="╯",
        h="─",
        v="│",
        lj="├",
        rj="┤",
        tj="┬",
        bj="┴",
        cross="┼",
    ),
    "ascii": BoxChars(
        tl="+",
        tr="+",
        bl="+",
        br="+",
        h="-",
        v="|",
        lj="+",
        rj="+",
        tj="+",
        bj="+",
        cross="+",
    ),
}


# =============================================================================
# BoxSet Proxy
# =============================================================================


class BoxSet:
    """Proxy object for accessing box-drawing styles from templates.

    Attribute access returns a ``BoxChars`` instance for the requested style.
    When ``unicode`` is False, all styles resolve to the ``ascii`` set.

    Args:
        unicode: When True, return the requested Unicode style; when False,
                 always return the ASCII fallback.

    Example:
        >>> box = BoxSet(unicode=True)
        >>> box.round.tl
        '╭'
        >>> box = BoxSet(unicode=False)
        >>> box.round.tl
        '+'
    """

    __slots__ = ("_unicode",)

    def __init__(self, *, unicode: bool = True) -> None:
        object.__setattr__(self, "_unicode", unicode)

    def __getattr__(self, name: str) -> BoxChars:
        if name not in _STYLES:
            available = ", ".join(sorted(_STYLES))
            raise AttributeError(f"Unknown box style {name!r}; available styles: {available}")
        if not self._unicode:
            return _STYLES["ascii"]
        return _STYLES[name]

    def __repr__(self) -> str:
        return f"BoxSet(unicode={self._unicode})"


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    "BoxChars",
    "BoxSet",
]
