"""HTML utilities for Kida template engine.

Provides optimized HTML escaping, the Markup safe-string class, and related utilities.
Zero external dependencies — pure Python 3.14+.

Security Hardening (RFC: Markup Security Hardening):
- NUL byte stripping in all escaping
- O(1) frozenset lookups for character classes
- Attribute name validation in xmlattr()
- Event handler attribute warnings
- Context-specific escaping (JS, CSS, URL)

All operations are O(n) single-pass with no ReDoS risk.
"""

from __future__ import annotations

import html
import re
import warnings
from collections.abc import Callable, Iterable
from typing import Any, Self, SupportsIndex, cast

# =============================================================================
# Core Escaping Infrastructure
# =============================================================================

# O(1) character class lookup (no regex in hot path)
_ESCAPE_CHARS: frozenset[str] = frozenset("&<>\"'\x00")

# Pre-compiled escape table for O(n) single-pass HTML escaping
# Includes NUL byte stripping for security
_ESCAPE_TABLE = str.maketrans(
    {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
        "\x00": "",  # Strip NUL bytes (security)
    }
)

# Pre-compiled regex for stripping HTML tags
# Note: This is for DISPLAY only, not security. See strip_tags() docstring.
_STRIPTAGS_RE = re.compile(r"<[^>]*>")

# Pre-compiled regex for removing whitespace between HTML tags
_SPACELESS_RE = re.compile(r">\s+<")

# =============================================================================
# Attribute Validation
# =============================================================================

# Valid XML/HTML attribute name pattern (O(1) validation using character sets)
# Per HTML5: attribute names are sequences of characters other than:
# - ASCII whitespace, NUL, quotes, apostrophe, >, /, =
_INVALID_ATTR_CHARS: frozenset[str] = frozenset(" \t\n\r\f\x00\"'>/=")

# Event handler attributes that can execute JavaScript
# Source: WHATWG HTML Living Standard + common SVG/MathML events
# Last updated: 2026-01
_EVENT_HANDLER_ATTRS: frozenset[str] = frozenset(
    {
        # Mouse events
        "onclick",
        "ondblclick",
        "onmousedown",
        "onmouseup",
        "onmouseover",
        "onmousemove",
        "onmouseout",
        "onmouseenter",
        "onmouseleave",
        "onwheel",
        "oncontextmenu",
        # Keyboard events
        "onkeydown",
        "onkeypress",
        "onkeyup",
        # Focus events
        "onfocus",
        "onblur",
        "onfocusin",
        "onfocusout",
        # Form events
        "onchange",
        "oninput",
        "oninvalid",
        "onreset",
        "onsubmit",
        "onformdata",
        "onselect",
        # Drag events
        "ondrag",
        "ondragend",
        "ondragenter",
        "ondragleave",
        "ondragover",
        "ondragstart",
        "ondrop",
        # Clipboard events
        "oncopy",
        "oncut",
        "onpaste",
        # Media events
        "onabort",
        "oncanplay",
        "oncanplaythrough",
        "oncuechange",
        "ondurationchange",
        "onemptied",
        "onended",
        "onerror",
        "onloadeddata",
        "onloadedmetadata",
        "onloadstart",
        "onpause",
        "onplay",
        "onplaying",
        "onprogress",
        "onratechange",
        "onseeked",
        "onseeking",
        "onstalled",
        "onsuspend",
        "ontimeupdate",
        "onvolumechange",
        "onwaiting",
        # Page/Window events
        "onload",
        "onunload",
        "onbeforeunload",
        "onresize",
        "onscroll",
        "onhashchange",
        "onpopstate",
        "onpageshow",
        "onpagehide",
        "onoffline",
        "ononline",
        "onstorage",
        "onmessage",
        "onmessageerror",
        # Print events
        "onbeforeprint",
        "onafterprint",
        # Animation events
        "onanimationstart",
        "onanimationend",
        "onanimationiteration",
        "onanimationcancel",
        # Transition events
        "ontransitionrun",
        "ontransitionstart",
        "ontransitionend",
        "ontransitioncancel",
        # Touch events
        "ontouchstart",
        "ontouchend",
        "ontouchmove",
        "ontouchcancel",
        # Pointer events
        "onpointerdown",
        "onpointerup",
        "onpointermove",
        "onpointerover",
        "onpointerout",
        "onpointerenter",
        "onpointerleave",
        "onpointercancel",
        "ongotpointercapture",
        "onlostpointercapture",
        # Other events
        "ontoggle",
        "onsearch",
        "onshow",
        "onsecuritypolicyviolation",
        "onslotchange",
        "onbeforeinput",
        "onbeforematch",
        # Deprecated but still functional
        "onmousewheel",
    }
)

