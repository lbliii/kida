---
title: Sandboxed Environment
description: Run untrusted templates safely with configurable security policies
draft: false
weight: 55
lang: en
type: doc
tags:
  - advanced
  - security
  - sandbox
keywords:
  - sandbox
  - SandboxedEnvironment
  - security policy
  - untrusted templates
icon: shield
---

# Sandboxed Environment

When templates come from untrusted sources -- user-submitted CMS content, customer-editable email templates, or plugin systems -- you need to prevent them from accessing sensitive data or executing arbitrary code. `SandboxedEnvironment` is a drop-in replacement for `Environment` that intercepts attribute access, function calls, imports, and resource consumption at render time.

```python
from kida import SandboxedEnvironment
```

All templates compiled by this environment are subject to sandbox restrictions. No code changes are needed in your templates -- the sandbox operates transparently at the engine level.

## Quick Start

```python
from kida import SandboxedEnvironment

env = SandboxedEnvironment()

# Safe: normal attribute access works
tmpl = env.from_string("Hello, {{ user.name }}!")
tmpl.render(user={"name": "Alice"})  # "Hello, Alice!"

# Blocked: dunder access raises SecurityError
tmpl = env.from_string("{{ user.__class__.__mro__ }}")
tmpl.render(user="hello")  # raises SecurityError
```

The default policy blocks all dunder attributes (except a safe subset like `__len__` and `__iter__`), prevents access to function, type, and code objects, disables imports, and limits `range()` to 10,000 elements.

## Security Policy Configuration

Customize the sandbox by passing a `SandboxPolicy` to the environment:

```python
from kida.sandbox import SandboxPolicy, SandboxedEnvironment

policy = SandboxPolicy(
    allowed_attributes={"name", "title", "email", "items"},
    blocked_types={type, type(lambda: 0)},
    max_output_size=50_000,
    max_range=1000,
)
env = SandboxedEnvironment(sandbox_policy=policy)
```

### All Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `allowed_attributes` | `frozenset[str] \| None` | `None` | If set, only these attribute names are accessible (plus safe collection methods). `None` means all non-blocked attributes are allowed. |
| `blocked_attributes` | `frozenset[str]` | `frozenset()` | Additional attribute names to block, merged with the built-in blocked set. |
| `blocked_types` | `frozenset[type]` | `frozenset()` | Object types that cannot be accessed at all. Function, type, and code objects are always blocked regardless of this setting. |
| `allow_import` | `bool` | `False` | Whether `__import__` is available in templates. |
| `allow_mutating_methods` | `bool` | `False` | Whether mutating collection methods (`append`, `pop`, `clear`, etc.) are accessible. |
| `allow_calling` | `frozenset[str] \| None` | `None` | Set of type names whose instances may be called. `None` permits all callables. An empty `frozenset()` blocks all calls. |
| `max_output_size` | `int \| None` | `None` | Maximum render output length in characters. `None` means unlimited. |
| `max_range` | `int` | `10000` | Maximum `range()` size allowed in templates. |

`SandboxPolicy` is a frozen dataclass -- construct a new instance for each configuration.

## Method Restrictions

The sandbox distinguishes between read-only and mutating methods on built-in collection and string types.

### Read-Only Methods (Always Allowed)

These methods are allowed by default because they do not modify application state:

| Type | Methods |
|------|---------|
| **dict** | `items`, `keys`, `values`, `get`, `copy` |
| **sequence** | `count`, `index` |
| **set** | `union`, `intersection`, `difference`, `issubset`, `issuperset`, `symmetric_difference` |
| **string** | `startswith`, `endswith`, `strip`, `lstrip`, `rstrip`, `split`, `rsplit`, `join`, `replace`, `lower`, `upper`, `title`, `capitalize`, `format`, `encode`, `decode`, `find`, `rfind`, `removeprefix`, `removesuffix` |

### Mutating Methods (Blocked by Default)

These methods are blocked unless the policy explicitly opts in:

```
append, extend, insert, pop, remove, sort, reverse, clear, update, add, discard
```

