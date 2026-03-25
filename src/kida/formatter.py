"""Opinionated template formatter for Kida.

Auto-formats Kida templates with consistent whitespace, indentation,
and tag spacing. No other Python template engine has a formatter.

Rules:
- Consistent spacing inside tags: ``{% if x %}`` not ``{%if x%}``
- Consistent spacing in output: ``{{ expr }}`` not ``{{expr}}``
- Indent block bodies by configured amount (default 2 spaces)
- Normalize blank lines (max 1 consecutive)
- Trim trailing whitespace
- Ensure final newline

Usage::

    from kida.formatter import format_template
    formatted = format_template(source)

CLI::

    kida fmt templates/

"""

from __future__ import annotations

import re

# Tag patterns for spacing normalization
_BLOCK_TAG_RE = re.compile(r"\{%-?\s*(.*?)\s*-?%\}", re.DOTALL)
_VAR_TAG_RE = re.compile(r"\{\{-?\s*(.*?)\s*-?\}\}", re.DOTALL)
_COMMENT_TAG_RE = re.compile(r"\{#-?\s*(.*?)\s*-?#\}", re.DOTALL)

# Detect block-opening keywords
_BLOCK_OPEN_KEYWORDS = frozenset(
    {
        "if",
        "for",
        "block",
        "while",
        "with",
        "def",
        "region",
        "call",
        "capture",
        "cache",
        "filter",
        "match",
        "spaceless",
        "embed",
        "raw",
        "push",
        "globals",
        "imports",
        "unless",
        "fragment",
    }
)

# Continuation keywords (same indent as parent)
_CONTINUATION_KEYWORDS = frozenset({"else", "elif", "empty", "case"})

# Closing keywords
_END_KEYWORDS_RE = re.compile(
    r"^end(?:if|for|block|while|with|def|region|call|capture|cache|filter|match|spaceless|embed|raw|push|globals|imports|unless|fragment)?$"
)

# Whitespace control markers
_WS_STRIP_OPEN = re.compile(r"\{%-")
_WS_STRIP_CLOSE = re.compile(r"-%\}")
_WS_STRIP_VAR_OPEN = re.compile(r"\{\{-")
_WS_STRIP_VAR_CLOSE = re.compile(r"-\}\}")


def format_template(
    source: str,
    *,
    indent: int = 2,
    max_blank_lines: int = 1,
    normalize_tag_spacing: bool = True,
) -> str:
    """Format a Kida template source string.

    Args:
        source: Template source text.
        indent: Number of spaces per indentation level.
        max_blank_lines: Maximum consecutive blank lines to allow.
        normalize_tag_spacing: If True, normalize spacing inside tags.

    Returns:
        Formatted template source.
    """
    if normalize_tag_spacing:
        source = _normalize_tag_spacing(source)

    lines = source.split("\n")
    result: list[str] = []
    current_indent = 0
    blank_count = 0

    for line in lines:
        stripped = line.strip()

        # Handle blank lines
        if not stripped:
            blank_count += 1
            if blank_count <= max_blank_lines:
                result.append("")
            continue
        blank_count = 0

        # Determine indent adjustment BEFORE this line
        dedent_this = _should_dedent_before(stripped)
        if dedent_this:
            current_indent = max(0, current_indent - 1)

        # Apply indentation
        indent_str = " " * (indent * current_indent)
        formatted = indent_str + stripped

        # Trim trailing whitespace
        result.append(formatted.rstrip())

        # Determine indent adjustment AFTER this line
        indent_after = _count_indent_change(stripped)
        current_indent = max(0, current_indent + indent_after)

    # Ensure final newline
    text = "\n".join(result)
    if text and not text.endswith("\n"):
        text += "\n"
    return text


def _normalize_tag_spacing(source: str) -> str:
    """Normalize spacing inside template tags."""

    # Normalize block tags: {%  if x  %} → {% if x %}
    def _fix_block(m: re.Match[str]) -> str:
        content = m.group(1).strip()
        # Preserve whitespace control markers
        original = m.group(0)
        prefix = "{%- " if original.startswith("{%-") else "{% "
        suffix = " -%}" if original.endswith("-%}") else " %}"
        return prefix + content + suffix

    source = _BLOCK_TAG_RE.sub(_fix_block, source)

    # Normalize variable tags: {{  expr  }} → {{ expr }}
    def _fix_var(m: re.Match[str]) -> str:
        content = m.group(1).strip()
        original = m.group(0)
        prefix = "{{- " if original.startswith("{{-") else "{{ "
        suffix = " -}}" if original.endswith("-}}") else " }}"
        return prefix + content + suffix

    source = _VAR_TAG_RE.sub(_fix_var, source)

    # Normalize comment tags
    def _fix_comment(m: re.Match[str]) -> str:
        content = m.group(1).strip()
        original = m.group(0)
        prefix = "{#- " if original.startswith("{#-") else "{# "
        suffix = " -#}" if original.endswith("-#}") else " #}"
        return prefix + content + suffix

    source = _COMMENT_TAG_RE.sub(_fix_comment, source)
    return source


def _get_block_keyword(line: str) -> str | None:
    """Extract the block keyword from a line containing a block tag."""
    m = re.search(r"\{%-?\s*(\w+)", line)
    if m:
        return m.group(1)
    return None


def _should_dedent_before(stripped: str) -> bool:
    """Check if this line should be dedented (closing/continuation tags)."""
    kw = _get_block_keyword(stripped)
    if kw is None:
        return False
    return kw in _CONTINUATION_KEYWORDS or bool(_END_KEYWORDS_RE.match(kw))


def _count_indent_change(stripped: str) -> int:
    """Count net indent change for this line.

    Returns +1 for block openers, -1 for closers that also re-indent
    (like else which dedents then indents).
    """
    kw = _get_block_keyword(stripped)
    if kw is None:
        return 0

    # Continuation keywords: dedented before, indent after
    if kw in _CONTINUATION_KEYWORDS:
        return 1

    # Opening keywords
    if kw in _BLOCK_OPEN_KEYWORDS:
        # Check if the block also closes on same line (self-closing)
        if _END_KEYWORDS_RE.search(
            stripped.split("{%")[-1].split("%}")[0].strip()
            if "{%" in stripped.split("{%", 1)[-1]
            else ""
        ):
            return 0
        return 1

    # End keywords were handled in dedent_before, but they don't indent after
    if _END_KEYWORDS_RE.match(kw):
        return 0

    return 0
