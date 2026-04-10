---
title: Error Boundaries
description: Catch rendering errors in templates with try/fallback blocks
draft: false
weight: 41
lang: en
type: doc
tags:
  - usage
  - error-handling
  - resilience
keywords:
  - error boundaries
  - try
  - fallback
  - graceful degradation
  - resilience
icon: shield
---

# Error Boundaries

`{% try %}...{% fallback %}...{% end %}` catches rendering errors inside a
template and renders fallback content instead of crashing the page.

## Basic usage

```jinja2
{% try %}
  {{ user.profile.avatar_url }}
{% fallback %}
  <img src="/default-avatar.png">
{% end %}
```

If `user.profile.avatar_url` raises an `UndefinedError`, the fallback renders.
If no error occurs, the body renders normally and the fallback is ignored.

## What gets caught

Error boundaries catch these exception types:

| Exception | Example |
|-----------|---------|
| `UndefinedError` | `{{ missing_var }}` |
| `TemplateRuntimeError` | Errors from includes, macros, filters |
| `TypeError` | `{{ 42 \| join(",") }}` (filter type mismatch) |
| `ValueError` | Value conversion failures |

Syntax errors are **not caught** -- they are raised at parse time, before
rendering begins.

## Partial output is discarded

When the body errors partway through, any output already produced by that body
is thrown away. Only the fallback renders:

```jinja2
{% try %}
  <p>Hello, {{ user.name }}!</p>
  <p>Your role: {{ user.role }}</p>    {# errors here #}
{% fallback %}
  <p>Could not load user info.</p>
{% end %}
```

Even though `Hello, Alice!` was rendered before the error, the entire body is
discarded and only `Could not load user info.` appears.

## Accessing the error

Add a name after `{% fallback %}` to bind the caught error as a dict:

```jinja2
{% try %}
  {{ widget.render() }}
{% fallback err %}
  <div class="error">
    <p>Widget failed: {{ err.message }}</p>
    <small>{{ err.type }}</small>
  </div>
{% end %}
```

The error dict has these fields:

| Field | Type | Description |
|-------|------|-------------|
| `message` | `str` | The exception message |
| `type` | `str` | Exception class name (e.g. `"UndefinedError"`) |
| `template` | `str \| None` | Template name where the error occurred |
| `line` | `int \| None` | Line number of the error |

## Nesting

Error boundaries nest. The innermost `{% try %}` catches first:

```jinja2
{% try %}
  {% try %}
    {{ risky_operation() }}
  {% fallback %}
    <p>Inner fallback</p>
  {% end %}
{% fallback %}
  <p>Outer fallback (only if inner also fails)</p>
{% end %}
```

If the inner fallback itself errors, the outer boundary catches it.

## Inside loops

Use `{% try %}` inside a loop to handle errors per-iteration without breaking
the whole list:

```jinja2
<ul>
{% for item in items %}
  <li>
    {% try %}
      {{ render_item(item) }}
    {% fallback %}
      <span class="error">Failed to render item</span>
    {% end %}
  </li>
{% end %}
</ul>
```

One bad item doesn't take down the rest of the list.

## With components

Error boundaries catch errors from any template code -- includes, macros,
and component calls:

```jinja2
{# Catch errors from an included partial #}
{% try %}
  {% include "widgets/dashboard.html" %}
{% fallback %}
  <p>Dashboard unavailable.</p>
{% end %}

{# Catch errors from a component #}
{% try %}
  {{ chart(data=analytics_data) }}
{% fallback err %}
  <p>Chart error: {{ err.message }}</p>
{% end %}
```

## Streaming

Error boundaries work correctly in streaming mode (`render_stream()`). The
try body is buffered internally -- chunks are only yielded to the stream after
the body completes without error. If the body errors, the buffer is discarded
and the fallback streams normally.

```python
for chunk in template.render_stream():
    response.write(chunk)
```

No partial try-body output leaks into the stream.

## Patterns

### Graceful degradation

Wrap optional sections so the page still renders when a data source fails:

```jinja2
<main>
  <h1>{{ page.title }}</h1>
  {{ page.content }}

  {% try %}
    {% include "partials/recommendations.html" %}
  {% fallback %}
    {# Recommendations unavailable -- page still works #}
  {% end %}
</main>
```

### Development vs. production

Show error details in development, hide them in production:

```jinja2
{% try %}
  {{ complex_widget() }}
{% fallback err %}
  {% if debug %}
    <pre>{{ err.type }}: {{ err.message }}</pre>
  {% else %}
    <p>Something went wrong.</p>
  {% end %}
{% end %}
```

### Per-item resilience in data-driven pages

```jinja2
{% for post in posts %}
  {% try %}
    <article>
      <h2>{{ post.title }}</h2>
      <p>{{ post.excerpt }}</p>
      <span>By {{ post.author.name }}</span>
    </article>
  {% fallback %}
    <article class="error">
      <h2>Post unavailable</h2>
    </article>
  {% end %}
{% end %}
```