# =============================================================================
# JavaScript Escaping
# =============================================================================

# JavaScript escape table (O(n) single-pass translation)
# Escapes characters that could:
# 1. Break out of string literals (\, ", ', newlines)
# 2. Break out of <script> context (<, >, /)
# 3. Break JavaScript parsing (U+2028, U+2029)
# 4. Enable template literal injection (`, $)
_JS_ESCAPE_TABLE = str.maketrans(
    {
        "\\": "\\\\",
        '"': '\\"',
        "'": "\\'",
        "`": "\\`",  # Template literal delimiter
        "$": "\\$",  # Template literal interpolation ${...}
        "\n": "\\n",
        "\r": "\\r",
        "\t": "\\t",
        "\x00": "\\x00",
        "<": "\\x3c",  # Prevent </script> breaking out
        ">": "\\x3e",
        "/": "\\/",  # Prevent </script> and <!-- -->
        "\u2028": "\\u2028",  # Line separator (breaks JS strings)
        "\u2029": "\\u2029",  # Paragraph separator
    }
)

# =============================================================================
# CSS Escaping
# =============================================================================

# CSS escape table (O(n) single-pass translation)
# Escapes characters that could break out of property values or @rules.
_CSS_ESCAPE_TABLE = str.maketrans(
    {
        "\\": "\\\\",
        '"': '\\"',
        "'": "\\'",
        "(": "\\(",
        ")": "\\)",
        "/": "\\/",
        "<": "\\3c ",
        ">": "\\3e ",
        "&": "\\26 ",
        "\x00": "",
    }
)

# =============================================================================
# URL Validation
# =============================================================================

# Safe URL schemes (frozenset for O(1) lookup)
_SAFE_SCHEMES: frozenset[str] = frozenset(
    {
        "http",
        "https",
        "mailto",
        "tel",
        "ftp",
        "ftps",
        "sms",
        # NOT included: javascript, vbscript, data (by default)
    }
)

# Relative URL prefixes (checked with startswith for efficiency)
_RELATIVE_PREFIXES: tuple[str, ...] = ("/", "./", "../", "#", "?")


# =============================================================================
# Markup Class
# =============================================================================


