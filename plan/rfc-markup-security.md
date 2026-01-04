# RFC: Markup Security Hardening

**Status**: Implemented ✅  
**Created**: 2026-01-04  
**Updated**: 2026-01-04  
**Author**: Bengal Contributors

---

## Executive Summary

Harden Kida's native `Markup` implementation for production security. While the current implementation handles basic HTML escaping correctly, it lacks coverage for edge cases that could lead to XSS vulnerabilities in security-sensitive applications.

**Key Deliverables:**
- Comprehensive XSS test suite (~60 test cases)
- NUL byte and Unicode edge case handling
- Attribute name validation in `xmlattr()`
- JavaScript/CSS context escaping utilities
- Performance-optimized escaping using window-based scanning
- Security documentation for users

---

## Background

### Why This Matters

Kida replaced MarkupSafe to achieve:
- Zero runtime dependencies
- Free-threading (PEP 703) compatibility
- Pure Python portability

However, MarkupSafe has 10+ years of security hardening. Our native implementation must match or exceed its security guarantees before Kida 1.0.

### Anticipated Use Cases

| Use Case | Security Sensitivity | Adoption Likelihood |
|----------|---------------------|---------------------|
| Static site generators (Bengal) | Medium | Very High |
| Web applications | **Critical** | High |
| Email templates | **Critical** | High |
| API documentation | Low-Medium | Medium |
| Report generation | Medium | Medium |
| Config/script generation | Low | Low |

**Primary risk**: Web apps and email templates with user-generated content. XSS in these contexts can lead to session hijacking, data theft, and malware distribution.

---

## Current State Analysis

### What Works ✅

```python
# Basic escaping
html_escape("<script>") → "&lt;script&gt;"  ✅

# Markup class protocol
Markup("<b>safe</b>") + "<script>"  → Markup('<b>safe</b>&lt;script&gt;')  ✅

# Format escaping
Markup("<p>{}</p>").format("<xss>") → Markup('<p>&lt;xss&gt;</p>')  ✅

# Five characters escaped
& → &amp;
< → &lt;
> → &gt;
" → &quot;
' → &#39;
```

### What's Missing ❌

#### 1. NUL Byte Handling

NUL bytes (`\x00`) can bypass filters in some parsers:

```python
# Current behavior (VULNERABLE)
html_escape("\x00<script>")  → "\x00&lt;script&gt;"
# The NUL byte is preserved, which some parsers may interpret as string termination
```

#### 2. Unicode Edge Cases

```python
# Zero-width characters can hide malicious content
html_escape("<scr\u200dipt>")  # Zero-width joiner in tag name

# RTL override can visually spoof content
html_escape("\u202ealert(1)")  # Right-to-left override

# Fullwidth brackets (different Unicode codepoints)
html_escape("\uff1cscript\uff1e")  # ＜script＞
```

#### 3. Attribute Context

Current `xmlattr()` doesn't validate attribute names:

```python
# Current behavior (DANGEROUS)
xmlattr({"onclick": "alert(1)", "class": "btn"})
→ Markup('onclick="alert(1)" class="btn"')  # XSS!
```

#### 4. JavaScript/CSS Context

No utilities for non-HTML contexts:

```html
<script>var x = "{{ user_input }}";</script>  <!-- Needs JS escaping -->
<style>.x { content: "{{ input }}"; }</style>  <!-- Needs CSS escaping -->
```

