---
title: Caching
description: Block-level output caching in templates
draft: false
weight: 70
lang: en
type: doc
tags:
- syntax
- caching
keywords:
- cache
- performance
- optimization
icon: database
---

# Caching

Kida provides built-in block-level caching to improve template rendering performance.

## Cache Directive

Cache expensive template fragments:

```kida
{% cache "sidebar" %}
    {# This content is computed once, then cached #}
    {% for item in expensive_query() %}
        {{ item.render() }}
    {% end %}
{% end %}
```

## Dynamic Cache Keys

Include variables in the cache key:

```kida
{% cache "user-profile-" + user.id %}
    {{ render_user_profile(user) }}
{% end %}
```

Multiple components:

```kida
{% cache "page-" + page.id + "-" + page.updated_at %}
    {{ page.content | markdown }}
{% end %}
```

## Cache Configuration

Configure caching in the Environment:

```python
from kida import Environment

env = Environment(
    fragment_cache_size=1000,  # Max cached fragments
    fragment_ttl=300.0,        # TTL in seconds (5 minutes)
)
```

## Cache Stats

Check cache statistics:

```python
info = env.cache_info()
print(info["fragment"])
# {'size': 50, 'max_size': 1000, 'hits': 500, 'misses': 50}
```

## Clear Cache

Clear cached fragments:

```python
# Clear all fragments
env.clear_fragment_cache()

# Clear all caches (templates + fragments)
env.clear_cache()
```

## Best Practices

### Good Cache Keys

```kida
{# ✅ Includes version for invalidation #}
{% cache "post-" + post.id + "-v" + post.version %}

{# ✅ Includes user for personalization #}
{% cache "dashboard-" + user.id %}

{# ✅ Includes locale for i18n #}
{% cache "nav-" + locale %}
```

### Avoid Overcaching

```kida
{# ❌ Too broad - caches everything #}
{% cache "page" %}
    {{ page.content }}
{% end %}

{# ✅ Scoped to specific content #}
{% cache "page-content-" + page.id + "-" + page.updated %}
    {{ page.content }}
{% end %}
```

### Cache Heavy Operations

Good candidates for caching:

- Complex database queries
- Markdown/RST rendering
- External API calls
- Expensive computations

```kida
{% cache "recent-posts" %}
    {% for post in get_recent_posts(limit=10) %}
        {{ post.title }}
    {% end %}
{% end %}
```

## Nested Caches

Caches can be nested:

```kida
{% cache "sidebar" %}
    <aside>
        {% cache "popular-tags" %}
            {{ render_tag_cloud() }}
        {% end %}
        
        {% cache "recent-posts" %}
            {{ render_recent_posts() }}
        {% end %}
    </aside>
{% end %}
```

## Cache Bypass

For debugging, you can temporarily disable caching:

```python
# Development: smaller cache, shorter TTL
env = Environment(
    fragment_cache_size=10,
    fragment_ttl=1.0,  # 1 second
)
```

## See Also

- [[docs/about/performance|Performance]] — Performance optimization
- [[docs/reference/configuration|Configuration]] — Environment options
- [[docs/usage/rendering-contexts|Rendering Contexts]] — Context passing

