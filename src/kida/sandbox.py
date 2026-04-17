"""Sandboxed template execution — defense-in-depth for risky templates.

``SandboxedEnvironment`` restricts attribute access, callable types, range
sizes, and imports to reduce the blast radius of a template that attempts to
reach out of its intended context. It is **not** an isolation boundary: it
does not restrict CPU, memory, or wall-clock use; it does not sandbox objects
you place in the render context; and the Python object model is large enough
that novel escapes are possible.

**Never render fully untrusted template source against a production context
with this sandbox alone.** Combine it with OS-level isolation (process
boundary, container, seccomp, WASM, etc.), a curated render context of
primitive types, and a wall-clock timeout. See ``SECURITY.md`` for the full
threat model and hardening guidance.

Usage::

    from kida import SandboxedEnvironment

    env = SandboxedEnvironment()
    # Templates cannot access __dunder__ attributes, call unsafe functions,
    # or import modules.
    env.from_string("{{ user.name }}").render(user=user)  # OK
    env.from_string("{{ user.__class__ }}").render(user=user)  # blocked

Custom policy::

    from kida.sandbox import SandboxPolicy, SandboxedEnvironment

    policy = SandboxPolicy(
        allowed_attributes={"name", "title", "items", "keys", "values"},
        blocked_types={type, type(lambda: 0)},
    )
    env = SandboxedEnvironment(sandbox_policy=policy)

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast, final

if TYPE_CHECKING:
    from collections.abc import Mapping

from kida.environment.core import Environment
from kida.exceptions import ErrorCode, TemplateError

# Types that are never safe to expose in templates
_UNSAFE_TYPES = frozenset(
    {
        type,  # type() can access metaclasses
        type(lambda: 0),  # function type — can access __globals__
        type((lambda: 0).__code__),  # code objects
        type(type.__dict__["__dict__"]),  # getset_descriptor
    }
)

# Attribute names that are always blocked
_BLOCKED_ATTRS = frozenset(
    {
        "__class__",
        "__subclasses__",
        "__bases__",
        "__mro__",
        "__dict__",
        "__globals__",
        "__code__",
        "__func__",
        "__self__",
        "__module__",
        "__init__",
        "__new__",
        "__del__",
        "__init_subclass__",
        "__set_name__",
        "__reduce__",
        "__reduce_ex__",
        "__getattr__",
        "__setattr__",
        "__delattr__",
        "__getattribute__",
        "__import__",
        "__loader__",
        "__spec__",
        "__builtins__",
        # Descriptor protocol
        "__get__",
        "__set__",
        "__delete__",
        # Frame/traceback access
        "gi_frame",
        "gi_code",
        "cr_frame",
        "cr_code",
        "ag_frame",
        "ag_code",
        "f_locals",
        "f_globals",
        "f_code",
        "f_builtins",
        "tb_frame",
        "tb_next",
        # OS-level
        "func_globals",
        "func_code",
    }
)

# Read-only method names safe on common collection/string types.
# Mutating methods (append, pop, clear, etc.) are excluded by default to
# prevent untrusted templates from modifying application state.
_SAFE_COLLECTION_METHODS = frozenset(
    {
        # dict read-only
        "items",
        "keys",
        "values",
        "get",
        "copy",
        # sequence read-only
        "count",
        "index",
        # set read-only
        "union",
        "intersection",
        "difference",
        "issubset",
        "issuperset",
        "symmetric_difference",
        # string methods (all non-mutating)
        "startswith",
        "endswith",
        "strip",
        "lstrip",
        "rstrip",
        "split",
        "rsplit",
        "join",
        "replace",
        "lower",
        "upper",
        "title",
        "capitalize",
        "format",
        "encode",
        "decode",
        "find",
        "rfind",
        "removeprefix",
        "removesuffix",
    }
)

# Mutating methods that are allowed only when the policy opts in.
_MUTATING_COLLECTION_METHODS = frozenset(
    {
        "append",
        "extend",
        "insert",
        "pop",
        "remove",
        "sort",
        "reverse",
        "clear",
        "update",
        "add",
        "discard",
    }
)


@final
@dataclass(frozen=True)
class SandboxPolicy:
    """Configuration for sandbox restrictions.

    Attributes:
        allowed_attributes: If set, only these attribute names are accessible
            (plus safe collection methods). If None, all non-blocked attributes
            are allowed.
        blocked_attributes: Additional attribute names to block (merged with
            the built-in blocked set).
        blocked_types: Object types that cannot be accessed at all.
            Default blocks function, type, and code objects.
        allow_import: Whether ``__import__`` is available. Default: False.
        allow_mutating_methods: Whether mutating collection methods (append,
            pop, clear, etc.) are accessible. Default: False.
        allow_calling: Set of type names whose instances may be called.
            If None (default), all callables obtained via attribute access
            are allowed. Pass an empty frozenset to block all calls.
        max_output_size: Maximum render output length in characters.
            None means unlimited.
        max_range: Maximum range() size. Default: 10000.
    """

    allowed_attributes: frozenset[str] | None = None
    blocked_attributes: frozenset[str] = frozenset()
    blocked_types: frozenset[type] = frozenset()
    allow_import: bool = False
    allow_mutating_methods: bool = False
    allow_calling: frozenset[str] | None = None
    max_output_size: int | None = None
    max_range: int = 10000


DEFAULT_POLICY = SandboxPolicy()


class SecurityError(TemplateError):
    """Raised when a sandbox policy violation is detected.

    Includes an error code and actionable suggestion for resolving the
    violation. All security errors inherit from TemplateError, so they
    are caught by ``except TemplateError``.

    Example::

        SecurityError: Access to attribute '__class__' is blocked by sandbox policy
          Hint: Remove the attribute access, or add '__class__' to
                SandboxPolicy(allowed_attributes=...) if you trust this template.
          Docs: https://lbliii.github.io/kida/docs/errors/#k-sec-001
    """

    def __init__(
        self,
        message: str,
        *,
        code: ErrorCode | None = None,
        suggestion: str | None = None,
    ):
        self.message = message
        self.code = code
        self.suggestion = suggestion
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        parts = [self.message]
        if self.suggestion:
            parts.append(f"  Hint: {self.suggestion}")
        if self.code:
            parts.append(f"  Docs: {self.code.docs_url}")
        return "\n".join(parts)


def _is_attr_blocked(name: str, policy: SandboxPolicy) -> bool:
    """Check if an attribute name is blocked by the policy."""
    if name in _BLOCKED_ATTRS or name in policy.blocked_attributes:
        return True
    # Block all dunder access except __len__, __iter__, __contains__, __getitem__
    if name.startswith("__") and name.endswith("__"):
        return name not in {
            "__len__",
            "__iter__",
            "__contains__",
            "__getitem__",
            "__str__",
            "__repr__",
        }
    # Check mutating methods — blocked unless policy opts in
    if name in _MUTATING_COLLECTION_METHODS:
        return not policy.allow_mutating_methods
    if policy.allowed_attributes is not None:
        return name not in policy.allowed_attributes and name not in _SAFE_COLLECTION_METHODS
    return False


def _is_type_blocked(obj: object, policy: SandboxPolicy) -> bool:
    """Check if an object's type is blocked."""
    obj_type = type(obj)
    return obj_type in _UNSAFE_TYPES or obj_type in policy.blocked_types