Current implementation has no `css_escape` or `js_escape` logic, leaving users to rely on basic HTML escaping which is insufficient for these contexts (e.g., HTML escaping `<` won't prevent breaking out of a CSS `url()` or a JS string literal).

#### 5. URL Protocol Validation

No helper to validate `href`/`src` URLs:

```html
<a href="{{ url }}">Click</a>
<!-- What if url = "javascript:alert(1)"? -->
```

#### 6. `striptags` Security

Current regex-based `striptags` is bypassable and not meant for security:

```python
# Current regex: r"<[^>]*>"
# Attack vectors that bypass:
"<script<script>>alert(1)</script>"  # Nested opening
"<div foo='>'><script>alert(1)</script>"  # Quote with > inside
```

---

## Proposed Changes

### Phase 1: Core Security (Critical)

#### 1.1 Performance-Optimized Escaping with Window Pattern

Replace regex-based checks with O(1) frozenset lookups following Bengal's lexer pattern.

**File**: `src/kida/utils/html.py`

```python
# O(1) character class lookup (no regex in hot path)
_ESCAPE_CHARS: frozenset[str] = frozenset('&<>"\'\x00')

# Pre-compiled escape table for O(n) single-pass HTML escaping
_ESCAPE_TABLE = str.maketrans(
    {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
        "\x00": "",  # Strip NUL bytes
    }
)


def _escape_str(s: str) -> str:
    """Escape a string for HTML (internal helper).

    Uses window-based scanning: O(1) frozenset check for fast path,
    O(n) single-pass translate for escaping. No regex.

    Args:
        s: String to escape.

    Returns:
        Escaped string (still plain str, not Markup).

    Complexity:
        O(n) single pass. No backtracking, no regex.
    """
    # Fast path: O(1) frozenset intersection check
    # If no escapable characters, return as-is
    # This is faster than regex.search() for short strings
    for char in s:
        if char in _ESCAPE_CHARS:
            break
    else:
        return s  # No escapable chars found

    # O(n) single-pass translation (handles NUL stripping + escaping)
    return s.translate(_ESCAPE_TABLE)
```

**Performance Note**: The frozenset loop is actually slower for very short strings due to Python function call overhead. An alternative using `any()` with a generator:

```python
def _escape_str(s: str) -> str:
    """Escape a string for HTML (internal helper)."""
    # Fast path using frozenset intersection
    if not _ESCAPE_CHARS.intersection(s):
        return s
    return s.translate(_ESCAPE_TABLE)
```

**Benchmark both approaches** and use the faster one. The `intersection()` approach creates a temporary set but is a single C-level call.

#### 1.2 Comprehensive XSS Test Suite

**File**: `tests/test_markup_security.py` (new)

```python
"""Security tests for Markup and HTML escaping.

Tests XSS vectors, Unicode edge cases, and context-specific escaping.
Based on OWASP XSS Filter Evasion Cheat Sheet and MarkupSafe test patterns.

All regex patterns used are O(n) linear time (no ReDoS risk).
"""

import pytest
from kida import Markup
from kida.utils.html import html_escape, xmlattr


class TestNULByteHandling:
    """NUL bytes can bypass filters in some contexts."""

    def test_nul_stripped_from_output(self):
        """NUL bytes should be removed entirely."""
        assert "\x00" not in html_escape("\x00<script>")

    def test_nul_before_tag(self):
        """NUL before tag name still escapes."""
        result = html_escape("\x00<script>")
        assert "&lt;script&gt;" in result

    def test_nul_in_tag(self):
        """NUL within tag name."""
        result = html_escape("<scr\x00ipt>")
        assert "&lt;" in result
        assert "\x00" not in result

    def test_nul_in_attribute(self):
        """NUL in attribute value."""
        result = html_escape('value="\x00test"')
        assert "\x00" not in result

    def test_multiple_nul_bytes(self):
        """Multiple NUL bytes all removed."""
        result = html_escape("\x00\x00<script>\x00")
        assert "\x00" not in result
        assert "&lt;script&gt;" in result


class TestUnicodeEdgeCases:
    """Unicode edge cases that could enable attacks."""

    def test_zero_width_joiner(self):
        """Zero-width joiner in tag name - still escapes < and >."""
        result = html_escape("<scr\u200dipt>")
        assert "&lt;" in result
        assert "&gt;" in result

    def test_zero_width_space(self):
        """Zero-width space - still escapes < and >."""
        result = html_escape("<\u200bscript>")
        assert "&lt;" in result

    def test_rtl_override_preserved(self):
        """RTL override should not crash and pass through."""
        result = html_escape("\u202ealert(1)")
        assert isinstance(result, str)
        assert "\u202e" in result  # RTL preserved, no < to escape

    def test_combining_characters(self):
        """Combining characters shouldn't break escaping."""
        result = html_escape("te\u0301st<b>")  # e + combining acute
        assert "&lt;b&gt;" in result
        assert "te\u0301st" in result  # Preserved

    def test_surrogate_pairs(self):
        """Emoji and other surrogate pairs."""
        result = html_escape("<b>Hello 👋 World</b>")
        assert "👋" in result
        assert "&lt;b&gt;" in result

    def test_fullwidth_brackets_passthrough(self):
        """Fullwidth brackets pass through (different codepoints).

        U+FF1C (＜) and U+FF1E (＞) are NOT HTML angle brackets.
        They are CJK fullwidth forms and should pass through unchanged.

        Note: Some browsers may still render these as angle-like characters,
        but they do NOT function as HTML tag delimiters. This is the correct
        behavior per HTML5 spec.
        """
        result = html_escape("\uff1cscript\uff1e")
        # Fullwidth brackets pass through unchanged
        assert "\uff1c" in result
        assert "\uff1e" in result
        # Real angle brackets would be escaped
        assert "&lt;" not in result

    def test_overlong_utf8_rejected(self):
        """Overlong UTF-8 sequences (if present) don't bypass escaping.

        Python 3 strings are decoded UTF-8, so overlong sequences would
        have already been rejected at decode time. This test documents
        that behavior.
        """
        # This is the normal < character
        result = html_escape("<")
        assert result == "&lt;"


class TestDoubleEscapePrevention:
    """Ensure no double-escaping occurs."""

    def test_markup_not_double_escaped(self):
        """Markup objects should not be re-escaped."""
        safe = Markup("&lt;already escaped&gt;")
        result = html_escape(safe)
        assert result == "&lt;already escaped&gt;"
        assert "&amp;lt;" not in result

    def test_entity_not_double_escaped(self):
        """Existing entities should not be re-escaped via Markup."""
        m = Markup("&amp;")
        result = str(m + "")  # Trigger concatenation
        assert result == "&amp;"
        assert "&amp;amp;" not in result

    def test_nested_markup_format(self):
        """Nested Markup.format() operations."""
        inner = Markup("<span>{}</span>").format("<xss>")
        outer = Markup("<div>{}</div>").format(inner)
        assert "<span>" in str(outer)
        assert "&lt;xss&gt;" in str(outer)
        assert "<xss>" not in str(outer)

    def test_triple_nested_format(self):
        """Triple nested formatting still prevents double-escape."""
        a = Markup("<a>{}</a>").format("<x>")
        b = Markup("<b>{}</b>").format(a)
        c = Markup("<c>{}</c>").format(b)
        result = str(c)
        assert "<a>" in result
        assert "<b>" in result
        assert "<c>" in result
        assert "&lt;x&gt;" in result
        assert result.count("&lt;") == 1  # Only <x> escaped


class TestMarkupOperations:
    """Markup class operations maintain safety invariants."""

    def test_add_escapes_plain_string(self):
        """+ operator escapes plain strings."""
        m = Markup("<b>") + "<script>"
        assert "&lt;script&gt;" in str(m)
        assert "<b>" in str(m)

    def test_radd_escapes_plain_string(self):
        """Reverse + escapes plain strings."""
        m = "<script>" + Markup("<b>")
        assert "&lt;script&gt;" in str(m)
        assert "<b>" in str(m)

    def test_mod_escapes_string_arg(self):
        """% formatting escapes string arguments."""
        m = Markup("<p>%s</p>") % "<script>"
        assert "&lt;script&gt;" in str(m)

    def test_mod_escapes_tuple_args(self):
        """% formatting escapes tuple arguments."""
        m = Markup("<p>%s %s</p>") % ("<a>", "<b>")
        assert "&lt;a&gt;" in str(m)
        assert "&lt;b&gt;" in str(m)

    def test_mod_escapes_dict_args(self):
        """% formatting escapes dict arguments."""
        m = Markup("<p>%(x)s</p>") % {"x": "<script>"}
        assert "&lt;script&gt;" in str(m)

    def test_format_escapes_positional(self):
        """format() escapes positional arguments."""
        m = Markup("<p>{} {}</p>").format("<a>", "<b>")
        assert "&lt;a&gt;" in str(m)
        assert "&lt;b&gt;" in str(m)

    def test_format_escapes_keyword(self):
        """format() escapes keyword arguments."""
        m = Markup("<p>{x}</p>").format(x="<script>")
        assert "&lt;script&gt;" in str(m)

    def test_join_escapes_elements(self):
        """join() escapes non-Markup elements."""
        m = Markup(", ").join(["<a>", "<b>", "<c>"])
        result = str(m)
        assert "&lt;a&gt;" in result
        assert "&lt;b&gt;" in result
        assert "&lt;c&gt;" in result

    def test_join_preserves_markup_elements(self):
        """join() preserves Markup elements."""
        m = Markup(", ").join([Markup("<b>"), "plain", Markup("<i>")])
        result = str(m)
        assert "<b>" in result  # Preserved
        assert "<i>" in result  # Preserved
        assert "plain" in result  # Not escaped (no special chars)

    def test_mul_returns_markup(self):
        """Multiplication returns Markup."""
        m = Markup("<b>") * 3
        assert isinstance(m, Markup)
        assert str(m) == "<b><b><b>"

    def test_string_methods_return_markup(self):
        """String methods return Markup instances."""
        m = Markup("<B>Test</B>")
        assert isinstance(m.lower(), Markup)
        assert isinstance(m.upper(), Markup)
        assert isinstance(m.strip(), Markup)
        assert isinstance(m.replace("B", "I"), Markup)


class TestKnownXSSVectors:
    """Known XSS attack patterns from OWASP and security research."""

    @pytest.mark.parametrize("vector,must_escape", [
        # Basic script injection
        ("<script>alert(1)</script>", True),
        ("<SCRIPT>alert(1)</SCRIPT>", True),
        ("<ScRiPt>alert(1)</ScRiPt>", True),

        # Event handlers (angle brackets must be escaped)
        ("<img src=x onerror=alert(1)>", True),
        ("<svg onload=alert(1)>", True),
        ("<body onload=alert(1)>", True),
        ("<div onmouseover=alert(1)>", True),

        # Breaking out of attributes
        ('"><script>alert(1)</script>', True),
        ("'><script>alert(1)</script>", True),

        # Protocol handlers (contain angle brackets)
        ("<a href=javascript:alert(1)>", True),
        ("<iframe src=javascript:alert(1)>", True),

        # Nested/malformed tags
        ("<<script>script>alert(1)<</script>/script>", True),
        ("<script<script>>alert(1)</script>", True),

        # Character encoding tricks
        ("<script>alert(String.fromCharCode(88,83,83))</script>", True),

        # Data URLs with script (contain angle brackets)
        ("<a href='data:text/html,<script>alert(1)</script>'>", True),
    ])
    def test_xss_vectors_escaped(self, vector, must_escape):
        """Common XSS vectors should be safely escaped."""
        result = html_escape(vector)
        if must_escape:
            # Should not contain unescaped angle brackets
            assert "<script>" not in result.lower()
            assert "<img" not in result.lower() or "onerror" not in result.lower()
            # Should contain escaped characters
            assert "&lt;" in result


class TestXmlattr:
    """xmlattr() function tests."""

    def test_basic_attributes(self):
        """Basic attribute generation."""
        result = str(xmlattr({"class": "btn", "id": "submit"}))
        assert 'class="btn"' in result
        assert 'id="submit"' in result

    def test_escapes_quotes_in_values(self):
        """Double quotes in values must be escaped."""
        result = str(xmlattr({"data-value": 'test"value'}))
        assert "&quot;" in result
        assert 'data-value="test&quot;value"' in result

    def test_escapes_angle_brackets(self):
        """Angle brackets in values must be escaped."""
        result = str(xmlattr({"title": "<script>alert(1)</script>"}))
        assert "&lt;" in result
        assert "<script>" not in result

    def test_escapes_ampersand(self):
        """Ampersands in values must be escaped."""
        result = str(xmlattr({"data-query": "a=1&b=2"}))
        assert "&amp;" in result

    def test_none_values_skipped(self):
        """None values should be omitted."""
        result = str(xmlattr({"class": "btn", "disabled": None}))
        assert "class" in result
        assert "disabled" not in result

    def test_empty_dict(self):
        """Empty dict returns empty Markup."""
        result = xmlattr({})
        assert str(result) == ""
        assert isinstance(result, Markup)

    def test_boolean_false_included(self):
        """Boolean False should be included (not None)."""
        result = str(xmlattr({"data-active": False}))
        assert "data-active" in result


class TestStriptags:
    """striptags method tests.

    Note: striptags is for DISPLAY ONLY, not security. It removes visible
    tags from content for rendering purposes. For security, always escape
    user input with html_escape() or use Markup properly.
    """

    def test_basic_strip(self):
        """Basic tag stripping."""
        m = Markup("<p>Hello <b>World</b></p>")
        assert m.striptags() == "Hello World"

    def test_preserves_text(self):
        """Text content is preserved."""
        m = Markup("<div><span>Keep this</span></div>")
        assert "Keep this" in m.striptags()

    def test_nested_tags(self):
        """Nested tags are all stripped."""
        m = Markup("<div><p><b><i>Deep</i></b></p></div>")
        assert m.striptags() == "Deep"

    def test_malformed_tags(self):
        """Malformed tags handled best-effort (display only)."""
        m = Markup("<div><p>Text</div>")
        result = m.striptags()
        assert "Text" in result


class TestUnescape:
    """unescape method tests."""

    def test_basic_unescape(self):
        """Basic entity unescaping."""
        m = Markup("&lt;script&gt;")
        assert m.unescape() == "<script>"

    def test_returns_plain_str(self):
        """unescape returns plain str, not Markup."""
        m = Markup("&lt;b&gt;")
        result = m.unescape()
        assert not isinstance(result, Markup)
        assert isinstance(result, str)

    def test_numeric_entities(self):
        """Numeric entities are unescaped."""
        m = Markup("&#60;&#62;")
        assert m.unescape() == "<>"

    def test_named_entities(self):
        """Named entities are unescaped."""
        m = Markup("&amp;&quot;&#39;")
        assert m.unescape() == "&\"'"
```

#### 1.3 Attribute Name Validation

**File**: `src/kida/utils/html.py`

```python
import warnings
from typing import Any

# Valid XML/HTML attribute name pattern (O(1) validation using character sets)
# Per HTML5: attribute names are sequences of characters other than:
# - ASCII whitespace, NUL, quotes, apostrophe, >, /, =
_INVALID_ATTR_CHARS: frozenset[str] = frozenset(' \t\n\r\f\x00"\'>/=')

# Event handler attributes that can execute JavaScript
# Source: WHATWG HTML Living Standard + common SVG/MathML events
# Last updated: 2026-01
_EVENT_HANDLER_ATTRS: frozenset[str] = frozenset({
    # Mouse events
    'onclick', 'ondblclick', 'onmousedown', 'onmouseup', 'onmouseover',
    'onmousemove', 'onmouseout', 'onmouseenter', 'onmouseleave', 'onwheel',
    'oncontextmenu',

    # Keyboard events
    'onkeydown', 'onkeypress', 'onkeyup',

    # Focus events
    'onfocus', 'onblur', 'onfocusin', 'onfocusout',

    # Form events
    'onchange', 'oninput', 'oninvalid', 'onreset', 'onsubmit', 'onformdata',
    'onselect',

    # Drag events
    'ondrag', 'ondragend', 'ondragenter', 'ondragleave', 'ondragover',
    'ondragstart', 'ondrop',

    # Clipboard events
    'oncopy', 'oncut', 'onpaste',

    # Media events
    'onabort', 'oncanplay', 'oncanplaythrough', 'oncuechange',
    'ondurationchange', 'onemptied', 'onended', 'onerror', 'onloadeddata',
    'onloadedmetadata', 'onloadstart', 'onpause', 'onplay', 'onplaying',
    'onprogress', 'onratechange', 'onseeked', 'onseeking', 'onstalled',
    'onsuspend', 'ontimeupdate', 'onvolumechange', 'onwaiting',

    # Page/Window events
    'onload', 'onunload', 'onbeforeunload', 'onresize', 'onscroll',
    'onerror', 'onhashchange', 'onpopstate', 'onpageshow', 'onpagehide',
    'onoffline', 'ononline', 'onstorage', 'onmessage', 'onmessageerror',

    # Print events
    'onbeforeprint', 'onafterprint',

    # Animation events
    'onanimationstart', 'onanimationend', 'onanimationiteration',
    'onanimationcancel',

    # Transition events
    'ontransitionrun', 'ontransitionstart', 'ontransitionend',
    'ontransitioncancel',

    # Touch events
    'ontouchstart', 'ontouchend', 'ontouchmove', 'ontouchcancel',

    # Pointer events
    'onpointerdown', 'onpointerup', 'onpointermove', 'onpointerover',
    'onpointerout', 'onpointerenter', 'onpointerleave', 'onpointercancel',
    'ongotpointercapture', 'onlostpointercapture',

    # Other events
    'ontoggle', 'onsearch', 'onshow', 'onsecuritypolicyviolation',
    'onslotchange', 'onbeforeinput', 'onbeforematch',

    # Deprecated but still functional
    'onmousewheel',
})


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

    # First char must not start with invalid chars
    for char in name:
        if char in _INVALID_ATTR_CHARS:
            return False
    return True


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
```

---

### Phase 2: Context-Specific Escaping (High Priority)

#### 2.1 JavaScript String Escaping

```python
# JavaScript escape table (O(n) single-pass translation)
# Escapes characters that could:
# 1. Break out of string literals (\, ", ', newlines)
# 2. Break out of <script> context (<, >, /)
# 3. Break JavaScript parsing (U+2028, U+2029)
# 4. Enable template literal injection (`, $)
_JS_ESCAPE_TABLE = str.maketrans({
    "\\": "\\\\",
    '"': '\\"',
    "'": "\\'",
    "`": "\\`",     # Template literal delimiter
    "$": "\\$",     # Template literal interpolation ${...}
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
    "\x00": "\\x00",
    "<": "\\x3c",   # Prevent </script> breaking out
    ">": "\\x3e",
    "/": "\\/",     # Prevent </script> and <!-- -->
    "\u2028": "\\u2028",  # Line separator (breaks JS strings)
    "\u2029": "\\u2029",  # Paragraph separator
})


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
        'Hello \\"World\\"'

        >>> js_escape("</script>")
        '\\x3c/script\\x3e'

        >>> js_escape("Hello `${name}`")  # Template literal
        'Hello \\`\\${name}\\`'

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


