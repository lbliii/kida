---
title: Filters
description: Transform values in template expressions
draft: false
weight: 30
lang: en
type: doc
tags:
- syntax
- filters
keywords:
- filters
- transformation
- pipes
icon: filter
---

# Filters

Filters transform values in template expressions using the pipe syntax.

## Basic Usage

```kida
{{ name | upper }}
{{ title | truncate(50) }}
{{ items | join(", ") }}
```

## Chaining Filters

```kida
{{ name | lower | capitalize }}
{{ text | striptags | truncate(100) }}
```

### Pipeline Operator

Use `|>` for improved readability:

```kida
{{ title |> escape |> upper |> truncate(50) }}
```

## Common Filters

### String Filters

| Filter | Description | Example |
|--------|-------------|---------|
| `upper` | Uppercase | `{{ "hello" \| upper }}` → `HELLO` |
| `lower` | Lowercase | `{{ "HELLO" \| lower }}` → `hello` |
| `capitalize` | Capitalize first | `{{ "hello" \| capitalize }}` → `Hello` |
| `title` | Title case | `{{ "hello world" \| title }}` → `Hello World` |
| `trim` | Strip whitespace | `{{ "  hi  " \| trim }}` → `hi` |
| `truncate` | Shorten text | `{{ text \| truncate(50) }}` |
| `replace` | Replace text | `{{ s \| replace("a", "b") }}` |
| `striptags` | Remove HTML | `{{ html \| striptags }}` |

### Collection Filters

| Filter | Description | Example |
|--------|-------------|---------|
| `first` | First item | `{{ items \| first }}` |
| `last` | Last item | `{{ items \| last }}` |
| `length` | Item count | `{{ items \| length }}` |
| `sort` | Sort items | `{{ items \| sort }}` |
| `reverse` | Reverse order | `{{ items \| reverse }}` |
| `unique` | Remove duplicates | `{{ items \| unique }}` |
| `join` | Concatenate | `{{ items \| join(", ") }}` |
| `take` | First N items | `{{ items \| take(5) }}` |
| `skip` | Skip N items | `{{ items \| skip(10) }}` |

### HTML Filters

| Filter | Description | Example |
|--------|-------------|---------|
| `escape` | HTML escape | `{{ html \| escape }}` |
| `safe` | Mark as safe | `{{ trusted \| safe }}` |
| `striptags` | Remove tags | `{{ html \| striptags }}` |

### Number Filters

| Filter | Description | Example |
|--------|-------------|---------|
| `abs` | Absolute value | `{{ -5 \| abs }}` → `5` |
| `round` | Round number | `{{ 3.7 \| round }}` → `4` |
| `int` | Convert to int | `{{ "42" \| int }}` → `42` |
| `float` | Convert to float | `{{ "3.14" \| float }}` → `3.14` |

### Utility Filters

| Filter | Description | Example |
|--------|-------------|---------|
| `default` | Fallback value | `{{ x \| default("N/A") }}` |
| `tojson` | JSON encode | `{{ data \| tojson }}` |
| `pprint` | Pretty print | `{{ data \| pprint }}` |
| `debug` | Debug output | `{{ items \| debug }}` |

## Filter Arguments

Filters can accept arguments:

```kida
{{ text | truncate(50) }}
{{ text | truncate(50, killwords=true) }}
{{ text | truncate(50, end="...") }}
{{ items | sort(attribute="date", reverse=true) }}
```

## Sorting with Attributes

Sort objects by attribute:

```kida
{% for post in posts | sort(attribute="date") %}
    {{ post.title }}
{% end %}

{# Multiple attributes #}
{% for page in pages | sort(attribute="weight,title") %}
    {{ page.title }}
{% end %}

{# Reverse order #}
{% for post in posts | sort(attribute="date", reverse=true) %}
    {{ post.title }}
{% end %}
```

## Grouping

Group items by attribute:

```kida
{% for group in posts | groupby("category") %}
    <h2>{{ group.grouper }}</h2>
    {% for post in group.list %}
        {{ post.title }}
    {% end %}
{% end %}
```

## Filtering Items

```kida
{# Select items matching condition #}
{{ items | selectattr("is_active") }}
{{ items | selectattr("status", "eq", "published") }}

{# Reject items matching condition #}
{{ items | rejectattr("is_draft") }}
```

## Safe HTML

Mark content as trusted HTML:

```kida
{{ html_content | safe }}

{# With reason for code review #}
{{ cms_block | safe(reason="sanitized by bleach library") }}
```

## See Also

- [[docs/reference/filters|Filter Reference]] — Complete filter list
- [[docs/extending/custom-filters|Custom Filters]] — Create your own filters
- [[docs/syntax/variables|Variables]] — Output expressions
