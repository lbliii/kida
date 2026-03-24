"""Terminal icon definitions for Kida template engine.

Provides an ``IconSet`` proxy that templates use to emit Unicode or ASCII icons.
Each icon is returned as a ``Styled`` string so it bypasses ANSI sanitization.

Usage in templates::

    {{ icons.check }} All tests passed
    {{ icons.arrow_r }} Next step

Thread-Safety:
    ``IconSet`` is immutable after construction. Safe for concurrent access.
"""

from __future__ import annotations

from difflib import get_close_matches

from kida.utils.terminal_escape import Styled

# =============================================================================
# Icon Definitions — (unicode, ascii_fallback)
# =============================================================================

_ICONS: dict[str, tuple[str, str]] = {
    # Status
    "check": ("✓", "[ok]"),
    "cross": ("✗", "[FAIL]"),
    "warn": ("⚠", "[!]"),
    "info": ("ℹ", "[i]"),  # noqa: RUF001
    "dot": ("●", "*"),
    "circle": ("○", "o"),
    "diamond": ("◆", "*"),
    "star": ("★", "*"),
    "heart": ("♥", "<3"),
    "flag": ("⚑", "[F]"),
    # Arrows
    "arrow_r": ("→", "->"),
    "arrow_l": ("←", "<-"),
    "arrow_u": ("↑", "^"),
    "arrow_d": ("↓", "v"),
    "fat_arrow": ("⇒", "=>"),
    "ret": ("↵", "<-'"),
    # Progress / activity
    "play": ("▶", ">"),
    "pause": ("⏸", "||"),
    "stop": ("■", "[]"),
    "record": ("⏺", "(o)"),
    "reload": ("⟳", "(R)"),
    "ellipsis": ("…", "..."),
    # Bullets / list markers
    "bullet": ("•", "*"),
    "dash": ("–", "-"),  # noqa: RUF001
    "tri_r": ("▸", ">"),
    "tri_d": ("▾", "v"),
    # Misc
    "lock": ("🔒", "[L]"),
    "unlock": ("🔓", "[U]"),
    "key": ("🔑", "[K]"),
    "link": ("🔗", "[~]"),
    "clip": ("📎", "[@]"),
    "folder": ("📁", "[D]"),
    "file": ("📄", "[F]"),
    "gear": ("⚙", "[G]"),
    "spark": ("✦", "*"),
    "zap": ("⚡", "!"),
}


# =============================================================================
# IconSet Proxy
# =============================================================================


class IconSet:
    """Proxy object for accessing terminal icons from templates.

    Attribute access returns a ``Styled`` string containing either the Unicode
    symbol or its ASCII fallback, depending on the ``unicode`` flag.

    Args:
        unicode: When True, return Unicode symbols; when False, ASCII fallbacks.

    Example:
        >>> icons = IconSet(unicode=True)
        >>> icons.check
        Styled('✓')
        >>> icons = IconSet(unicode=False)
        >>> icons.check
        Styled('[ok]')
    """

    __slots__ = ("_unicode",)

    def __init__(self, *, unicode: bool = True) -> None:
        object.__setattr__(self, "_unicode", unicode)

    def __getattr__(self, name: str) -> Styled:
        pair = _ICONS.get(name)
        if pair is None:
            msg = f"Unknown icon {name!r}"
            close = get_close_matches(name, _ICONS.keys(), n=3, cutoff=0.6)
            if close:
                msg += f"; did you mean {', '.join(repr(c) for c in close)}?"
            raise AttributeError(msg)
        idx = 0 if self._unicode else 1
        return Styled(pair[idx])

    def __repr__(self) -> str:
        return f"IconSet(unicode={self._unicode})"


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    "IconSet",
]