```


#### 2.2 CSS Context Escaping

```python
# CSS escape table (O(n) single-pass translation)
# Escapes characters that could break out of property values or @rules.
_CSS_ESCAPE_TABLE = str.maketrans({
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
})


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
```


#### 2.3 URL Protocol Validation

```python
# Safe URL schemes (frozenset for O(1) lookup)
_SAFE_SCHEMES: frozenset[str] = frozenset({
    'http', 'https', 'mailto', 'tel', 'ftp', 'ftps', 'sms',
    # NOT included: javascript, vbscript, data (by default)
})

# Relative URL prefixes (checked with startswith for efficiency)
_RELATIVE_PREFIXES: tuple[str, ...] = ('/', './', '../', '#', '?')


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
    if url.startswith('//'):
        return True

    # Find scheme (characters before first colon)
    # Use window-based scanning: O(n) single pass
    colon_pos = -1
    for i, char in enumerate(url):
        if char == ':':
            colon_pos = i
            break
        # Scheme chars: a-z, A-Z, 0-9, +, -, . (but must start with letter)
        if i == 0:
            if not char.isalpha():
                return True  # No valid scheme, treated as relative
        elif not (char.isalnum() or char in '+-.'):
            return True  # Invalid scheme char, treated as relative

    if colon_pos == -1:
        return True  # No scheme, treated as relative

    scheme = url[:colon_pos].lower()

    # Handle data: URLs separately
    if scheme == 'data':
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
```

---

### Phase 3: Utilities & Documentation (Medium Priority)

#### 3.1 Soft String (Lazy Evaluation)

```python
from collections.abc import Callable


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
        if hasattr(self._value, "__html__"):
            return self._value.__html__()
        return html_escape(value)

    def __repr__(self) -> str:
        if self._resolved:
            return f"SoftStr({self._value!r})"
        return "SoftStr(<unresolved>)"

    def __bool__(self) -> bool:
        return bool(str(self))

    def __len__(self) -> int:
        return len(str(self))
