---
title: Filters Reference
description: All built-in filters with examples
draft: false
weight: 20
lang: en
type: doc
tags:
- reference
- filters
keywords:
- filters
- reference
icon: filter
---

# Filters Reference

Complete reference for all built-in filters.

## String Filters

### abs

Return absolute value.

```kida
{{ -5 | abs }}  → 5
```

### capitalize

Capitalize first character.

```kida
{{ "hello world" | capitalize }}  → Hello world
```

### center

Center string in given width.

```kida
{{ "hi" | center(10) }}  → "    hi    "
```

### escape / e

HTML-escape the value.

```kida
{{ "<script>" | escape }}  → &lt;script&gt;
{{ "<b>" | e }}  → &lt;b&gt;
```

### format

Format string with arguments.

```kida
{{ "Hello, {}!" | format(name) }}
{{ "{} + {} = {}" | format(1, 2, 3) }}
```

### indent

Indent text lines.

```kida
{{ text | indent(4) }}
{{ text | indent(4, first=true) }}
```

### lower

Convert to lowercase.

```kida
{{ "HELLO" | lower }}  → hello
```

### replace

Replace occurrences.

```kida
{{ "hello" | replace("l", "L") }}  → heLLo
{{ "aaa" | replace("a", "b", 2) }}  → bba
```

### safe

Mark as safe HTML (no escaping).

```kida
{{ html_content | safe }}
{{ trusted | safe(reason="sanitized") }}
```

### striptags

Remove HTML tags.

```kida
{{ "<p>Hello</p>" | striptags }}  → Hello
```

### title

Title case.

```kida
{{ "hello world" | title }}  → Hello World
```

### trim / strip

Remove whitespace.

```kida
{{ "  hello  " | trim }}  → hello
{{ "xxhelloxx" | trim("x") }}  → hello
```

### truncate

Truncate to length.

```kida
{{ text | truncate(50) }}
{{ text | truncate(50, killwords=true) }}
{{ text | truncate(50, end="[...]") }}
```

### upper

Convert to uppercase.

```kida
{{ "hello" | upper }}  → HELLO
```

### urlencode

URL-encode a string.

```kida
{{ "hello world" | urlencode }}  → hello%20world
```

### wordcount

Count words.

```kida
{{ "hello world" | wordcount }}  → 2
```

### wordwrap

Wrap text at width.

```kida
{{ long_text | wordwrap(80) }}
```

---

## Collection Filters

### batch

Group items into batches.

```kida
{% for row in items | batch(3) %}
    {% for item in row %}{{ item }}{% end %}
{% end %}
```

### first

Return first item.

```kida
{{ items | first }}
{{ [1, 2, 3] | first }}  → 1
```

### groupby

Group by attribute.

```kida
{% for group in posts | groupby("category") %}
    <h2>{{ group.grouper }}</h2>
    {% for post in group.list %}
        {{ post.title }}
    {% end %}
{% end %}
```

### join

Join with separator.

```kida
{{ items | join(", ") }}
{{ [1, 2, 3] | join("-") }}  → 1-2-3
```

### last

Return last item.

```kida
{{ items | last }}
{{ [1, 2, 3] | last }}  → 3
```

### length / count

Return item count.

```kida
{{ items | length }}
{{ "hello" | length }}  → 5
```

### list

Convert to list.

```kida
{{ range(5) | list }}  → [0, 1, 2, 3, 4]
```

### map

Extract attribute from items.

```kida
{{ users | map(attribute="name") | join(", ") }}
```

### max

Return maximum.

```kida
{{ [1, 5, 3] | max }}  → 5
{{ items | max(attribute="score") }}
```

### min

Return minimum.

```kida
{{ [1, 5, 3] | min }}  → 1
{{ items | min(attribute="price") }}
```

### reject

Reject items matching test.

```kida
{{ items | reject("none") | list }}
```

### rejectattr

Reject items where attribute matches.

```kida
{{ posts | rejectattr("is_draft") | list }}
{{ users | rejectattr("age", "lt", 18) | list }}
```

### reverse

Reverse sequence.