def _make_sandboxed_getattr(policy: SandboxPolicy):
    """Create a sandboxed version of safe_getattr."""
    from kida.template.helpers import _MISS, UNDEFINED

    def sandboxed_getattr(obj: object, name: str) -> object:
        if obj is None:
            return UNDEFINED
        if _is_attr_blocked(name, policy):
            raise SecurityError(
                f"Access to attribute {name!r} is blocked by sandbox policy",
                code=ErrorCode.BLOCKED_ATTRIBUTE,
                suggestion=f"Remove the attribute access, or add {name!r} to "
                "SandboxPolicy(allowed_attributes=...) if you trust this template.",
            )
        if _is_type_blocked(obj, policy):
            raise SecurityError(
                f"Access to objects of type {type(obj).__name__!r} is blocked by sandbox policy",
                code=ErrorCode.BLOCKED_TYPE,
                suggestion=f"Remove {type(obj).__name__!r} from SandboxPolicy(blocked_types=...) "
                "if you trust this template, or avoid passing objects of this type to the template.",
            )
        # Delegate to standard resolution, but with checks
        if type(obj) is dict:
            d = cast("dict[str, Any]", obj)
            val = d.get(name, _MISS)
            if val is not _MISS:
                return "" if val is None else val
            val = getattr(obj, name, _MISS)
            if val is not _MISS:
                return "" if val is None else val
            return UNDEFINED
        if isinstance(obj, dict):
            d = cast("dict[str, Any]", obj)
            try:
                val = d[name]
                return "" if val is None else val
            except KeyError:
                try:
                    val = getattr(obj, name)
                    return "" if val is None else val
                except AttributeError:
                    return UNDEFINED
        val = getattr(obj, name, _MISS)
        if val is not _MISS:
            return "" if val is None else val
        try:
            val = cast("Mapping[str, Any]", obj)[name]
            return "" if val is None else val
        except KeyError, TypeError:
            return UNDEFINED

    return sandboxed_getattr


def _make_sandboxed_getattr_none(policy: SandboxPolicy):
    """Create a sandboxed version of getattr_preserve_none."""
    from kida.template.helpers import _MISS

    def sandboxed_getattr_none(obj: object, name: str) -> object:
        if _is_attr_blocked(name, policy):
            raise SecurityError(
                f"Access to attribute {name!r} is blocked by sandbox policy",
                code=ErrorCode.BLOCKED_ATTRIBUTE,
                suggestion=f"Remove the attribute access, or add {name!r} to "
                "SandboxPolicy(allowed_attributes=...) if you trust this template.",
            )
        if obj is not None and _is_type_blocked(obj, policy):
            raise SecurityError(
                f"Access to objects of type {type(obj).__name__!r} is blocked by sandbox policy",
                code=ErrorCode.BLOCKED_TYPE,
                suggestion=f"Remove {type(obj).__name__!r} from SandboxPolicy(blocked_types=...) "
                "if you trust this template, or avoid passing objects of this type to the template.",
            )
        if type(obj) is dict:
            d = cast("dict[str, Any]", obj)
            val = d.get(name, _MISS)
            if val is not _MISS:
                return val
            val = getattr(obj, name, _MISS)
            if val is not _MISS:
                return val
            return None
        if isinstance(obj, dict):
            d = cast("dict[str, Any]", obj)
            try:
                return d[name]
            except KeyError:
                try:
                    return getattr(obj, name)
                except AttributeError:
                    return None
        val = getattr(obj, name, _MISS)
        if val is not _MISS:
            return val
        try:
            return cast("Mapping[str, Any]", obj)[name]
        except KeyError, TypeError:
            return None

    return sandboxed_getattr_none


