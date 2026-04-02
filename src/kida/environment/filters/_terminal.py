"""Terminal style, layout, and data-rendering filters for Kida templates.

Provides ANSI color/decoration filters, layout helpers (pad, table, tree),
and data-display filters (badge, bar, kv) for terminal-mode output.

All style filters return ``Styled`` strings. The ``make_terminal_filters``
factory produces a filter dict with closures bound to the caller's
color/unicode capabilities.
"""

from __future__ import annotations

import difflib
from typing import Any

from kida.utils.ansi_width import (
    ansi_center,
    ansi_ljust,
    ansi_rjust,
    visible_len,
)
from kida.utils.terminal_boxes import _STYLES, BoxChars
from kida.utils.terminal_escape import Styled, ansi_sanitize

# =============================================================================
# ANSI SGR Code Tables
# =============================================================================

_FG_CODES: dict[str, int] = {
    "black": 30,
    "red": 31,
    "green": 32,
    "yellow": 33,
    "blue": 34,
    "magenta": 35,
    "cyan": 36,
    "white": 37,
    "bright_red": 91,
    "bright_green": 92,
    "bright_yellow": 93,
    "bright_blue": 94,
    "bright_magenta": 95,
    "bright_cyan": 96,
}

_DECO_CODES: dict[str, int] = {
    "bold": 1,
    "dim": 2,
    "italic": 3,
    "underline": 4,
    "blink": 5,
    "inverse": 7,
    "strike": 9,
}

_RESET = "\033[0m"

# =============================================================================
# Badge Status Mapping
# =============================================================================

_BADGE_MAP: dict[str, tuple[str, str, str, str]] = {
    # key -> (unicode_icon, ascii_icon, color_name, ascii_label)
    "pass": ("check", "check", "green", "PASS"),
    "success": ("check", "check", "green", "PASS"),
    "ok": ("check", "check", "green", "OK"),
    "fail": ("cross", "cross", "red", "FAIL"),
    "error": ("cross", "cross", "red", "ERROR"),
    "failed": ("cross", "cross", "red", "FAIL"),
    "warn": ("warn", "warn", "yellow", "WARN"),
    "warning": ("warn", "warn", "yellow", "WARN"),
    "skip": ("circle", "circle", "dim", "SKIP"),
    "skipped": ("circle", "circle", "dim", "SKIP"),
    "info": ("info", "info", "blue", "INFO"),
}

# Unicode / ASCII icon pairs (duplicated from terminal_icons to avoid
# coupling the filter to IconSet at runtime).
_ICON_CHARS: dict[str, tuple[str, str]] = {
    "check": ("\u2713", "[ok]"),
    "cross": ("\u2717", "[FAIL]"),
    "warn": ("\u26a0", "[!]"),
    "info": ("\u2139", "[i]"),
    "circle": ("\u25cb", "o"),
}


# =============================================================================
# Helpers
# =============================================================================


def _sgr(code: int, text: str) -> Styled:
    """Wrap *text* in an SGR escape pair and return as Styled."""
    return Styled(f"\033[{code}m{ansi_sanitize(text)}{_RESET}")


def _parse_color_arg(color: Any) -> tuple[str, int | tuple[int, int, int]]:
    """Parse a color argument into a mode and value.

    Returns:
        ("256", n) for int 0-255
        ("rgb", (r, g, b)) for hex string or 3-int tuple/list
    """
    if isinstance(color, int):
        return ("256", color)
    if isinstance(color, (list, tuple)) and len(color) == 3:
        return ("rgb", (int(color[0]), int(color[1]), int(color[2])))
    if isinstance(color, str):
        s = color.strip().lstrip("#")
        # Check for named color first
        lower = s.lower()
        if lower in _FG_CODES:
            return ("sgr", _FG_CODES[lower])
        if len(s) == 6:
            r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
            return ("rgb", (r, g, b))
        # Try as integer string
        return ("256", int(s))
    raise ValueError(f"Invalid color value: {color!r}")


# =============================================================================
# Factory
# =============================================================================