```kida
{{ [1, 2, 3] | reverse | list }}  → [3, 2, 1]
```

### select

Select items matching test.

```kida
{{ items | select("defined") | list }}
```

### selectattr

Select items where attribute matches.

```kida
{{ posts | selectattr("is_published") | list }}
{{ users | selectattr("role", "eq", "admin") | list }}
```

### skip

Skip first N items.

```kida
{{ items | skip(5) }}
{{ posts | skip(10) | take(10) }}
```

### slice

Slice into groups.

```kida
{% for column in items | slice(3) %}
    <div class="column">
        {% for item in column %}{{ item }}{% end %}
    </div>
{% end %}
```

### sort

Sort sequence.

```kida
{{ items | sort }}
{{ items | sort(reverse=true) }}
{{ posts | sort(attribute="date") }}
{{ pages | sort(attribute="weight,title") }}
```

### sum

Sum values.

```kida
{{ [1, 2, 3] | sum }}  → 6
{{ items | sum(attribute="price") }}
```

### take

Take first N items.

```kida
{{ items | take(5) }}
{{ posts | sort(attribute="date", reverse=true) | take(3) }}
```

### unique

Remove duplicates.

```kida
{{ items | unique }}
{{ posts | unique(attribute="category") }}
```

### compact

Remove None/falsy values.

```kida
{{ [1, None, 2, "", 3] | compact }}  → [1, 2, 3]
{{ items | compact(truthy=false) }}  {# Only remove None #}
```

---

## Number Filters

### float

Convert to float.

```kida
{{ "3.14" | float }}  → 3.14
{{ "bad" | float(default=0.0) }}  → 0.0
```

### int

Convert to integer.

```kida
{{ "42" | int }}  → 42
{{ "bad" | int(default=0) }}  → 0
```

### round

Round number.

```kida
{{ 3.7 | round }}  → 4
{{ 3.14159 | round(2) }}  → 3.14
{{ 3.5 | round(method="ceil") }}  → 4
{{ 3.5 | round(method="floor") }}  → 3
```

### filesizeformat

Format bytes as human-readable.

```kida
{{ 1024 | filesizeformat }}  → 1.0 kB
{{ 1048576 | filesizeformat(binary=true) }}  → 1.0 MiB
```

### format_number / commas

Format with thousands separator.

```kida
{{ 1234567 | format_number }}  → 1,234,567
{{ 1234.5 | format_number(2) }}  → 1,234.50
{{ 1000000 | commas }}  → 1,000,000
```

---

## Utility Filters

### attr

Get attribute from object.

```kida
{{ user | attr("name") }}
```

### default / d

Return default if undefined or None.

```kida
{{ missing | default("N/A") }}
{{ value | d("fallback") }}
{{ maybe_false | default(true, boolean=true) }}
```

### dictsort

Sort dict and return pairs.

```kida
{% for key, value in data | dictsort %}
    {{ key }}: {{ value }}
{% end %}
```

### get

Safe dictionary/object access.

```kida
{{ config | get("timeout", 30) }}
{{ data | get("items") }}  {# Avoids method name conflict #}
```

### pprint

Pretty-print value.

```kida
<pre>{{ data | pprint }}</pre>
```

### require

Require non-None value.

```kida
{{ user.id | require("User ID required") }}
```

### tojson

Convert to JSON.

```kida
<script>const data = {{ config | tojson }};</script>
{{ data | tojson(indent=2) }}
```

### xmlattr

Convert dict to XML attributes.

```kida
<div{{ attrs | xmlattr }}></div>
```

---

## Debug Filters

### debug

Print debug info to stderr.

```kida
{{ posts | debug }}
{{ posts | debug("my posts") }}
{{ items | debug(max_items=10) }}
```

---

## Randomization Filters

**Warning**: These are impure (non-deterministic).

### random

Return random item.

```kida
{{ items | random }}
```

### shuffle

Return shuffled copy.

```kida
{{ items | shuffle }}
```

## See Also

- [[docs/syntax/filters|Filter Syntax]] — Using filters
- [[docs/extending/custom-filters|Custom Filters]] — Create filters