def _make_sandboxed_range(policy: SandboxPolicy):
    """Create a range() that enforces max_range."""
    max_range = policy.max_range

    def sandboxed_range(*args: int) -> range:
        r = range(*args)
        if len(r) > max_range:
            raise SecurityError(
                f"range() size {len(r)} exceeds sandbox limit of {max_range}",
                code=ErrorCode.RANGE_LIMIT,
                suggestion=f"Reduce the range size, or increase "
                f"SandboxPolicy(max_range={max_range * 10}) if this is intentional.",
            )
        return r

    return sandboxed_range


@dataclass
class SandboxedEnvironment(Environment):
    """Environment subclass that enforces sandbox restrictions.

    All templates compiled by this environment use sandboxed attribute access,
    restricted builtins, and policy-enforced limits.

    The sandbox intercepts:
    - Attribute access (blocks __dunder__, unsafe types)
    - ``__import__`` (disabled by default)
    - ``range()`` (size-limited)
    - Template output (optional size limit)

    Example::

        env = SandboxedEnvironment()
        tmpl = env.from_string("{{ user.name }}")
        tmpl.render(user={"name": "Alice"})  # OK

        tmpl = env.from_string("{{ user.__class__.__mro__ }}")
        tmpl.render(user="hello")  # raises SecurityError

    Custom policy::

        from kida.sandbox import SandboxPolicy
        policy = SandboxPolicy(allowed_attributes=frozenset({"name", "email"}))
        env = SandboxedEnvironment(sandbox_policy=policy)

    """

    sandbox_policy: SandboxPolicy | None = None

    def __post_init__(self) -> None:
        self._sandbox_policy = self.sandbox_policy or DEFAULT_POLICY
        super().__post_init__()
        # Replace range() in globals with sandboxed version
        self.globals["range"] = _make_sandboxed_range(self._sandbox_policy)

    def _get_sandbox_policy(self) -> SandboxPolicy:
        return self._sandbox_policy


def _make_sandboxed_call(policy: SandboxPolicy):
    """Create a call interceptor that blocks unsafe callables.

    When ``policy.allow_calling`` is None, all callables are permitted
    (attribute-level checks are still enforced).  When set to a
    frozenset of type names, only instances of those types may be called.
    Blocked types (function, type, code) are always denied.
    """

    def sandboxed_call(func: Any, *args: Any, **kwargs: Any) -> Any:
        # Always block calls to fundamentally unsafe types
        if _is_type_blocked(func, policy):
            raise SecurityError(
                f"Calling objects of type {type(func).__name__!r} is blocked by sandbox policy",
                code=ErrorCode.BLOCKED_CALLABLE,
                suggestion=f"Remove {type(func).__name__!r} from SandboxPolicy(blocked_types=...) "
                "if you trust this template, or avoid passing callables of this type.",
            )
        # If allow_calling is set, enforce the allowlist
        if policy.allow_calling is not None:
            type_name = type(func).__name__
            if type_name not in policy.allow_calling:
                raise SecurityError(
                    f"Calling objects of type {type_name!r} is not permitted by sandbox policy",
                    code=ErrorCode.BLOCKED_CALLABLE,
                    suggestion=f"Add {type_name!r} to "
                    "SandboxPolicy(allow_calling=frozenset({...})) to permit calls to this type.",
                )
        return func(*args, **kwargs)

    return sandboxed_call


def patch_template_namespace(namespace: dict[str, Any], policy: SandboxPolicy) -> None:
    """Patch a template namespace dict to enforce sandbox restrictions.

    Called by Template.__init__ when the environment is a SandboxedEnvironment.
    Replaces unsafe functions with sandboxed versions.
    """
    # Replace attribute access functions
    namespace["_getattr"] = _make_sandboxed_getattr(policy)
    namespace["_getattr_none"] = _make_sandboxed_getattr_none(policy)

    # Replace call helper with sandboxed version that blocks unsafe callables
    namespace["_sandboxed_call"] = _make_sandboxed_call(policy)

    # Restrict builtins
    if policy.allow_import:
        namespace["__builtins__"] = {"__import__": __import__}
    else:
        namespace["__builtins__"] = {}

    # Replace range with size-limited version
    namespace["_range"] = _make_sandboxed_range(policy)

    # Remove direct env access
    namespace.pop("_env", None)