class Markup(str):
    """A string subclass marking content as safe (won't be auto-escaped).

    The Markup class implements the `__html__` protocol used by template engines
    to identify pre-escaped content. When combined with regular strings via
    operators like `+`, the non-Markup strings are automatically escaped.

    This is Kida's native implementation — no external dependencies required.

    Example:
        >>> safe = Markup("<b>bold</b>")
        >>> safe
        Markup('<b>bold</b>')
        >>> str(safe)
        '<b>bold</b>'
        >>> safe + " <script>"  # Non-Markup is escaped
        Markup('<b>bold</b> &lt;script&gt;')

    Thread-Safety:
        Immutable (inherits from str). Safe for concurrent access.
    """

    __slots__ = ()

    def __new__(cls, value: Any = "") -> Self:
        """Create a Markup string.

        Args:
            value: Content to mark as safe. If it has an `__html__()` method,
                   that method is called to get the string value.

        Returns:
            Markup instance containing the safe content.
        """
        if hasattr(value, "__html__"):
            value = value.__html__()
        return super().__new__(cls, value)

    def __html__(self) -> Self:
        """Return self — already safe content.

        This method is the `__html__` protocol that template engines use
        to detect pre-escaped content.
        """
        return self

    def __repr__(self) -> str:
        return f"Markup({super().__repr__()})"

    # --- Operations that escape non-Markup values ---

    def __add__(self, other: str) -> Self:
        """Concatenate, escaping `other` if not Markup."""
        if isinstance(other, str) and not isinstance(other, Markup):
            other = _escape_str(other)
        return self.__class__(super().__add__(other))

    def __radd__(self, other: str) -> Self:
        """Reverse concatenate, escaping `other` if not Markup."""
        if isinstance(other, str) and not isinstance(other, Markup):
            other = _escape_str(other)
        return self.__class__(other.__add__(self))

    def __mul__(self, n: SupportsIndex) -> Self:
        """Repeat string n times."""
        return self.__class__(super().__mul__(n))

    def __rmul__(self, n: SupportsIndex) -> Self:
        """Repeat string n times (reverse)."""
        return self.__class__(super().__mul__(n))

    def __mod__(self, args: Any) -> Self:
        """Format string with %-style, escaping non-Markup args."""
        escaped_args: Any
        if isinstance(args, tuple):
            args_tuple = cast("tuple[Any, ...]", args)
            escaped_args = tuple(_escape_arg(a) for a in args_tuple)
        elif isinstance(args, dict):
            args_dict = cast("dict[str, Any]", args)
            escaped_args = {k: _escape_arg(v) for k, v in args_dict.items()}
        else:
            escaped_args = _escape_arg(args)
        return self.__class__(super().__mod__(escaped_args))

    def format(self, *args: Any, **kwargs: Any) -> Self:
        """Format string, escaping non-Markup arguments."""
        args = tuple(_escape_arg(a) for a in args)
        kwargs = {k: _escape_arg(v) for k, v in kwargs.items()}
        return self.__class__(super().format(*args, **kwargs))

    def join(self, seq: Iterable[str]) -> Self:
        """Join sequence, escaping non-Markup elements."""
        return self.__class__(super().join(_escape_arg(s) for s in seq))

    # --- String methods that return Markup ---

    def capitalize(self) -> Self:
        return self.__class__(super().capitalize())

    def casefold(self) -> Self:
        return self.__class__(super().casefold())

    def center(self, width: SupportsIndex, fillchar: str = " ") -> Self:
        return self.__class__(super().center(width, fillchar))

    def lower(self) -> Self:
        return self.__class__(super().lower())

    def upper(self) -> Self:
        return self.__class__(super().upper())

    def title(self) -> Self:
        return self.__class__(super().title())

    def swapcase(self) -> Self:
        return self.__class__(super().swapcase())

    def strip(self, chars: str | None = None) -> Self:
        return self.__class__(super().strip(chars))

    def lstrip(self, chars: str | None = None) -> Self:
        return self.__class__(super().lstrip(chars))

    def rstrip(self, chars: str | None = None) -> Self:
        return self.__class__(super().rstrip(chars))

    def ljust(self, width: SupportsIndex, fillchar: str = " ") -> Self:
        return self.__class__(super().ljust(width, fillchar))

    def rjust(self, width: SupportsIndex, fillchar: str = " ") -> Self:
        return self.__class__(super().rjust(width, fillchar))

    def zfill(self, width: SupportsIndex) -> Self:
        return self.__class__(super().zfill(width))

    def replace(self, old: str, new: str, count: SupportsIndex = -1) -> Self:
        return self.__class__(super().replace(old, new, count))

    def expandtabs(self, tabsize: SupportsIndex = 8) -> Self:
        return self.__class__(super().expandtabs(tabsize))

    def split(  # type: ignore[override]
        self, sep: str | None = None, maxsplit: SupportsIndex = -1
    ) -> list[Self]:
        return [self.__class__(s) for s in super().split(sep, maxsplit)]

    def rsplit(  # type: ignore[override]
        self, sep: str | None = None, maxsplit: SupportsIndex = -1
    ) -> list[Self]:
        return [self.__class__(s) for s in super().rsplit(sep, maxsplit)]

    def splitlines(self, keepends: bool = False) -> list[Self]:  # type: ignore[override]
        return [self.__class__(s) for s in super().splitlines(keepends)]

    def partition(self, sep: str) -> tuple[Self, Self, Self]:
        a, b, c = super().partition(sep)
        return self.__class__(a), self.__class__(b), self.__class__(c)

    def rpartition(self, sep: str) -> tuple[Self, Self, Self]:
        a, b, c = super().rpartition(sep)
        return self.__class__(a), self.__class__(b), self.__class__(c)

    # --- Utility methods ---

    def striptags(self) -> Self:
        """Remove HTML tags from the string.

        **IMPORTANT: This is for DISPLAY purposes only, not security.**

        This method uses regex-based tag removal which can be bypassed
        with malformed HTML. It is suitable for:
        - Displaying text previews
        - Extracting text content for search indexing
        - Formatting plain-text emails from HTML

        For security (preventing XSS), always use html_escape() or the
        Markup class with autoescape enabled.

        Returns:
            Markup with all HTML tags removed.
        """
        return self.__class__(_STRIPTAGS_RE.sub("", self))

    def unescape(self) -> str:
        """Convert HTML entities back to characters.

        Returns:
            Plain string with entities decoded (no longer marked as safe).
        """
        return html.unescape(self)

    @classmethod
    def escape(cls, value: Any) -> Self:
        """Escape a value and wrap it as Markup.

        This is the class method form of escaping — use for explicit escaping.

        Args:
            value: Value to escape. Objects with `__html__()` are used as-is.

        Returns:
            Markup instance with the escaped content.
        """
        if hasattr(value, "__html__"):
            return cls(value.__html__())
        return cls(_escape_str(str(value)))


