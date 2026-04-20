**`strict_undefined` defaults to `True`** — `Environment(strict_undefined=...)` now defaults to `True`, aligning with the library's documented "strict-by-default" stance. Missing variables **and** missing attribute access now raise `UndefinedError` with a descriptive message (variable/attribute/key). Previously, the flag was opt-in and missing attributes silently rendered as `""`, contradicting the `__init__.py` docstring.

**Migration**: Update templates to use `is defined`, `??` (null-coalescing), or `| default(...)` for optional values. Example:

```kida
{# Before (lenient) #}
{% if user.nickname %}{{ user.nickname }}{% end %}

{# After (strict-friendly) #}
{% if user.nickname is defined and user.nickname %}{{ user.nickname }}{% end %}
{{ user.nickname ?? "" }}
{{ user.nickname | default("") }}
```

**Escape hatch**: Pass `strict_undefined=False` on the Environment to restore the previous lenient behavior. This is recommended only as a transitional shim.