```

#### 3.2 Format HTML Helper

```python
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
```

#### 3.3 Enhanced `striptags` with Security Documentation

```python
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
```

---

## Performance Considerations

### Window-Based Scanning vs Regex

Kida's security functions use the "window-based scanning" pattern from Bengal's lexer:

| Approach | Use Case | Complexity |
|----------|----------|------------|
| `frozenset.intersection(s)` | Check if ANY escapable chars | O(n) |
| `for c in s: if c in frozenset` | Same, explicit loop | O(n) |
| `re.compile(r'[...]').search(s)` | Regex version | O(n) but higher constant |
| `str.translate()` | Apply escape table | O(n) single pass |

**Key principles:**
1. **No regex in hot paths** — Use frozenset for character class checks
2. **Single-pass operations** — Never backtrack
3. **O(1) lookups** — frozenset for membership, dict for translation
4. **Early exit** — Fast path when no work needed

### Benchmark Targets

| Function | Target | Notes |
|----------|--------|-------|
| `html_escape(no_special)` | <100ns | Fast path, no translation |
| `html_escape(with_special)` | <500ns | O(n) translate |
| `url_is_safe(relative)` | <200ns | Early exit |
| `url_is_safe(absolute)` | <500ns | Full validation |
| `xmlattr(5 attrs)` | <2μs | Includes escaping |
| `js_escape(typical)` | <500ns | O(n) translate |

**Performance regression threshold**: <10% slower than current implementation.

### ReDoS Safety

All regex patterns in this RFC are **linear time O(n)**:

- `_STRIPTAGS_RE = re.compile(r"<[^>]*>")` — Linear, no backtracking
- `_SPACELESS_RE = re.compile(r">\s+<")` — Linear, no backtracking

No patterns use nested quantifiers or alternation that could cause exponential backtracking.

---

## Public API

### Exports from `kida.utils.html`

```python
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

    # Context-specific (Phase 2)
    "js_escape",
    "JSString",
    "css_escape",
    "url_is_safe",
    "safe_url",

    # Lazy evaluation (Phase 3)
    "SoftStr",
]
```

### Re-exports from `kida` package

```python
# In kida/__init__.py
from kida.utils.html import Markup, html_escape
```

---

## Migration & Compatibility

### MarkupSafe Compatibility

Kida's `Markup` is API-compatible with MarkupSafe:

| MarkupSafe | Kida | Status |
|------------|------|--------|
| `Markup(value)` | `Markup(value)` | ✅ Identical |
| `Markup.escape(s)` | `Markup.escape(s)` | ✅ Identical |
| `markup.__html__()` | `markup.__html__()` | ✅ Identical |
| `markup + str` | `markup + str` | ✅ Identical |
| `markup.format(...)` | `markup.format(...)` | ✅ Identical |
| `markup.striptags()` | `markup.striptags()` | ✅ Identical |
| `markup.unescape()` | `markup.unescape()` | ✅ Identical |
| `escape(s)` | `html_escape(s)` | ⚠️ Renamed |
| `soft_str(s)` | `SoftStr(s)` | ⚠️ Class vs function |

### For Bengal Users

No changes required. Bengal imports `Markup` from Kida, which is already the native implementation.

---

## Testing Requirements

### Test Categories

| Category | Test Count | Priority |
|----------|------------|----------|
| NUL byte handling | 5 | Critical |
| Unicode edge cases | 8 | Critical |
| Double-escape prevention | 4 | Critical |
| Markup operations | 12 | Critical |
| XSS vectors | 15 | Critical |
| xmlattr | 8 | High |
| striptags | 4 | High |
| unescape | 4 | High |
| js_escape | 10 | Medium |
| url_is_safe | 12 | Medium |
| format_html | 4 | Medium |
| SoftStr | 5 | Medium |
| **Total** | **~91** | |

### Performance Benchmarks

**File**: `benchmarks/benchmark_escape.py`

```python
"""Benchmarks for HTML escaping functions.

Run with: pytest benchmarks/ --benchmark-only
"""

