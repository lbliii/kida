---
title: Inheritance
description: Template inheritance with extends and blocks
draft: false
weight: 50
lang: en
type: doc
tags:
- syntax
- inheritance
keywords:
- extends
- block
- inheritance
icon: layers
---

# Inheritance

Template inheritance lets you build a base template with common structure and override specific sections in child templates.

> **Note:** Unlike Jinja2, Kida does not support `super()`. Child blocks fully replace parent content. For "add-to" patterns, define explicit extension blocks in your base template (e.g., `{% block extra_head %}{% end %}`).

## Base Template

Create a base template with blocks that can be overridden:

```kida
{# base.html #}
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}My Site{% end %}</title>
    {% block head %}{% end %}
</head>
<body>
    <header>
        {% block header %}
            <h1>My Site</h1>
            <nav>{% block nav %}{% end %}</nav>
        {% end %}
    </header>

    <main>
        {% block content %}{% end %}
    </main>

    <footer>
        {% block footer %}
            <p>&copy; 2024</p>
        {% end %}
    </footer>
</body>
</html>
```

## Child Template

Extend the base and override blocks:

```kida
{# page.html #}
{% extends "base.html" %}

{% block title %}About - My Site{% end %}

{% block content %}
    <h2>About Us</h2>
    <p>Welcome to our site!</p>
{% end %}
```

Result: The child template inherits all of `base.html`, with the `title` and `content` blocks replaced.

## Real-World Examples

### Documentation Site

A three-column documentation layout extending a base template:

```kida
{# layouts/base.html #}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{% block title %}Docs{% end %}</title>
    <link rel="stylesheet" href="/css/main.css">
    {% block extra_head %}{% end %}
</head>
<body>
    <header>{% include "partials/nav.html" %}</header>
    <main>{% block content %}{% end %}</main>
    <footer>{% include "partials/footer.html" %}</footer>
    {% block extra_scripts %}{% end %}
</body>
</html>
```

```kida
{# layouts/docs.html #}
{% extends "layouts/base.html" %}

{% block content %}
<div class="docs-layout">
    <nav class="docs-sidebar">
        {% block sidebar %}
            {% include "partials/docs-nav.html" %}
        {% end %}
    </nav>
    <article class="docs-content">
        <h1>{% block page_title %}{% end %}</h1>
        {% block article %}{% end %}
    </article>
    <aside class="docs-toc">
        {% block toc %}{% end %}
    </aside>
</div>
{% end %}
```

```kida
{# pages/getting-started.html #}
{% extends "layouts/docs.html" %}

{% block title %}Getting Started - MyProject{% end %}
{% block page_title %}Getting Started{% end %}

{% block article %}
<p>Welcome to the quick start guide.</p>
{{ content }}
{% end %}

{% block toc %}
<nav class="toc">
    <h3>On this page</h3>
    {{ toc_html }}
</nav>
{% end %}
```

### Extension Blocks Pattern

Since Kida doesn't support `super()`, use explicit extension blocks to add content without replacing the parent:

```kida
{# base.html #}
<head>
    <link rel="stylesheet" href="/css/base.css">
    <link rel="stylesheet" href="/css/theme.css">
    {% block extra_head %}{% end %}  {# Extension point #}
</head>
<body>
    {% block content %}{% end %}
    
    <script src="/js/main.js"></script>
    {% block extra_scripts %}{% end %}  {# Extension point #}
</body>
```

```kida
{# blog/post.html #}
{% extends "base.html" %}

{% block extra_head %}
    {# Adds to head without replacing base styles #}
    <link rel="stylesheet" href="/css/syntax-highlight.css">
    <meta property="og:title" content="{{ post.title }}">
{% end %}

{% block content %}
<article class="blog-post">
    <h1>{{ post.title }}</h1>
    <time>{{ post.date | dateformat }}</time>
    {{ post.content }}
</article>
{% end %}

{% block extra_scripts %}
    {# Adds to scripts without replacing main.js #}
    <script src="/js/syntax-highlight.js"></script>
{% end %}
```

### Blog with Author Layout

Multi-level inheritance for a blog:

```kida
{# layouts/base.html #}
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}Blog{% end %}</title>
</head>
<body>
    {% block body %}{% end %}
</body>
</html>
```

```kida
{# layouts/blog.html #}
{% extends "layouts/base.html" %}

{% block body %}
<div class="blog-container">
    <aside class="blog-sidebar">
        {% block sidebar %}
            {% include "partials/recent-posts.html" %}
        {% end %}
    </aside>
    <main class="blog-main">
        {% block main %}{% end %}
    </main>
</div>
{% end %}
```

