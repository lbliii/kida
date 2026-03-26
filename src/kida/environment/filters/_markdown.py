"""Markdown formatting filters for Kida templates.

Provides GFM text formatting, link/badge helpers, table rendering,
and layout filters for markdown-mode output.

All filters return ``Marked`` strings to preserve safety through the
template engine's autoescape pipeline.
"""

from __future__ import annotations

from typing import Any

from kida.utils.markdown_escape import Marked, markdown_escape

# =============================================================================
# Badge Emoji Mapping
# =============================================================================

_BADGE_EMOJI: dict[str, str] = {
    "pass": ":white_check_mark:",
    "success": ":white_check_mark:",
    "ok": ":white_check_mark:",
    "fail": ":x:",
    "error": ":x:",
    "failed": ":x:",
    "warn": ":warning:",
    "warning": ":warning:",
    "skip": ":heavy_minus_sign:",
    "skipped": ":heavy_minus_sign:",
    "info": ":information_source:",
}


# =============================================================================
# Factory
# =============================================================================


def make_markdown_filters() -> dict[str, Any]:
    """Build markdown filter dict.

    Returns:
        Dict mapping filter name to callable, ready for environment registration.
    """
    filters: dict[str, Any] = {}

    # -----------------------------------------------------------------
    # Text formatting
    # -----------------------------------------------------------------
    def _filter_bold(value: Any) -> Marked:
        return Marked(f"**{markdown_escape(value)}**")

    def _filter_italic(value: Any) -> Marked:
        return Marked(f"*{markdown_escape(value)}*")

    def _filter_code(value: Any) -> Marked:
        s = str(value)
        # If the value contains backticks, use double backticks with spaces
        if "`" in s:
            return Marked(f"`` {s} ``")
        return Marked(f"`{s}`")

    def _filter_strike(value: Any) -> Marked:
        return Marked(f"~~{markdown_escape(value)}~~")

    filters["bold"] = _filter_bold
    filters["italic"] = _filter_italic
    filters["code"] = _filter_code
    filters["strike"] = _filter_strike

    # -----------------------------------------------------------------
    # Links
    # -----------------------------------------------------------------
    def _filter_link(text: Any, url: str) -> Marked:
        return Marked(f"[{markdown_escape(text)}]({url})")

    filters["link"] = _filter_link

    # -----------------------------------------------------------------
    # Badges
    # -----------------------------------------------------------------
    def _filter_badge(value: Any) -> Marked:
        key = str(value).lower().strip()
        emoji = _BADGE_EMOJI.get(key, f":{key}:")
        return Marked(emoji)

    filters["badge"] = _filter_badge

    # -----------------------------------------------------------------
    # Data: table
    # -----------------------------------------------------------------
    def _filter_table(
        data: Any,
        headers: list[str] | None = None,
    ) -> Marked:
        data = list(data)
        if not data:
            return Marked("")

        col_names: list[str]

        # Normalise input
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

        lines: list[str] = []
        # Header row
        lines.append("| " + " | ".join(col_names) + " |")
        # Separator
        lines.append("| " + " | ".join("---" for _ in col_names) + " |")
        # Data rows
        for row in rows:
            # Escape pipe chars in cell content
            escaped = [cell.replace("|", "\\|") for cell in row]
            lines.append("| " + " | ".join(escaped) + " |")

        return Marked("\n".join(lines))

    filters["table"] = _filter_table

    # -----------------------------------------------------------------
    # Data: codeblock
    # -----------------------------------------------------------------
    def _filter_codeblock(value: Any, lang: str = "") -> Marked:
        s = str(value)
        return Marked(f"```{lang}\n{s}\n```")

    filters["codeblock"] = _filter_codeblock

    # -----------------------------------------------------------------
    # Layout: details
    # -----------------------------------------------------------------
    def _filter_details(value: Any, summary: str = "Details") -> Marked:
        s = str(value)
        return Marked(
            f"<details>\n<summary>{markdown_escape(summary)}</summary>\n\n{s}\n\n</details>"
        )

    filters["details"] = _filter_details

    # -----------------------------------------------------------------
    # Headings
    # -----------------------------------------------------------------
    def _filter_h1(value: Any) -> Marked:
        return Marked(f"# {markdown_escape(value)}")

    def _filter_h2(value: Any) -> Marked:
        return Marked(f"## {markdown_escape(value)}")

    def _filter_h3(value: Any) -> Marked:
        return Marked(f"### {markdown_escape(value)}")

    def _filter_h4(value: Any) -> Marked:
        return Marked(f"#### {markdown_escape(value)}")

    filters["h1"] = _filter_h1
    filters["h2"] = _filter_h2
    filters["h3"] = _filter_h3
    filters["h4"] = _filter_h4

    return filters


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    "make_markdown_filters",
]
