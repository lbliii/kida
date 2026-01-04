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
- super
icon: layers
---

# Inheritance

Template inheritance lets you build a base template with common structure and override specific sections in child templates.

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

## super()

Include the parent block's content:

```kida
{# base.html #}
{% block head %}
    <link rel="stylesheet" href="/css/base.css">
{% end %}
```

```kida
{# child.html #}
{% extends "base.html" %}

{% block head %}
    {{ super() }}
    <link rel="stylesheet" href="/css/page.css">
{% end %}
```

Output:

```html
<link rel="stylesheet" href="/css/base.css">
<link rel="stylesheet" href="/css/page.css">
```

## Multiple Levels

Inheritance can be multi-level:

```kida
{# base.html #}
{% block content %}Base{% end %}
```

```kida
{# layout.html #}
{% extends "base.html" %}
{% block content %}
    <div class="layout">{{ super() }}</div>
{% end %}
```

```kida
{# page.html #}
{% extends "layout.html" %}
{% block content %}
    {{ super() }}
    <p>Page content</p>
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

