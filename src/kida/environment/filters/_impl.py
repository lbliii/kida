"""Built-in filters for Kida templates.

Registry aggregating filter implementations from category submodules.
Filters transform values in template expressions using the pipe syntax:
`{{ value | filter }}` or `{{ value | filter(arg1, arg2) }}`
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kida.environment.filters._collections import (
    SORT_KEY_NONE,
    _filter_attr,
    _filter_batch,
    _filter_compact,
    _filter_dictsort,
    _filter_first,
    _filter_groupby,
    _filter_join,
    _filter_last,
    _filter_length,
    _filter_map,
    _filter_reject,
    _filter_rejectattr,
    _filter_reverse,
    _filter_select,
    _filter_selectattr,
    _filter_skip,
    _filter_slice,
    _filter_sort,
    _filter_take,
    _filter_unique,
    _make_sort_key_numeric,
    _make_sort_key_string,
)
from kida.environment.filters._debug import _filter_debug, _filter_pprint
from kida.environment.filters._html_security import (
    _filter_csp_nonce,
    _filter_escape,
    _filter_safe,
    _filter_striptags,
    _filter_xmlattr,
)
from kida.environment.filters._misc import (
    _filter_classes,
    _filter_date,
    _filter_get,
    _filter_random,
    _filter_shuffle,
    _filter_urlencode,
)
from kida.environment.filters._numbers import (
    _filter_abs,
    _filter_commas,
    _filter_decimal,
    _filter_filesizeformat,
    _filter_format_number,
    _filter_max,
    _filter_min,
    _filter_round,
    _filter_sum,
)
from kida.environment.filters._string import (
    _filter_capitalize,
    _filter_center,
    _filter_format,
    _filter_indent,
    _filter_lower,
    _filter_pluralize,
    _filter_replace,
    _filter_slug,
    _filter_title,
    _filter_trim,
    _filter_truncate,
    _filter_upper,
    _filter_wordcount,
    _filter_wordwrap,
)
from kida.environment.filters._type_conversion import (
    _filter_float,
    _filter_int,
    _filter_list,
    _filter_string,
    _filter_tojson,
    _filter_typeof,
)
from kida.environment.filters._validation import _filter_default, _filter_require

# Default filters - comprehensive set matching Jinja2
DEFAULT_FILTERS: dict[str, Callable[..., Any]] = {
    # Basic transformations
    "abs": _filter_abs,
    "capitalize": _filter_capitalize,
    "center": _filter_center,
    "d": _filter_default,
    "date": _filter_date,
    "default": _filter_default,
    "e": _filter_escape,
    "escape": _filter_escape,
    "first": _filter_first,
    "format": _filter_format,
    "indent": _filter_indent,
    "int": _filter_int,
    "join": _filter_join,
    "last": _filter_last,
    "length": _filter_length,
    "list": _filter_list,
    "lower": _filter_lower,
    "pluralize": _filter_pluralize,
    "pprint": _filter_pprint,
    "replace": _filter_replace,
    "reverse": _filter_reverse,
    "safe": _filter_safe,
    "sort": _filter_sort,
    "string": _filter_string,
    "striptags": _filter_striptags,
    "title": _filter_title,
    "trim": _filter_trim,
    "truncate": _filter_truncate,
    "upper": _filter_upper,
    "urlencode": _filter_urlencode,
    "wordwrap": _filter_wordwrap,
    "xmlattr": _filter_xmlattr,
    # Serialization
    "tojson": _filter_tojson,
    # Collections
    "attr": _filter_attr,
    "batch": _filter_batch,
    "groupby": _filter_groupby,
    "map": _filter_map,
    "max": _filter_max,
    "min": _filter_min,
    "reject": _filter_reject,
    "rejectattr": _filter_rejectattr,
    "select": _filter_select,
    "selectattr": _filter_selectattr,
    "skip": _filter_skip,
    "slice": _filter_slice,
    "slug": _filter_slug,
    "sum": _filter_sum,
    "take": _filter_take,
    "unique": _filter_unique,
    "classes": _filter_classes,
    "compact": _filter_compact,
    # Additional filters
    "count": _filter_length,  # alias
    "decimal": _filter_decimal,
    "dictsort": _filter_dictsort,
    "filesizeformat": _filter_filesizeformat,
    "float": _filter_float,
    "round": _filter_round,
    "strip": _filter_trim,  # alias
    "wordcount": _filter_wordcount,
    "format_number": _filter_format_number,
    "commas": _filter_commas,
    # Debugging and validation filters
    "require": _filter_require,
    "debug": _filter_debug,
    "typeof": _filter_typeof,
    # Safe access filter (avoids Python method name conflicts)
    "get": _filter_get,
    # Randomization filters (impure - non-deterministic)
    "random": _filter_random,
    "shuffle": _filter_shuffle,
    # CSP nonce injection
    "csp_nonce": _filter_csp_nonce,
}

# Re-exports for kida.environment.filters public API
__all__ = [
    "DEFAULT_FILTERS",
    "SORT_KEY_NONE",
    "_filter_attr",
    "_filter_batch",
    "_filter_classes",
    "_filter_compact",
    "_filter_debug",
    "_filter_decimal",
    "_filter_default",
    "_filter_dictsort",
    "_filter_escape",
    "_filter_filesizeformat",
    "_filter_first",
    "_filter_format",
    "_filter_get",
    "_filter_groupby",
    "_filter_join",
    "_filter_last",
    "_filter_length",
    "_filter_list",
    "_filter_map",
    "_filter_max",
    "_filter_min",
    "_filter_pprint",
    "_filter_random",
    "_filter_reject",
    "_filter_rejectattr",
    "_filter_require",
    "_filter_reverse",
    "_filter_safe",
    "_filter_select",
    "_filter_selectattr",
    "_filter_shuffle",
    "_filter_skip",
    "_filter_slice",
    "_filter_sort",
    "_filter_string",
    "_filter_sum",
    "_filter_take",
    "_filter_tojson",
    "_filter_trim",
    "_filter_typeof",
    "_filter_unique",
    "_make_sort_key_numeric",
    "_make_sort_key_string",
]
