"""Shared constants for Kida.

Extracted from html.py to keep modules focused.
"""

from __future__ import annotations

# Resource limits (DoS protection)
MAX_FILTER_CHAIN_LEN = 200
MAX_PARTIAL_EVAL_DEPTH = 100

# ---------------------------------------------------------------------------
# Pure-filter registry (canonical location — imported by coalescing, purity,
# and partial_eval instead of duplicating the list)
# ---------------------------------------------------------------------------

# Filters safe for f-string coalescing: simple, no iteration, no side effects.
PURE_FILTERS_COALESCEABLE: frozenset[str] = frozenset(
    {
        # String case transformations
        "upper",
        "lower",
        "title",
        "capitalize",
        "swapcase",
        # Whitespace handling
        "trim",
        "strip",
        "lstrip",
        "rstrip",
        # HTML escaping
        "escape",
        "e",
        "forceescape",
        # Default values
        "default",
        "d",
        # Type conversion
        "int",
        "float",
        "string",
        "str",
        "bool",
        # Collection info
        "length",
        "count",
        # Collection access
        "first",
        "last",
        # String operations
        "join",
        "center",
        "ljust",
        "rjust",
        # Formatting
        "truncate",
        "wordwrap",
        "indent",
        # URL encoding
        "urlencode",
        # Formatting (pure)
        "date",
        "slug",
        "pluralize",
    }
)

# All filters known to be pure (deterministic, no side effects).
# Superset of PURE_FILTERS_COALESCEABLE — includes filters that are pure
# but too complex for f-string coalescing (e.g. collection transforms).
PURE_FILTERS_ALL: frozenset[str] = PURE_FILTERS_COALESCEABLE | frozenset(
    {
        # String manipulation (additional)
        "replace",
        "striptags",
        "urlize",
        "wordcount",
        # Collections (iteration-based, still deterministic)
        "sort",
        "reverse",
        "unique",
        "batch",
        "slice",
        "list",
        "map",
        "select",
        "reject",
        "selectattr",
        "rejectattr",
        "groupby",
        "pprint",
        # Type conversion (additional)
        "tojson",
        "safe",
        # Math
        "abs",
        "round",
        "sum",
        "min",
        "max",
        # Format
        "filesizeformat",
        "format",
        # Path/URL
        "basename",
        "dirname",
        "splitext",
        # Kida-specific
        "take",
        "skip",
        "where",
        "sort_by",
        # SSG-specific (deterministic for a build)
        "dateformat",
        "date_iso",
        "absolute_url",
        "relative_url",
        "meta_keywords",
        "jsonify",
        "markdownify",
        "slugify",
        "plainify",
        "humanize",
        "titlecase",
        "words",
    }
)

# Filters known to be impure (non-deterministic)
IMPURE_FILTERS: frozenset[str] = frozenset(
    {
        "random",
        "shuffle",
    }
)

# Functions known to be pure
PURE_FUNCTIONS: frozenset[str] = frozenset(
    {
        # Python builtins
        "len",
        "str",
        "int",
        "float",
        "bool",
        "list",
        "dict",
        "set",
        "tuple",
        "frozenset",
        "min",
        "max",
        "sum",
        "abs",
        "round",
        "pow",
        "sorted",
        "reversed",
        "enumerate",
        "zip",
        "map",
        "filter",
        "any",
        "all",
        "range",
        "hasattr",
        "getattr",
        "isinstance",
        "type",
        "ord",
        "chr",
        "hex",
        "oct",
        "bin",
        "repr",
        "hash",
    }
)

# Event handler attributes that can execute JavaScript
# Source: WHATWG HTML Living Standard + common SVG/MathML events
# Last updated: 2026-01
EVENT_HANDLER_ATTRS: frozenset[str] = frozenset(
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
