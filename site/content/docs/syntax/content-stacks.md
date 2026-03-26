---
title: Content Stacks
description: Collect and render content from nested templates with push and stack tags
draft: false
weight: 65
lang: en
type: doc
tags:
  - syntax
  - stacks
  - portals
keywords:
  - push
  - stack
  - content stacks
  - portals
  - CSS aggregation
  - JS aggregation
icon: layers
---

# Content Stacks

Content stacks solve a common problem in template hierarchies: child templates and partials need to contribute CSS, JavaScript, or other content to a location they do not control (typically the `<head>` or end of `<body>` in a base layout).

With `{% push %}` and `{% stack %}`, any template can append content to a named collection, and the base template decides where that collected content is rendered.

## Basic Usage

Use `{% push "name" %}` to add content to a named stack, and `{% stack "name" %}` to render everything that was pushed:

```kida
{# base.html #}
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="/css/main.css">
    {% stack "styles" %}
</head>
<body>
    {% block content %}{% end %}

    <script src="/js/main.js"></script>
    {% stack "scripts" %}
</body>
</html>
```

```kida
{# page.html #}
{% extends "base.html" %}

{% block content %}
    <div class="widget">
        {{ widget.render() }}
    </div>

    {% push "styles" %}
        <link rel="stylesheet" href="/css/widget.css">
    {% end %}

    {% push "scripts" %}
        <script src="/js/widget.js"></script>
    {% end %}
{% end %}
```

The rendered output places widget assets exactly where the base template defined the stack output points.

## Named Stacks

Stack names are string literals. You can define as many independent stacks as you need:

```kida
{% stack "styles" %}
{% stack "scripts" %}
{% stack "meta" %}
{% stack "modals" %}
```

Each `{% push %}` targets a specific stack by name. Pushes to different stacks are independent:

```kida
{% push "meta" %}
    <meta property="og:title" content="{{ page.title }}">
{% end %}

{% push "styles" %}
    <style>.hero { background: url('{{ page.hero_image }}'); }</style>
{% end %}
```

Content is rendered in the order it was pushed. If multiple templates push to the same stack, the output follows rendering order.

## Use with Inheritance

Stacks work across template inheritance chains. Child blocks can push content that appears in the base template's stack output:

```kida
{# base.html #}
<html>
<head>
    {% stack "head" %}
</head>
<body>
    {% block body %}{% end %}
    {% stack "scripts" %}
</body>
</html>
```

```kida
{# layout.html #}
{% extends "base.html" %}

{% block body %}
    <nav>...</nav>
    <main>{% block content %}{% end %}</main>

    {% push "head" %}
        <link rel="stylesheet" href="/css/layout.css">
    {% end %}
{% end %}
```

```kida
{# article.html #}
{% extends "layout.html" %}

{% block content %}
    <article>{{ article.body }}</article>

    {% push "head" %}
        <link rel="stylesheet" href="/css/article.css">
    {% end %}

    {% push "scripts" %}
        <script src="/js/reading-time.js"></script>
    {% end %}
{% end %}
```

The final output includes both `/css/layout.css` and `/css/article.css` in the `<head>`, and `/js/reading-time.js` before `</body>`.

Stacks also work inside included templates:

```kida
{# partials/gallery.html #}
<div class="gallery">
    {% for image in images %}
        <img src="{{ image.url }}" alt="{{ image.alt }}">
    {% end %}
</div>

{% push "styles" %}
    <link rel="stylesheet" href="/css/gallery.css">
{% end %}

{% push "scripts" %}
    <script src="/js/lightbox.js"></script>
{% end %}
```

```kida
{# page.html #}
{% extends "base.html" %}

{% block content %}
    {% include "partials/gallery.html" %}
{% end %}
```

The gallery partial's CSS and JS are collected and rendered at the stack output points in `base.html`.

## Common Patterns

### CSS Collection

Aggregate page-specific stylesheets without duplicating `<link>` tags in every child template:

```kida
{# base.html #}
<head>
    <link rel="stylesheet" href="/css/reset.css">
    <link rel="stylesheet" href="/css/main.css">
    {% stack "styles" %}
</head>
```

```kida
{# dashboard.html #}
{% extends "base.html" %}

{% block content %}
    {% push "styles" %}
        <link rel="stylesheet" href="/css/charts.css">
        <link rel="stylesheet" href="/css/dashboard.css">
    {% end %}

    <div class="dashboard">
        {% include "partials/chart.html" %}
    </div>
{% end %}
```

### JS Modules

Load JavaScript at the end of the body, contributed by any template in the hierarchy:

```kida
{# base.html #}
<body>
    {% block content %}{% end %}

    <script src="/js/vendor.js"></script>
    {% stack "scripts" %}
    {% stack "inline_js" %}
</body>
```

```kida
{# form.html #}
{% extends "base.html" %}

{% block content %}
    <form id="contact">...</form>

    {% push "scripts" %}
        <script src="/js/validation.js"></script>
    {% end %}

    {% push "inline_js" %}
        <script>
            document.getElementById('contact')
                .addEventListener('submit', validateForm);
        </script>
    {% end %}
{% end %}
```

### Meta Tags

Build up `<meta>` tags from child templates:

```kida
{# base.html #}
<head>
    <meta charset="utf-8">
    {% stack "meta" %}
    <title>{{ page.title }} - My Site</title>
</head>
```

```kida
{# blog-post.html #}
{% extends "base.html" %}

{% block content %}
    {% push "meta" %}
        <meta name="description" content="{{ post.summary }}">
        <meta property="og:title" content="{{ post.title }}">
        <meta property="og:image" content="{{ post.image }}">
    {% end %}

    <article>{{ post.body }}</article>
{% end %}
```

## See Also

- [[docs/syntax/inheritance|Inheritance]] -- Template inheritance with extends and blocks
- [[docs/syntax/includes|Includes]] -- Include partial templates
- [[docs/advanced/compiler|Compiler]] -- How push/stack compiles to Python
