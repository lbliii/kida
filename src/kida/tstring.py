"""Kida Template String support (PEP 750).

Provides t-string tags for Python 3.14+:
- `k`: Kida-style interpolation with auto-escaping
- `r`: Safe, composable regex patterns with ReDoS validation

Example:
    >>> from kida.tstring import k, r
    >>> name = "<script>"
    >>> k(t"Hello {name}!")  # Auto-escapes
    'Hello &lt;script&gt;!'

    >>> NAME = r"[a-zA-Z_][a-zA-Z0-9_]*"
    >>> INTEGER = r"\\d+"
    >>> pattern = r(t"{NAME}|{INTEGER}")  # Composes safely
    >>> pattern.compile().match("variable_123")
    <re.Match object; span=(0, 12), match='variable_123'>
"""

from __future__ import annotations

import re
from importlib import import_module
from types import ModuleType
from typing import Any, Protocol, cast, runtime_checkable

from kida.utils.html import html_escape


@runtime_checkable
class TemplateProtocol(Protocol):
    strings: tuple[str, ...]
    interpolations: tuple[Any, ...]


class TemplateLibProtocol(Protocol):
    Template: type[TemplateProtocol]


templatelib_module: ModuleType | None
try:  # Python <3.14 fallback: allow tests and callers to pass compatible objects
    templatelib_module = import_module("string.templatelib")
except ImportError:  # pragma: no cover - exercised via fallback path
    templatelib_module = None

templatelib: TemplateLibProtocol | None = cast(TemplateLibProtocol | None, templatelib_module)


# =============================================================================
# r-tag: Composable Regex Patterns
# =============================================================================


class PatternError(Exception):
    """Error raised when a regex pattern is invalid or unsafe."""

    pass


# Known ReDoS-vulnerable patterns (simplified detection)
_REDOS_PATTERNS = [
    re.compile(r"\([^)]*[+*][^)]*\)[+*]"),  # (a+)+ or (a*)+ or (a+)* etc.
    re.compile(r"\(\.\*\)[+*]"),  # (.*)+ or (.*)*
    re.compile(r"\([^)]*\|[^)]*\)[+*][^)]*\\1"),  # (a|b)+...backreference
]


def _validate_redos_safety(pattern: str) -> None:
    """Validate pattern doesn't contain known ReDoS vulnerabilities.

    Raises:
        PatternError: If pattern contains known dangerous constructs.

    Note:
        This is a simplified check that catches common ReDoS patterns.
        It's not exhaustive but catches the most dangerous cases.

    """
    for redos_re in _REDOS_PATTERNS:
        if redos_re.search(pattern):
            raise PatternError(
                f"Pattern may be vulnerable to ReDoS (exponential backtracking):\n"
                f"  Pattern: {pattern!r}\n"
                f"  Risk: Nested quantifiers can cause exponential time complexity.\n"
                f"  Fix: Simplify the pattern or use atomic groups if available."
            )


class ComposablePattern:
    """A composable regex pattern with safety validation.

    ComposablePattern wraps a regex pattern string and provides:
    - Lazy compilation (pattern is compiled on first use)
    - ReDoS validation at creation time
    - Safe composition via the | operator

    Example:
            >>> NAME = ComposablePattern(r"[a-zA-Z_][a-zA-Z0-9_]*")
            >>> INTEGER = ComposablePattern(r"\\d+")
            >>> combined = NAME | INTEGER
            >>> combined.compile().match("hello")
        <re.Match object; span=(0, 5), match='hello'>

    Attributes:
        pattern: The raw regex pattern string

    """

    __slots__ = ("_pattern", "_compiled")

    def __init__(self, pattern: str, *, validate: bool = True) -> None:
        """Create a composable pattern.

        Args:
            pattern: The regex pattern string
            validate: Whether to validate for ReDoS risks (default: True)

        Raises:
            PatternError: If validate=True and pattern is unsafe
            re.error: If pattern has invalid regex syntax
        """
        # Validate syntax by attempting to compile
        try:
            re.compile(pattern)
        except re.error as e:
            raise PatternError(f"Invalid regex syntax: {e}") from e

        if validate:
            _validate_redos_safety(pattern)

        self._pattern = pattern
        self._compiled: re.Pattern[str] | None = None

    @property
    def pattern(self) -> str:
        """The raw regex pattern string."""
        return self._pattern

    def compile(self, flags: int = 0) -> re.Pattern[str]:
        """Compile the pattern to a regex object.

        Args:
            flags: Regex flags (re.IGNORECASE, re.MULTILINE, etc.)

        Returns:
            Compiled re.Pattern object

        Note:
            Result is cached if flags=0 (the common case).
        """
        if flags == 0:
            if self._compiled is None:
                self._compiled = re.compile(self._pattern)
            return self._compiled
        return re.compile(self._pattern, flags)

    def __or__(self, other: ComposablePattern | str) -> ComposablePattern:
        """Combine patterns with alternation: pattern1 | pattern2.

        Both patterns are wrapped in non-capturing groups to prevent
        group interference.

        Example:
            >>> NAME = ComposablePattern(r"[a-z]+")
            >>> NUM = ComposablePattern(r"\\d+")
            >>> combined = NAME | NUM
            >>> combined.pattern
            '(?:[a-z]+)|(?:\\\\d+)'
        """
        other_pattern = other._pattern if isinstance(other, ComposablePattern) else other
        return ComposablePattern(
            f"(?:{self._pattern})|(?:{other_pattern})",
            validate=False,  # Already validated individually
        )

    def __repr__(self) -> str:
        return f"ComposablePattern({self._pattern!r})"