See [Allowlists](#allowlists) for how to enable them.

### Dunder Access

Most dunder attributes are blocked. The following safe subset is permitted:

- `__len__` -- needed for `length` filter and truthiness checks
- `__iter__` -- needed for `{% for %}` loops
- `__contains__` -- needed for `in` operator
- `__getitem__` -- needed for bracket access (`items[0]`)
- `__str__`, `__repr__` -- needed for string output

All other dunder attributes (`__class__`, `__subclasses__`, `__bases__`, `__mro__`, `__dict__`, `__globals__`, etc.) are unconditionally blocked.

## Call-Time Safety Checking

The sandbox intercepts every attribute access and function call at render time -- not at compile time. This means:

1. **Attribute access** is checked against the policy before the value is returned. Blocked attributes raise `SecurityError` immediately.
2. **Type checks** run on the object being accessed. If the object's type is in the unsafe set (or `blocked_types`), access is denied regardless of the attribute name.
3. **Function calls** are intercepted when `allow_calling` is configured. The callable's type name is checked against the allowlist before invocation.

```python
from kida import SandboxedEnvironment, SecurityError

env = SandboxedEnvironment()

try:
    tmpl = env.from_string("{{ func.__globals__ }}")
    tmpl.render(func=lambda: None)
except SecurityError as e:
    print(e)  # "Access to attribute '__globals__' is blocked by sandbox policy"
```

The sandbox also replaces `range()` with a size-limited version:

```python
env = SandboxedEnvironment()
tmpl = env.from_string("{% for i in range(999999) %}x{% endfor %}")
tmpl.render()  # raises SecurityError: range() size 999999 exceeds sandbox limit of 10000
```

## Allowlists

### allow_mutating_methods

Enable mutating methods when templates need to build data structures:

```python
from kida.sandbox import SandboxPolicy, SandboxedEnvironment

policy = SandboxPolicy(allow_mutating_methods=True)
env = SandboxedEnvironment(sandbox_policy=policy)

tmpl = env.from_string("""
{% set items = [] %}
{% for name in names %}
  {% do items.append(name.upper()) %}
{% endfor %}
{{ items | join(", ") }}
""")
tmpl.render(names=["alice", "bob"])
```

> **Warning**: Enabling mutating methods allows templates to modify objects passed in via the context. Only enable this when templates are semi-trusted or context objects are copies.

### allow_calling

Restrict which types of callables templates can invoke:

```python
from kida.sandbox import SandboxPolicy, SandboxedEnvironment

# Only allow calling methods on built-in types
policy = SandboxPolicy(
    allow_calling=frozenset({"builtin_function_or_method", "method"}),
)
env = SandboxedEnvironment(sandbox_policy=policy)
```

When `allow_calling` is `None` (the default), all callables obtained via attribute access are permitted -- attribute-level checks still apply. Set it to an empty `frozenset()` to block all function calls:

```python
# Block all calls -- templates can only read attributes
policy = SandboxPolicy(allow_calling=frozenset())
```

### allowed_attributes

Lock down attribute access to an explicit allowlist:

```python
policy = SandboxPolicy(
    allowed_attributes=frozenset({"name", "email", "title", "created_at"}),
)
env = SandboxedEnvironment(sandbox_policy=policy)

# Only .name, .email, .title, .created_at are accessible
# (plus safe collection methods like .items, .keys, .get)
```

When `allowed_attributes` is set, any attribute not in the allowlist and not in the safe collection methods set is blocked.

## Examples

### CMS with User-Submitted Templates

```python
from kida.sandbox import SandboxPolicy, SandboxedEnvironment

policy = SandboxPolicy(
    allowed_attributes=frozenset({
        "title", "body", "author", "published_at",
        "name", "email", "avatar_url",
        "items", "keys", "values",
    }),
    max_output_size=100_000,  # 100KB limit
    max_range=100,
)
env = SandboxedEnvironment(sandbox_policy=policy)

user_template = db.get_template(page_id)
tmpl = env.from_string(user_template)
html = tmpl.render(page=page, site=site_config)
```

### Customer-Editable Email Templates

```python
from kida.sandbox import SandboxPolicy, SandboxedEnvironment

policy = SandboxPolicy(
    allowed_attributes=frozenset({
        "first_name", "last_name", "email", "company",
        "order_id", "total", "items",
        "name", "quantity", "price",
    }),
    allow_calling=frozenset(),  # No function calls
    max_output_size=50_000,
    max_range=50,
)
env = SandboxedEnvironment(sandbox_policy=policy)

template_source = customer.get_email_template("welcome")
tmpl = env.from_string(template_source)
html = tmpl.render(user=user, order=order)
```

### Plugin System with Semi-Trusted Code

```python
from kida.sandbox import SandboxPolicy, SandboxedEnvironment

policy = SandboxPolicy(
    allow_mutating_methods=True,   # Plugins may build data
    allow_import=False,            # No imports
    blocked_attributes=frozenset({"password", "secret_key", "api_key"}),
    blocked_types=frozenset({type, type(lambda: 0)}),
    max_range=5000,
)
env = SandboxedEnvironment(sandbox_policy=policy)
```

## Limitations

- **Compile-time only via runtime checks.** The sandbox does not statically analyze templates. It intercepts attribute access and calls at render time, so a blocked operation only raises `SecurityError` when the code path executes.
- **No CPU time limits.** The sandbox limits `range()` size and output length, but cannot prevent infinite loops or expensive computations. Use OS-level timeouts (e.g., `signal.alarm` or process-level limits) for CPU protection.
- **No filesystem or network restrictions.** The sandbox controls template-level access. If a context object exposes methods that perform I/O, the sandbox does not intercept the I/O itself -- only access to the method. Audit what you pass into the template context.
- **Mutating methods affect the caller.** When `allow_mutating_methods=True`, templates can modify mutable objects passed in the context. Pass copies if you need to preserve originals.
- **Type-name matching for allow_calling.** The `allow_calling` option matches on `type(obj).__name__`, not the actual type object. Two unrelated types with the same `__name__` would both be permitted.

## See Also

- [[docs/advanced/security|Security Hardening]] -- Context-specific escaping, URL validation, and resource limits
- [[docs/reference/configuration|Configuration]] -- Environment options reference
