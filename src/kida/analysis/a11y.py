"""Accessibility linting for Kida templates.

Static analysis to detect common accessibility issues:
- ``<img>`` without ``alt`` attribute
- ``<input>``/``<select>``/``<textarea>`` without associated ``<label>`` or ``aria-label``
- Heading hierarchy violations (skipping levels)
- Missing ``lang`` attribute on ``<html>``

Usage::

    from kida.analysis.a11y import check_a11y
    issues = check_a11y(template_ast)
    for issue in issues:
        print(f"Line {issue.lineno}: [{issue.rule}] {issue.message}")

"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from kida.analysis.node_visitor import NodeVisitor

if TYPE_CHECKING:
    from kida.nodes import Data, Output, Template


@dataclass(frozen=True, slots=True)
class A11yIssue:
    """A single accessibility finding."""

    lineno: int
    col_offset: int
    rule: str  # e.g. "img-alt", "heading-order"
    message: str
    severity: str = "warning"  # "warning" | "error"


# Regex patterns for HTML tag detection in Data nodes
_IMG_RE = re.compile(r"<img\b([^>]*)(?:/>|>)", re.IGNORECASE | re.DOTALL)
_A_OPEN_RE = re.compile(r"<a\b([^>]*)>", re.IGNORECASE | re.DOTALL)
_INPUT_RE = re.compile(r"<(input|select|textarea)\b([^>]*)(?:/>|>)", re.IGNORECASE | re.DOTALL)
_HEADING_RE = re.compile(r"<h([1-6])\b", re.IGNORECASE)
_HTML_RE = re.compile(r"<html\b([^>]*)>", re.IGNORECASE | re.DOTALL)

# Attribute patterns
_ALT_ATTR_RE = re.compile(r"""\balt\s*=\s*(?:"[^"]*"|'[^']*')""", re.IGNORECASE)
_ALT_EMPTY_RE = re.compile(r"""\balt\s*=\s*(?:""|'')""", re.IGNORECASE)
_ARIA_LABEL_RE = re.compile(r"""\baria-label(?:ledby)?\s*=\s*(?:"[^"]*"|'[^']*')""", re.IGNORECASE)
_ROLE_IMG_RE = re.compile(r"""\brole\s*=\s*["'](?:presentation|none)["']""", re.IGNORECASE)
_LANG_RE = re.compile(r"""\blang\s*=\s*(?:"[^"]*"|'[^']*')""", re.IGNORECASE)
_ID_ATTR_RE = re.compile(r"""\bid\s*=\s*["']([^"']*)["']""", re.IGNORECASE)
_FOR_ATTR_RE = re.compile(r"""\bfor\s*=\s*["']([^"']*)["']""", re.IGNORECASE)
_LABEL_RE = re.compile(r"<label\b([^>]*)>", re.IGNORECASE | re.DOTALL)
_TITLE_ATTR_RE = re.compile(r"""\btitle\s*=\s*(?:"[^"]*"|'[^']*')""", re.IGNORECASE)


class _A11yVisitor(NodeVisitor):
    """AST visitor that collects accessibility issues."""

    def __init__(self) -> None:
        self.issues: list[A11yIssue] = []
        self._heading_levels: list[int] = []
        self._label_for_ids: set[str] = set()
        self._input_ids: list[tuple[int, int, str]] = []  # (lineno, col, id)

    def visit_Data(self, node: Data) -> None:  # noqa: N802
        self._check_img_alt(node)
        self._check_headings(node)
        self._check_html_lang(node)
        self._collect_labels(node)
        self._collect_inputs(node)

    def visit_Output(self, node: Output) -> None:  # noqa: N802
        pass  # Output nodes are dynamic — can't statically lint

    def _check_img_alt(self, node: Data) -> None:
        """Check <img> tags have alt attributes."""
        for m in _IMG_RE.finditer(node.value):
            attrs = m.group(1)
            # Skip decorative images (role="presentation" or role="none")
            if _ROLE_IMG_RE.search(attrs):
                continue
            if not _ALT_ATTR_RE.search(attrs):
                # Check for dynamic alt via template expression ({{ ... }})
                # This is in a Data node, so no dynamic attrs — it's missing
                lineno = node.lineno + node.value[: m.start()].count("\n")
                self.issues.append(
                    A11yIssue(
                        lineno=lineno,
                        col_offset=node.col_offset,
                        rule="img-alt",
                        message="<img> missing alt attribute",
                        severity="error",
                    )
                )

    def _check_headings(self, node: Data) -> None:
        """Check heading hierarchy (no skipping levels)."""
        for m in _HEADING_RE.finditer(node.value):
            level = int(m.group(1))
            if self._heading_levels:
                last = self._heading_levels[-1]
                if level > last + 1:
                    lineno = node.lineno + node.value[: m.start()].count("\n")
                    self.issues.append(
                        A11yIssue(
                            lineno=lineno,
                            col_offset=node.col_offset,
                            rule="heading-order",
                            message=f"Heading level skipped: <h{level}> after <h{last}> (expected <h{last + 1}>)",
                        )
                    )
            self._heading_levels.append(level)

    def _check_html_lang(self, node: Data) -> None:
        """Check <html> tag has lang attribute."""
        for m in _HTML_RE.finditer(node.value):
            attrs = m.group(1)
            if not _LANG_RE.search(attrs):
                lineno = node.lineno + node.value[: m.start()].count("\n")
                self.issues.append(
                    A11yIssue(
                        lineno=lineno,
                        col_offset=node.col_offset,
                        rule="html-lang",
                        message="<html> missing lang attribute",
                    )
                )

    def _collect_labels(self, node: Data) -> None:
        """Collect label for= IDs for input association checking."""
        for m in _LABEL_RE.finditer(node.value):
            attrs = m.group(1)
            for_match = _FOR_ATTR_RE.search(attrs)
            if for_match:
                self._label_for_ids.add(for_match.group(1))

    def _collect_inputs(self, node: Data) -> None:
        """Collect input/select/textarea elements for label association."""
        for m in _INPUT_RE.finditer(node.value):
            tag = m.group(1).lower()
            attrs = m.group(2)
            # Skip if has aria-label/aria-labelledby
            if _ARIA_LABEL_RE.search(attrs):
                continue
            # Skip if has title (sometimes acceptable)
            if _TITLE_ATTR_RE.search(attrs):
                continue
            # Skip hidden inputs
            if tag == "input" and re.search(r'\btype\s*=\s*["\']hidden["\']', attrs, re.IGNORECASE):
                continue
            lineno = node.lineno + node.value[: m.start()].count("\n")
            id_match = _ID_ATTR_RE.search(attrs)
            input_id = id_match.group(1) if id_match else ""
            self._input_ids.append((lineno, node.col_offset, input_id))

    def finalize(self) -> None:
        """Post-traversal checks (e.g., input-label association)."""
        for lineno, col, input_id in self._input_ids:
            if not input_id or input_id not in self._label_for_ids:
                self.issues.append(
                    A11yIssue(
                        lineno=lineno,
                        col_offset=col,
                        rule="input-label",
                        message="Form element missing associated <label> or aria-label",
                    )
                )


def check_a11y(template: Template) -> list[A11yIssue]:
    """Run accessibility checks on a parsed template AST.

    Args:
        template: Parsed Template AST node.

    Returns:
        List of A11yIssue findings, sorted by line number.
    """
    visitor = _A11yVisitor()
    visitor.visit(template)
    visitor.finalize()
    return sorted(visitor.issues, key=lambda i: (i.lineno, i.col_offset))