# =============================================================================
# Core Escaping Functions
# =============================================================================


def _escape_str(s: str) -> str:
    """Escape a string for HTML (internal helper).

    Uses O(n) single-pass str.translate() for all strings.

    Rationale: benchmarks on 2026-01-11 (Python 3.14) showed the previous
    frozenset intersection "fast path" was slower for 64–8192 byte inputs
    with no escapable characters (154ns → 5.9µs for translate-only vs
    569ns → 50µs with intersection). We now always translate; CPython
    returns the original string when no substitutions are needed.

    Args:
        s: String to escape.

    Returns:
        Escaped string (still plain str, not Markup).

    Complexity:
        O(n) single pass. No backtracking, no regex.
    """
    return s.translate(_ESCAPE_TABLE)


def _escape_arg(value: Any) -> Any:
    """Escape a value if it's a string but not Markup.

    Used for escaping format arguments.
    """
    if isinstance(value, Markup):
        return value
    if isinstance(value, str):
        return _escape_str(value)
    return value


def html_escape(value: Any) -> str:
    """O(n) single-pass HTML escaping with type optimization.

    Returns plain str (for template._escape use).

    Complexity: O(n) single-pass using str.translate().

    Security:
        - Escapes &, <, >, ", '
        - Strips NUL bytes (\\x00) which can bypass some filters
        - Objects with __html__() are returned as-is (already safe)

    Optimizations:
        1. Skip Markup objects (already safe)
        2. Skip numeric types (int, float, bool) - cannot contain HTML chars
        3. Single-pass translation instead of 5 chained .replace()

    The numeric type optimization provides ~2.5x speedup for number-heavy
    templates (benchmarks/test_benchmark_optimization_levers.py).

    Args:
        value: Value to escape (will be converted to string)

    Returns:
        Escaped string (not Markup, so it can be escaped again if needed)
    """
    # Skip Markup objects - they're already safe
    # Must check before str() conversion since str(Markup) returns plain str
    if isinstance(value, Markup):
        return str(value)

    # Optimization: numeric types cannot contain HTML special characters
    # Use type() instead of isinstance() to exclude subclasses that might
    # override __str__ with HTML content
    # Note: This is safe because int/float/bool.__str__ always returns
    # decimal digits, signs, decimal points, 'e', 'True', or 'False'
    value_type = type(value)
    if value_type is int or value_type is float or value_type is bool:
        return str(value)

    s = str(value)
    return _escape_str(s)