import pytest
from kida.utils.html import html_escape, js_escape, url_is_safe, xmlattr
from kida import Markup


# --- html_escape benchmarks ---

def test_escape_no_special(benchmark):
    """Fast path: no special characters."""
    benchmark(html_escape, "Hello World no special chars here at all")


def test_escape_single_char(benchmark):
    """Single escapable character."""
    benchmark(html_escape, "Hello & World")


def test_escape_heavy(benchmark):
    """Many special characters."""
    benchmark(html_escape, "<script>alert('xss');</script>" * 10)


def test_escape_with_nul(benchmark):
    """NUL byte handling."""
    benchmark(html_escape, "\x00<script>\x00alert(1)\x00</script>\x00")


# --- Markup benchmarks ---

def test_markup_format(benchmark):
    """Markup.format() with escaping."""
    m = Markup("<p>{}</p>")
    benchmark(m.format, "<script>alert(1)</script>")


def test_markup_concat(benchmark):
    """Markup concatenation."""
    m = Markup("<b>")
    benchmark(lambda: m + "<script>")


# --- Context escaping benchmarks ---

def test_js_escape(benchmark):
    """JavaScript escaping."""
    benchmark(js_escape, 'Hello "World" </script> `${x}`')


def test_url_is_safe_relative(benchmark):
    """URL validation: relative (fast path)."""
    benchmark(url_is_safe, "/path/to/page")


