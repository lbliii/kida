"""Shared constants for Kida.

Extracted from html.py to keep modules focused.
"""

from __future__ import annotations

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