def html_escape_filter(value: Any) -> Markup:
    """HTML escape returning Markup (for filter use).

    Returns Markup object so result won't be escaped again by autoescape.

    Args:
        value: Value to escape (will be converted to string)

    Returns:
        Markup object (safe, won't be double-escaped)
    """
    # Already safe - return as-is
    if isinstance(value, Markup):
        return value
    return Markup(html_escape(value))


# =============================================================================
# Attribute Functions
# =============================================================================


def _is_valid_attr_name(name: str) -> bool:
    """Check if attribute name is valid per HTML5 spec.

    Uses O(n) single-pass check with frozenset for O(1) char lookup.
    No regex.

    Args:
        name: Attribute name to validate.

    Returns:
        True if valid, False otherwise.
    """
    if not name:
        return False
    # Check each character against invalid set (O(n) single pass)
    return all(char not in _INVALID_ATTR_CHARS for char in name)


def xmlattr(
    value: dict[str, Any],
    *,
    allow_events: bool = False,
    strip_events: bool = False,
    strict: bool = True,
) -> Markup:
    """Convert dict to XML/HTML attributes string.

    Escapes attribute values and formats as key="value" pairs.
    Returns Markup to prevent double-escaping when autoescape is enabled.

    Attribute ordering: Python 3.7+ dicts maintain insertion order.
    Output order matches input dict order.

    Security:
        - Validates attribute names per HTML5 spec
        - Warns on event handler attributes (onclick, onerror, etc.)
        - Escapes all attribute values

    Args:
        value: Dictionary of attribute names to values.
        allow_events: If False (default), warns on event handler attributes
                      (onclick, onerror, etc.). Set True to suppress.
        strip_events: If True, automatically removes event handler attributes.
                      Default False.
        strict: If True (default), raises on invalid attribute names.
                If False, skips invalid names with a warning.

    Returns:
        Markup object containing space-separated key="value" pairs.

    Raises:
        ValueError: If strict=True and an invalid attribute name is found.

    Example:
        >>> xmlattr({"class": "btn", "data-id": "123"})
        Markup('class="btn" data-id="123"')

        >>> xmlattr({"onclick": "alert(1)"})  # Warns by default
        Markup('onclick="alert(1)"')

        >>> xmlattr({"onclick": "handler()"}, strip_events=True)  # onclick removed
        Markup('')
    """
    parts: list[str] = []
    for key, val in value.items():
        if val is None:
            continue

        # Validate attribute name (O(n) single pass, no regex)
        if not _is_valid_attr_name(key):
            msg = f"Invalid attribute name: {key!r}"
            if strict:
                raise ValueError(msg)
            warnings.warn(msg, UserWarning, stacklevel=2)
            continue

        # Handle event handlers (potential XSS vector)
        if key.lower() in _EVENT_HANDLER_ATTRS:
            if strip_events:
                continue
            if not allow_events:
                warnings.warn(
                    f"Event handler attribute '{key}' can execute JavaScript. "
                    f"Use allow_events=True to suppress this warning, or "
                    f"strip_events=True to remove them.",
                    UserWarning,
                    stacklevel=2,
                )

        escaped = html_escape(str(val))
        parts.append(f'{key}="{escaped}"')

    return Markup(" ".join(parts))


# =============================================================================
# Context-Specific Escaping
# =============================================================================