```kida
{# blog/post.html #}
{% extends "layouts/blog.html" %}

{% block title %}{{ post.title }} - Blog{% end %}

{% block main %}
<article>
    <header>
        <h1>{{ post.title }}</h1>
        <p class="byline">
            By <a href="{{ post.author.url }}">{{ post.author.name }}</a>
            on {{ post.date | dateformat('%B %d, %Y') }}
        </p>
    </header>
    <div class="post-content">
        {{ post.content }}
    </div>
    <footer>
        {% for tag in post.tags %}
            <a href="/tags/{{ tag }}/" class="tag">{{ tag }}</a>
        {% end %}
    </footer>
</article>
{% end %}
```

## Conditional Blocks

Blocks can include an `if` clause to conditionally render their content. If the condition is falsy, the block produces no output.

```kida
{% block sidebar if show_sidebar %}
    <aside>
        {% include "partials/sidebar.html" %}
    </aside>
{% end %}
```

This is equivalent to wrapping the block body in `{% if %}`, but reads more cleanly and keeps the condition visible at the block declaration.

### Dynamic Conditions

The condition can be any expression:

```kida
{% block hero if page.show_hero %}
    <section class="hero">
        <h1>{{ page.title }}</h1>
    </section>
{% end %}

{% block debug_panel if debug_mode %}
    <pre>{{ context | tojson(indent=2) }}</pre>
{% end %}
```

### With Inheritance

Conditional blocks work with template inheritance. A child template can override a conditional block, and the condition is evaluated in the child's context:

```kida
{# base.html #}
{% block analytics if not debug %}
    <script src="/analytics.js"></script>
{% end %}
```

```kida
{# page.html #}
{% extends "base.html" %}

{% block analytics if enable_tracking %}
    <script src="/custom-analytics.js"></script>
{% end %}
```

### Falsy Values

The following values cause the block to be skipped: `false`, `none`, `0`, `""` (empty string), `[]` (empty list).

---

## Block Scoping

Blocks can be nested:

```kida
{# base.html #}
{% block sidebar %}
    <aside>
        {% block sidebar_content %}
            Default sidebar
        {% end %}
    </aside>
{% end %}
```

```kida
{# child.html #}
{% extends "base.html" %}

{% block sidebar_content %}
    Custom sidebar content
{% end %}
```

## Multiple Levels

Inheritance can be multi-level. Each child completely replaces the parent's block:

```kida
{# base.html #}
{% block content %}Base{% end %}
```

```kida
{# layout.html #}
{% extends "base.html" %}
{% block content %}
    <div class="layout">Layout content</div>
{% end %}
```

```kida
{# page.html #}
{% extends "layout.html" %}
{% block content %}
    <div class="layout">
        <p>Page content</p>
    </div>
{% end %}
```

## Dynamic Extends

The parent template can be a variable:

```kida
{% extends parent_template %}

{% block content %}
    Dynamic parent!
{% end %}
```

```python
template.render(parent_template="layouts/wide.html")
```

## Block Inside Loops

Blocks cannot be defined inside loops or conditionals. This is intentional—blocks are resolved at compile time.

```kida
{# ❌ Invalid #}
{% for item in items %}
    {% block item %}{{ item }}{% end %}
{% end %}

{# ✅ Valid: Use a function instead #}
{% def render_item(item) %}
    <div>{{ item }}</div>
{% end %}

{% for item in items %}
    {{ render_item(item) }}
{% end %}
```

## Best Practices

### Descriptive Block Names

```kida
{# Good #}
{% block page_title %}{% end %}
{% block sidebar_navigation %}{% end %}
{% block footer_copyright %}{% end %}

{# Avoid #}
{% block b1 %}{% end %}
{% block content2 %}{% end %}
```

### Default Content

Provide sensible defaults in base templates:

```kida
{% block meta_description %}
    <meta name="description" content="Default site description">
{% end %}
```

### Template Hierarchy

```
base.html           ← Site-wide structure
├── docs.html       ← Documentation layout
│   └── tutorial.html  ← Tutorial-specific
├── blog.html       ← Blog layout
│   └── post.html   ← Single post
└── home.html       ← Homepage
```

## See Also

- [[docs/syntax/includes|Includes]] — Include partials
- [[docs/syntax/functions|Functions]] — Reusable template functions
- [[docs/usage/loading-templates|Loading Templates]] — Template loaders
