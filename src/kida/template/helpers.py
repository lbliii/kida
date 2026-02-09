"""Pure runtime helper functions injected into the template namespace.

These functions are called by compiled template code at render time.
None of them close over Environment state — they are pure functions
that use only their parameters and deferred imports.

Thread-Safety:
All functions are stateless and safe for concurrent use.

"""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter as _perf_counter
from typing import Any

from kida.render_accumulator import get_accumulator as _get_accumulator
from kida.utils.html import _SPACELESS_RE, Markup

# =============================================================================
# Shared Base Namespace (Performance Optimization)
# =============================================================================
# Static entries shared across all Template instances to avoid repeated
# dictionary construction. These are copied once per Template.__init__
# instead of constructed fresh each time.
#
# Thread-Safety: This dict is read-only after module load.
# =============================================================================

STATIC_NAMESPACE: dict[str, Any] = {
    "__builtins__": {"__import__": __import__},
    "_Markup": Markup,
    "_str": str,
    "_len": len,
    "_range": range,
    "_list": list,
    "_dict": dict,
    "_set": set,
    "_tuple": tuple,
    "_isinstance": isinstance,
    "_bool": bool,
    "_int": int,
    "_float": float,
    "_get_accumulator": _get_accumulator,
    "_perf_counter": _perf_counter,
}


def record_filter_usage(acc: Any, name: str, result: Any) -> Any:
    """Record filter usage for profiling, returning the result unchanged.

    Called by compiled code for every filter invocation. When profiling
    is disabled (acc is None), the cost is a single falsy check + return.

    Args:
        acc: RenderAccumulator instance, or None when profiling is off
        name: Filter name for recording
        result: The filter's return value (passed through unchanged)

    Returns:
        The result argument unchanged.
    """
    if acc is not None:
        acc.record_filter(name)
    return result


def record_macro_usage(acc: Any, name: str, result: Any) -> Any:
    """Record macro ({% def %}) call for profiling, returning the result unchanged.

    Called by compiled code for every macro invocation. When profiling
    is disabled (acc is None), the cost is a single falsy check + return.

    Args:
        acc: RenderAccumulator instance, or None when profiling is off
        name: Macro/def name for recording
        result: The macro's return value (passed through unchanged)

    Returns:
        The result argument unchanged.
    """
    if acc is not None:
        acc.record_macro(name)
    return result


# Add to STATIC_NAMESPACE after functions are defined
STATIC_NAMESPACE["_record_filter"] = record_filter_usage
STATIC_NAMESPACE["_record_macro"] = record_macro_usage


def lookup(ctx: dict[str, Any], var_name: str) -> Any:
    """Look up a variable in strict mode.

    In strict mode, undefined variables raise UndefinedError instead
    of silently returning None. This catches typos and missing variables
    early, improving debugging experience.

    Performance:
        - Fast path (defined var): O(1) dict lookup
        - Error path: Raises UndefinedError with template context
    """
    from kida.environment.exceptions import UndefinedError, build_source_snippet
    from kida.render_context import get_render_context

    try:
        return ctx[var_name]
    except KeyError:
        # Get template context from RenderContext for better error messages
        render_ctx = get_render_context()
        template_name = render_ctx.template_name if render_ctx else None
        lineno = render_ctx.line if render_ctx else None
        source = render_ctx.source if render_ctx else None
        snippet = build_source_snippet(source, lineno) if source and lineno else None
        raise UndefinedError(
            var_name,
            template_name,
            lineno,
            available_names=frozenset(ctx.keys()),
            source_snippet=snippet,
        ) from None