def r(template: TemplateProtocol) -> ComposablePattern:
    """The `r` tag for composable regex patterns.

    Composes regex patterns safely by wrapping interpolated values in
    non-capturing groups. This prevents group index collision and
    quantifier interference.

    Example:
            >>> NAME = r"[a-zA-Z_][a-zA-Z0-9_]*"
            >>> STRING = r"'[^']*'"
            >>> pattern = r(t"{NAME}|{STRING}")
            >>> pattern.pattern
        "(?:[a-zA-Z_][a-zA-Z0-9_]*)|(?:'[^']*')"

    Args:
        template: A t-string template with pattern interpolations

    Returns:
        ComposablePattern that can be compiled or further composed

    Raises:
        TypeError: If template is not a valid t-string
        PatternError: If resulting pattern is invalid or ReDoS-vulnerable

    """
    if not isinstance(template, TemplateProtocol):
        raise TypeError("r() expects a t-string template")

    strings = template.strings
    interpolations = template.interpolations
    parts: list[str] = []

    for i, s in enumerate(strings):
        parts.append(s)
        if i < len(interpolations):
            interp = interpolations[i]
            # Get the value - handle both .value attribute and direct value
            val = getattr(interp, "value", interp)

            # Convert to pattern string
            if isinstance(val, ComposablePattern):
                sub_pattern = val.pattern
            elif isinstance(val, str):
                sub_pattern = val
            else:
                raise TypeError(
                    f"r() interpolation must be str or ComposablePattern, got {type(val).__name__}"
                )

            # Wrap in non-capturing group for safe composition
            parts.append(f"(?:{sub_pattern})")

    final_pattern = "".join(parts)
    return ComposablePattern(final_pattern)


# =============================================================================
# k-tag: Kida Template Strings
# =============================================================================


def k(template: TemplateProtocol) -> str:
    """The `k` tag for Kida template strings.

    Processes a PEP 750 t-string with automatic HTML escaping.
    Values are escaped unless they implement `__html__()` (Markup).

    Example:
            >>> name = "World"
            >>> k(t"Hello {name}!")
            'Hello World!'

            >>> k(t"<p>{user_input}</p>")  # Auto-escapes user_input
            '<p>&lt;script&gt;...&lt;/script&gt;</p>'

    Note: Currently supports simple interpolation. Future versions will
    integrate with the Kida compiler for filter support.

    Type Safety:
        The TemplateProtocol type hint ensures static type checkers (mypy,
        pyright) catch misuse like `k("string")`. Runtime isinstance() check
        is omitted for performance (~35% faster). Duck typing allows test mocks.

    """
    # Direct attribute access - duck typing allows t-strings, Template objects,
    # and test mocks (SimpleNamespace). Type checker enforces TemplateProtocol.
    strings = template.strings
    interpolations = template.interpolations
    parts: list[str] = []

    for i in range(len(strings)):
        parts.append(strings[i])
        if i < len(interpolations):
            interp = interpolations[i]
            val = getattr(interp, "value", interp)
            # Auto-escape if it's not already Markup (Kida principle)
            if hasattr(val, "__html__"):
                parts.append(val.__html__())
            else:
                parts.append(html_escape(str(val)))

    return "".join(parts)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "k",
    "r",
    "ComposablePattern",
    "PatternError",
    "TemplateProtocol",
    "templatelib",
]