def js_escape(value: Any) -> str:
    """Escape a value for use inside JavaScript string literals.

    This escapes characters that could break out of a JS string or
    inject code. Use this when embedding user data in inline scripts.

    Complexity: O(n) single pass using str.translate().

    Args:
        value: Value to escape (will be converted to string).

    Returns:
        Escaped string safe for use in JS string context.

    Example:
        >>> js_escape('Hello "World"')
        'Hello \\\\"World\\\\"'

        >>> js_escape("</script>")
        '\\\\x3c/script\\\\x3e'

        >>> js_escape("Hello `${name}`")  # Template literal
        'Hello \\\\`\\\\${name}\\\\`'

    Warning:
        This is for string literals only. Do not use for:
        - JavaScript identifiers
        - Numeric values (use int()/float() validation)
        - JSON (use json.dumps())
    """
    return str(value).translate(_JS_ESCAPE_TABLE)


class JSString(str):
    """A string safe for JavaScript string literal context.

    Similar to Markup but for JavaScript strings instead of HTML.
    Prevents accidental double-escaping in JS contexts.

    Example:
        >>> safe = JSString(js_escape(user_input))
        >>> f'var x = "{safe}";'  # Safe to embed
    """

    __slots__ = ()

    def __new__(cls, value: Any = "") -> Self:
        return super().__new__(cls, value)

    def __repr__(self) -> str:
        return f"JSString({super().__repr__()})"


def css_escape(value: Any) -> str:
    """Escape a value for use in CSS contexts.

    Protects against breaking out of quotes in properties or
    injecting malicious content into url() or @import.

    Complexity: O(n) single pass using str.translate().

    Args:
        value: Value to escape.

    Returns:
        Escaped string safe for CSS property values.
    """
    return str(value).translate(_CSS_ESCAPE_TABLE)


# =============================================================================
# URL Validation
# =============================================================================


def url_is_safe(url: str, *, allow_data: bool = False) -> bool:
    """Check if a URL has a safe protocol scheme.

    Protects against javascript:, vbscript:, and data: URLs that
    can execute code when used in href/src attributes.

    Uses window-based parsing: O(n) single pass, no regex.

    Args:
        url: URL to check.
        allow_data: If True, allow data: URLs. Default False.

    Returns:
        True if the URL is safe to use in href/src attributes.

    Example:
        >>> url_is_safe("https://example.com")
        True
        >>> url_is_safe("javascript:alert(1)")
        False
        >>> url_is_safe("/path/to/page")
        True
        >>> url_is_safe("  javascript:alert(1)  ")  # Whitespace stripped
        False
    """
    # Strip NUL bytes and whitespace (prevent bypass attempts)
    url = url.replace("\x00", "").strip()

    if not url:
        return True  # Empty is safe (becomes #)

    # Relative URLs are safe
    if url.startswith(_RELATIVE_PREFIXES):
        return True

    # Protocol-relative URLs inherit page protocol
    if url.startswith("//"):
        return True

    # Find scheme (characters before first colon)
    # Use window-based scanning: O(n) single pass
    colon_pos = -1
    for i, char in enumerate(url):
        if char == ":":
            colon_pos = i
            break
        # Scheme chars: a-z, A-Z, 0-9, +, -, . (but must start with letter)
        if i == 0:
            if not char.isalpha():
                return True  # No valid scheme, treated as relative
        elif not (char.isalnum() or char in "+-."):
            return True  # Invalid scheme char, treated as relative

    if colon_pos == -1:
        return True  # No scheme, treated as relative

    scheme = url[:colon_pos].lower()

    # Handle data: URLs separately
    if scheme == "data":
        return allow_data

    return scheme in _SAFE_SCHEMES


def safe_url(url: str, *, fallback: str = "#") -> str:
    """Return URL if safe, otherwise return fallback.

    Use in templates where you need a safe URL value (href, src, etc.).

    Args:
        url: URL to validate.
        fallback: Value to return if URL is unsafe. Default "#".

    Returns:
        The URL if safe, otherwise the fallback.

    Example:
        >>> safe_url("https://example.com")
        'https://example.com'
        >>> safe_url("javascript:alert(1)")
        '#'
        >>> safe_url("javascript:void(0)", fallback="/home")
        '/home'
    """
    if url_is_safe(url):
        return url
    return fallback