def test_url_is_safe_absolute(benchmark):
    """URL validation: absolute safe URL."""
    benchmark(url_is_safe, "https://example.com/path?query=1")


def test_url_is_safe_javascript(benchmark):
    """URL validation: javascript: protocol."""
    benchmark(url_is_safe, "javascript:alert(1)")


# --- xmlattr benchmarks ---

def test_xmlattr_simple(benchmark):
    """Simple attribute set."""
    benchmark(xmlattr, {"class": "btn", "id": "submit"})


def test_xmlattr_with_escaping(benchmark):
    """Attributes requiring escaping."""
    benchmark(xmlattr, {"data-value": '<script>"test"</script>', "class": "btn"})
```

**Target**: No more than 10% slower than current implementation.

---

## Documentation

### Required Documentation

1. **Security Guide** (`docs/security.md`)
   - When to use `Markup` vs raw strings
   - Context-specific escaping (HTML, JS, URL)
   - Common XSS pitfalls
   - Safe patterns for user input
   - `striptags` is NOT for security (display only)

2. **API Reference Updates**
   - Document `xmlattr(allow_events=True)` pattern
   - Document `js_escape()` use cases and limitations
   - Document `url_is_safe()` pattern
   - Add complexity annotations (O(n) etc.)

3. **Migration Guide**
   - From MarkupSafe (for Jinja2 users switching to Kida)
   - Differences and additions

---

## Implementation Plan

### Phase 1: Core Security (Week 1)

| Task | Effort | Priority |
|------|--------|----------|
| **Establish performance baseline (current implementation)** | 1h | Critical |
| Refactor `_escape_str` with frozenset pattern | 1h | Critical |
| Add NUL byte stripping to escape table | 0.5h | Critical |
| Create `test_markup_security.py` | 4h | Critical |
| Add attribute name validation (no regex) | 1h | Critical |
| Update xmlattr with event warnings/stripping | 1h | Critical |
| Document `striptags` security posture | 0.5h | Critical |
| Run full test suite + benchmarks | 1h | Critical |
| **Phase 1 Total** | **10h** | |

### Phase 2: Context Escaping (Week 2)

| Task | Effort | Priority |
|------|--------|----------|
| Implement `js_escape()` with backtick/$ | 2h | High |
| Implement `JSString` class | 0.5h | High |
| **Implement `css_escape()`** | 2h | High |
| Implement `url_is_safe()` (window-based) | 2h | High |
| **Implement `safe_url()`** | 0.5h | High |
| Add tests for Phase 2 | 4h | High |
| **Phase 2 Total** | **11h** | |

### Phase 3: Utilities & Docs (Week 3)

| Task | Effort | Priority |
|------|--------|----------|
| Implement `SoftStr` with proper `__html__` | 1h | Medium |
| Implement `format_html()` | 0.5h | Medium |
| Add tests for Phase 3 | 1h | Medium |
| Write Security Guide | 3h | High |
| Update API docs with complexity notes | 2h | Medium |
| Create benchmarks suite | 1.5h | Medium |
| **Phase 3 Total** | **9h** | |

**Total Effort**: ~26 hours

---

## Success Criteria

### Phase 1 (Critical)

- [ ] All 60 XSS vector tests pass
- [ ] NUL bytes stripped from all output
- [ ] `xmlattr()` warns on or strips event handlers by default
- [ ] No double-escaping in any scenario
- [ ] All existing tests still pass
- [ ] **Performance baseline established and maintained**
- [ ] Benchmark shows no regression (or improvement)

### Phase 2 (High)

- [ ] `js_escape()` handles backticks and `${...}`
- [ ] **`css_escape()` protects against quote breakouts and malicious `url()` injections**
- [ ] `url_is_safe()` blocks `javascript:`, `vbscript:`, `data:` by default
- [ ] `url_is_safe()` strips NUL bytes from URLs
- [ ] 100% test coverage for new functions

### Phase 3 (Medium)

- [ ] Security documentation complete
- [ ] `striptags` documented as "display only, not security"
- [ ] API reference updated with complexity notes
- [ ] Benchmarks show <10% performance regression
- [ ] Migration guide for MarkupSafe users

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing behavior | High | Extensive test suite before changes |
| Performance regression | Medium | Benchmark before/after; use frozenset pattern |
| Missing edge cases | High | Use OWASP test vectors; fuzz testing |
| Over-escaping breaks templates | Medium | Double-escape prevention tests |
| User confusion with warnings | Low | Clear docs; `allow_events` escape hatch |
| ReDoS vulnerability | Medium | All regex patterns are O(n) linear |

---

## References

**Security Resources:**
- [OWASP XSS Filter Evasion Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/XSS_Filter_Evasion_Cheat_Sheet.html)
- [OWASP XSS Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)
- [MarkupSafe Source](https://github.com/pallets/markupsafe)
- [WHATWG HTML Living Standard - Event Handlers](https://html.spec.whatwg.org/#event-handlers)

**Related Files:**
- Source: `src/kida/utils/html.py`
- Tests: `tests/test_markup_security.py` (new)
- Benchmarks: `benchmarks/benchmark_escape.py` (new)
- Docs: `docs/security.md` (new)

**Related RFCs:**
- `rfc-kida-extraction.md` — Package extraction plan

**Internal Patterns:**
- Bengal lexer window pattern: `bengal/rendering/parsers/patitas/lexer/`
- State machine lexer: `bengal/rendering/rosettes/lexers/_state_machine.py`