def make_terminal_filters(
    color: bool = True,
    unicode: bool = True,
    color_depth: str | None = None,
) -> dict[str, Any]:
    """Build terminal filter dict with closures bound to capability flags.

    Args:
        color: Whether ANSI color codes should be emitted.
        unicode: Whether Unicode box-drawing / icon characters are available.
        color_depth: Terminal color depth: ``"none"``, ``"basic"``, ``"256"``,
            or ``"truecolor"``.  When provided, ``fg()`` and ``bg()`` degrade
            gracefully — e.g. RGB values are mapped to the nearest 256-color
            or basic-16 code when the terminal doesn't support truecolor.
            If *None*, falls back to ``"truecolor"`` when *color* is True.

    Returns:
        Dict mapping filter name to callable, ready for environment registration.
    """
    # Resolve color_depth from the bool flag if not explicitly provided
    if color_depth is None:
        color_depth = "truecolor" if color else "none"
    color = color_depth != "none"

    filters: dict[str, Any] = {}

    # -----------------------------------------------------------------
    # Foreground color filters
    # -----------------------------------------------------------------
    for name, code in _FG_CODES.items():
        if color:
            _code = code  # capture

            def _fg_filter(value: Any, *, _c: int = _code) -> Styled:
                return _sgr(_c, str(value))

            filters[name] = _fg_filter
        else:

            def _fg_noop(value: Any) -> Styled:
                return Styled(ansi_sanitize(value))

            filters[name] = _fg_noop

    # -----------------------------------------------------------------
    # Decoration filters
    # -----------------------------------------------------------------
    for name, code in _DECO_CODES.items():
        if color:
            _code = code

            def _deco_filter(value: Any, *, _c: int = _code) -> Styled:
                return _sgr(_c, str(value))

            filters[name] = _deco_filter
        else:

            def _deco_noop(value: Any) -> Styled:
                return Styled(ansi_sanitize(value))

            filters[name] = _deco_noop

    # -----------------------------------------------------------------
    # Extended color: fg / bg (with color depth fallback)
    # -----------------------------------------------------------------
    _depth = color_depth  # capture for closures

    if color:
        from kida.utils.color_convert import (
            index256_to_basic_fg,
            rgb_to_256,
            rgb_to_basic_fg,
        )

        def _filter_fg(value: Any, color_arg: Any) -> Styled:
            mode, val = _parse_color_arg(color_arg)
            s = ansi_sanitize(value)

            if mode == "sgr":
                # Named colors always work at basic depth
                return Styled(f"\033[{val}m{s}{_RESET}")

            if mode == "rgb":
                r, g, b = val  # type: ignore[misc]
                if _depth == "truecolor":
                    return Styled(f"\033[38;2;{r};{g};{b}m{s}{_RESET}")
                if _depth == "256":
                    return Styled(f"\033[38;5;{rgb_to_256(r, g, b)}m{s}{_RESET}")
                # basic — map to nearest 16-color
                return Styled(f"\033[{rgb_to_basic_fg(r, g, b)}m{s}{_RESET}")

            # mode == "256"
            assert isinstance(val, int)
            if _depth in ("truecolor", "256"):
                return Styled(f"\033[38;5;{val}m{s}{_RESET}")
            # basic — map 256 index to nearest 16-color
            return Styled(f"\033[{index256_to_basic_fg(val)}m{s}{_RESET}")

        def _filter_bg(value: Any, color_arg: Any) -> Styled:
            mode, val = _parse_color_arg(color_arg)
            s = ansi_sanitize(value)

            if mode == "sgr":
                assert isinstance(val, int)
                return Styled(f"\033[{val + 10}m{s}{_RESET}")

            if mode == "rgb":
                r, g, b = val  # type: ignore[misc]
                if _depth == "truecolor":
                    return Styled(f"\033[48;2;{r};{g};{b}m{s}{_RESET}")
                if _depth == "256":
                    return Styled(f"\033[48;5;{rgb_to_256(r, g, b)}m{s}{_RESET}")
                # basic — map to nearest 16-color bg (fg code + 10)
                return Styled(f"\033[{rgb_to_basic_fg(r, g, b) + 10}m{s}{_RESET}")

            # mode == "256"
            assert isinstance(val, int)
            if _depth in ("truecolor", "256"):
                return Styled(f"\033[48;5;{val}m{s}{_RESET}")
            # basic — map 256 index to nearest 16-color bg
            return Styled(f"\033[{index256_to_basic_fg(val) + 10}m{s}{_RESET}")

    else:

        def _filter_fg(value: Any, color_arg: Any) -> Styled:
            return Styled(ansi_sanitize(value))

        def _filter_bg(value: Any, color_arg: Any) -> Styled:
            return Styled(ansi_sanitize(value))

    filters["fg"] = _filter_fg
    filters["bg"] = _filter_bg

    # -----------------------------------------------------------------
    # Layout: pad
    # -----------------------------------------------------------------
    def _filter_pad(
        value: Any,
        width: int,
        align: str = "left",
        fill: str = " ",
    ) -> Styled:
        s = str(value)
        if align == "right":
            return Styled(ansi_rjust(s, width, fill))
        if align == "center":
            return Styled(ansi_center(s, width, fill))
        return Styled(ansi_ljust(s, width, fill))

    filters["pad"] = _filter_pad

    # -----------------------------------------------------------------
    # Data: badge
    # -----------------------------------------------------------------
    def _filter_badge(
        value: Any,
        icon: str | None = None,
        badge_color: str | None = None,
    ) -> Styled:
        key = str(value).lower().strip()
        mapping = _BADGE_MAP.get(key)

        if mapping is not None:
            icon_name, _, color_name, ascii_label = mapping
            if not color:
                return Styled(f"[{ascii_label}]")
            # Pick icon character
            pair = _ICON_CHARS.get(icon_name, ("?", "?"))
            ic = pair[0] if unicode else pair[1]
            # Apply color
            if color_name in _FG_CODES:
                code = _FG_CODES[color_name]
                return Styled(f"\033[{code}m{ic}{_RESET}")
            if color_name == "dim":
                return Styled(f"\033[2m{ic}{_RESET}")
            return Styled(ic)

        # Unknown status: use provided icon/color or plain text
        text = ansi_sanitize(value)
        if icon:
            pair = _ICON_CHARS.get(icon)
            text = (pair[0] if unicode else pair[1]) + " " + text if pair else f"{icon} {text}"
        if badge_color and color and badge_color in _FG_CODES:
            code = _FG_CODES[badge_color]
            return Styled(f"\033[{code}m{text}{_RESET}")
        return Styled(text)

    filters["badge"] = _filter_badge

    # -----------------------------------------------------------------
    # Data: bar
    # -----------------------------------------------------------------
    def _filter_bar(
        value: Any,
        width: int = 20,
        show_pct: bool = True,
    ) -> Styled:
        pct = max(0.0, min(1.0, float(value)))
        filled = int(pct * width)
        empty = width - filled

        if unicode:
            bar = "\u2588" * filled + "\u2591" * empty
        else:
            bar = "#" * filled + "-" * empty
            bar = f"[{bar}]"

        if show_pct:
            bar += f" {int(pct * 100)}%"
        return Styled(bar)

    filters["bar"] = _filter_bar

    # -----------------------------------------------------------------
    # Data: kv
    # -----------------------------------------------------------------
    def _filter_kv(
        label: Any,
        value: Any,
        width: int = 40,
        sep: str = " ",
        fill: str = "\u00b7",
    ) -> Styled:
        lbl = ansi_sanitize(label)
        val = ansi_sanitize(value)
        lbl_len = visible_len(lbl)
        val_len = visible_len(val)
        sep_len = len(sep)
        fill_count = max(1, width - lbl_len - val_len - sep_len * 2)
        if not unicode and fill == "\u00b7":
            fill = "."
        return Styled(f"{lbl}{sep}{fill * fill_count}{sep}{val}")

    filters["kv"] = _filter_kv

    # -----------------------------------------------------------------
    # Data: table
    # -----------------------------------------------------------------
    def _filter_table(
        data: Any,
        headers: list[str] | None = None,
        border: str = "light",
        align: dict[str, str] | None = None,
        max_width: int | None = None,
    ) -> Styled:
        data = list(data)
        if not data:
            return Styled("")

        rows: list[list[str]]
        col_names: list[str]

        # Normalise input and compute column widths in merged passes
        if isinstance(data[0], dict):
            if headers is None:
                seen: dict[str, None] = {}
                for row in data:
                    for k in row:
                        seen.setdefault(k, None)
                col_names = list(seen)
            else:
                col_names = headers
            rows = [[str(row.get(c, "")) for c in col_names] for row in data]
        else:
            col_names = [f"col{i}" for i in range(len(data[0]))] if headers is None else headers
            rows = [[str(cell) for cell in row] for row in data]

        num_cols = len(col_names)

        # Compute column widths (merged with row iteration)
        col_widths = [visible_len(c) for c in col_names]
        for row in rows:
            for i in range(min(len(row), num_cols)):
                w = visible_len(row[i])
                if w > col_widths[i]:
                    col_widths[i] = w

        # Apply max_width constraint
        if max_width is not None:
            box = _get_box(border, unicode)
            # overhead: border chars + padding
            overhead = (num_cols + 1) + (num_cols * 2)  # │ + spaces
            available = max_width - overhead
            if available > 0:
                total = sum(col_widths)
                if total > available:
                    ratio = available / total
                    col_widths = [max(1, int(w * ratio)) for w in col_widths]

        # Resolve alignment
        align_map = align or {}
        col_aligns: list[str] = [align_map.get(c, "left") for c in col_names]

        box = _get_box(border, unicode)
        lines: list[str] = []

        def _pad_cell(text: str, width: int, alignment: str) -> str:
            if alignment == "right":
                return ansi_rjust(text, width)
            if alignment == "center":
                return ansi_center(text, width)
            return ansi_ljust(text, width)

        def _row_line(cells: list[str]) -> str:
            parts = [
                f" {_pad_cell(cells[i], col_widths[i], col_aligns[i])} " for i in range(num_cols)
            ]
            return box.v + box.v.join(parts) + box.v

        def _rule(left: str, mid: str, right: str) -> str:
            segs = [box.h * (w + 2) for w in col_widths]
            return left + mid.join(segs) + right

        # Top border
        lines.append(_rule(box.tl, box.tj, box.tr))
        # Header
        lines.append(_row_line(col_names))
        # Header separator
        lines.append(_rule(box.lj, box.cross, box.rj))
        # Data rows
        for row in rows:
            # Pad row to num_cols
            padded = row + [""] * (num_cols - len(row))
            lines.append(_row_line(padded))
        # Bottom border
        lines.append(_rule(box.bl, box.bj, box.br))

        return Styled("\n".join(lines))

    filters["table"] = _filter_table

    # -----------------------------------------------------------------
    # Data: tree
    # -----------------------------------------------------------------
    def _filter_tree(data: Any, indent: int = 2) -> Styled:
        if not isinstance(data, dict):
            return Styled(str(data))

        if unicode:
            branch = "\u251c" + "\u2500" * (indent - 1) + " "
            last_branch = "\u2514" + "\u2500" * (indent - 1) + " "
            pipe = "\u2502" + " " * indent
            space = " " * (indent + 1)
        else:
            branch = "|" + "-" * (indent - 1) + " "
            last_branch = "\\" + "-" * (indent - 1) + " "
            pipe = "|" + " " * indent
            space = " " * (indent + 1)

        lines: list[str] = []

        def _walk(node: dict[str, Any], prefix: str) -> None:
            entries = list(node.items())
            for i, (key, val) in enumerate(entries):
                is_last = i == len(entries) - 1
                connector = last_branch if is_last else branch
                lines.append(f"{prefix}{connector}{key}")
                if isinstance(val, dict) and val:
                    extension = space if is_last else pipe
                    _walk(val, prefix + extension)

        _walk(data, "")
        return Styled("\n".join(lines))

    filters["tree"] = _filter_tree

    # -----------------------------------------------------------------
    # Data: diff
    # -----------------------------------------------------------------
    def _filter_diff(old: Any, new: Any, context: int = 3) -> Styled:
        old_lines = str(old).splitlines(keepends=True)
        new_lines = str(new).splitlines(keepends=True)
        diff_lines = list(difflib.unified_diff(old_lines, new_lines, n=context, lineterm=""))
        if not diff_lines:
            return Styled("")

        result: list[str] = []
        for line in diff_lines:
            # Strip trailing newline for consistent output
            line = line.rstrip("\n")
            if line.startswith(("+++", "---")):
                if color:
                    result.append(f"\033[2m{line}{_RESET}")
                else:
                    result.append(line)
            elif line.startswith("@@"):
                if color:
                    result.append(f"\033[36m{line}{_RESET}")
                else:
                    result.append(line)
            elif line.startswith("+"):
                if color:
                    result.append(f"\033[32m+ {line[1:]}{_RESET}")
                else:
                    result.append(f"+ {line[1:]}")
            elif line.startswith("-"):
                if color:
                    result.append(f"\033[31m- {line[1:]}{_RESET}")
                else:
                    result.append(f"- {line[1:]}")
            else:
                if color:
                    result.append(f"\033[2m  {line}{_RESET}")
                else:
                    result.append(f"  {line}")
        return Styled("\n".join(result))

    filters["diff"] = _filter_diff

    return filters


# =============================================================================
# Internal Helpers
# =============================================================================


def _get_box(style: str, use_unicode: bool) -> BoxChars:
    """Resolve a box style name to a BoxChars instance."""
    if not use_unicode:
        return _STYLES["ascii"]
    return _STYLES.get(style, _STYLES["light"])


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    "make_terminal_filters",
]