# =============================================================================
# Utility Functions
# =============================================================================


def strip_tags(value: str) -> str:
    """Remove HTML tags from string.

    **IMPORTANT: This is for DISPLAY purposes only, not security.**

    This function uses regex-based tag removal which can be bypassed
    with malformed HTML. It is suitable for:
    - Displaying text previews
    - Extracting text content for search indexing
    - Formatting plain-text emails from HTML

    For security (preventing XSS), always use html_escape() or the
    Markup class with autoescape enabled.

    Uses pre-compiled regex for performance. O(n) single pass.

    Args:
        value: String potentially containing HTML tags

    Returns:
        String with all HTML tags removed
    """
    return _STRIPTAGS_RE.sub("", str(value))


def spaceless(html_str: str) -> str:
    """Remove whitespace between HTML tags.

    Args:
        html_str: HTML string

    Returns:
        HTML string with whitespace between tags removed
    """
    return _SPACELESS_RE.sub("><", html_str).strip()


def format_html(format_string: str, *args: Any, **kwargs: Any) -> Markup:
    """Format a string with HTML escaping of all arguments.

    Like str.format() but escapes all arguments for HTML safety.
    The format string itself is trusted (not escaped).

    This is a convenience wrapper around Markup().format().

    Args:
        format_string: Format string (trusted, not escaped).
        *args: Positional arguments (escaped).
        **kwargs: Keyword arguments (escaped).

    Returns:
        Markup object with escaped arguments.

    Example:
        >>> format_html("<p>Hello, {name}!</p>", name="<script>")
        Markup('<p>Hello, &lt;script&gt;!</p>')

        >>> format_html("<a href='{url}'>{text}</a>", url="/page", text="<Click>")
        Markup("<a href='/page'>&lt;Click&gt;</a>")

    Warning:
        The format_string is NOT escaped. Only use with trusted strings.
        For user-controlled format strings, use Markup.escape() on each part.
    """
    return Markup(format_string).format(*args, **kwargs)


# =============================================================================
# Lazy Evaluation (SoftStr)
# =============================================================================


class SoftStr:
    """A string wrapper that defers __str__ evaluation.

    Useful for expensive string operations that may not be needed.
    Commonly used with missing template variables or expensive lookups.

    Thread-Safety:
        The lazy evaluation is NOT thread-safe. If you need thread-safe
        lazy evaluation, compute the value before passing to templates.

    Example:
        >>> soft = SoftStr(lambda: expensive_operation())
        >>> # expensive_operation() not called yet
        >>> str(soft)  # Now it's called
        >>> str(soft)  # Returns cached value
    """

    __slots__ = ("_func", "_value", "_resolved")

    def __init__(self, func: Callable[[], str]) -> None:
        self._func = func
        self._resolved = False
        self._value: str = ""

    def __str__(self) -> str:
        if not self._resolved:
            self._value = self._func()
            self._resolved = True
        return self._value

    def __html__(self) -> str:
        """Support __html__ protocol - escape when rendered.

        Handles the case where _func returns Markup properly.
        """
        value = str(self)
        # If the resolved value is already Markup, don't double-escape
        html_method = getattr(self._value, "__html__", None)
        if html_method is not None:
            result: str = html_method()
            return result
        return html_escape(value)

    def __repr__(self) -> str:
        if self._resolved:
            return f"SoftStr({self._value!r})"
        return "SoftStr(<unresolved>)"

    def __bool__(self) -> bool:
        return bool(str(self))

    def __len__(self) -> int:
        return len(str(self))


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Core
    "Markup",
    "html_escape",
    "html_escape_filter",
    # Utilities
    "strip_tags",
    "spaceless",
    "xmlattr",
    "format_html",
    # Context-specific escaping
    "js_escape",
    "JSString",
    "css_escape",
    "url_is_safe",
    "safe_url",
    # Lazy evaluation
    "SoftStr",
]