def lookup_scope(
    ctx: dict[str, Any], scope_stack: list[dict[str, Any]], var_name: str
) -> Any:
    """Lookup variable in scope stack (top to bottom), then ctx.

    Checks scopes from innermost to outermost, then falls back to ctx.
    Raises UndefinedError if not found (strict mode).
    """
    # Check scope stack from top (innermost) to bottom (outermost)
    for scope in reversed(scope_stack):
        if var_name in scope:
            return scope[var_name]

    # Fall back to ctx
    if var_name in ctx:
        return ctx[var_name]

    # Not found - raise UndefinedError with available names for suggestions
    from kida.environment.exceptions import UndefinedError, build_source_snippet
    from kida.render_context import get_render_context

    render_ctx = get_render_context()
    template_name = render_ctx.template_name if render_ctx else None
    lineno = render_ctx.line if render_ctx else None
    source = render_ctx.source if render_ctx else None
    snippet = build_source_snippet(source, lineno) if source and lineno else None

    all_names: set[str] = set(ctx.keys())
    for scope in scope_stack:
        all_names.update(scope.keys())

    raise UndefinedError(
        var_name,
        template_name,
        lineno,
        available_names=frozenset(all_names),
        source_snippet=snippet,
    ) from None


def default_safe(
    value_fn: Callable[[], Any],
    default_value: Any = "",
    boolean: bool = False,
) -> Any:
    """Safe default filter that works with strict mode.

    In strict mode, the value expression might raise UndefinedError.
    This helper catches that and returns the default value.

    Args:
        value_fn: A lambda that evaluates the value expression
        default_value: The fallback value if undefined or None/falsy
        boolean: If True, check for falsy values; if False, check for None only

    Returns:
        The value if defined and valid, otherwise the default
    """
    from kida.environment.exceptions import UndefinedError

    try:
        value = value_fn()
    except UndefinedError:
        return default_value

    # Apply default filter logic
    if boolean:
        # Return default if value is falsy
        return value if value else default_value
    else:
        # Return default only if value is None
        return value if value is not None else default_value


def is_defined(value_fn: Callable[[], Any]) -> bool:
    """Check if a value is defined in strict mode.

    In strict mode, we need to catch UndefinedError to determine
    if a variable is defined.

    Args:
        value_fn: A lambda that evaluates the value expression

    Returns:
        True if the value is defined (doesn't raise UndefinedError
        and is not None), False otherwise
    """
    from kida.environment.exceptions import UndefinedError

    try:
        value = value_fn()
        return value is not None
    except UndefinedError:
        return False


def null_coalesce(left_fn: Callable[[], Any], right_fn: Callable[[], Any]) -> Any:
    """Safe null coalescing that handles undefined variables.

    In strict mode, the left expression might raise UndefinedError.
    This helper catches that and returns the right value.

    Unlike the default filter:
    - Returns right ONLY if left is None or undefined
    - Does NOT treat falsy values (0, '', False, []) as needing replacement

    Args:
        left_fn: A lambda that evaluates the left expression
        right_fn: A lambda that evaluates the right expression (lazy)

    Returns:
        The left value if defined and not None, otherwise the right value
    """
    from kida.environment.exceptions import UndefinedError

    try:
        value = left_fn()
    except UndefinedError:
        return right_fn()

    # Return right only if left is None
    return value if value is not None else right_fn()


def spaceless(html: str) -> str:
    """Remove whitespace between HTML tags.

    RFC: kida-modern-syntax-features

    Example:
        {% spaceless %}
        <ul>
            <li>a</li>
        </ul>
        {% end %}
        Output: <ul><li>a</li></ul>
    """
    return _SPACELESS_RE.sub("><", html).strip()


def coerce_numeric(value: Any) -> int | float:
    """Coerce value to numeric type for arithmetic operations.

    Handles Markup objects (from macros) and strings that represent numbers.
    This prevents string multiplication when doing arithmetic with macro results.

    Example:
        macro returns Markup('  24  ')
        coerce_numeric(Markup('  24  ')) -> 24

    Args:
        value: Any value, typically Markup from macro or filter result

    Returns:
        int if value parses as integer, float if decimal, 0 for non-numeric
    """
    # Fast path: already numeric (but not bool, which is a subclass of int)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value

    # Convert to string and strip whitespace
    s = str(value).strip()

    # Try int first (more common), then float
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            # Non-numeric string defaults to 0
            return 0


def str_safe(value: Any) -> str:
    """Convert value to string, treating None as empty string.

    This is used for template output so that optional chaining
    expressions that evaluate to None produce empty output rather
    than the literal string 'None'.

    RFC: kida-modern-syntax-features — needed for optional chaining.
    """
    if value is None:
        return ""
    return str(value)
