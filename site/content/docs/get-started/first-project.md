---
title: First Project
description: Build a multi-page template project with inheritance, filters, and context
draft: false
weight: 30
lang: en
type: doc
tags:
- tutorial
- quickstart
keywords:
- first project
- template inheritance
- filters
- blocks
icon: package
---

# First Project

Build a mini email template system using inheritance, filters, and context passing.

## Project Structure

```
my-templates/
├── templates/
│   ├── base.html
│   ├── welcome.html
│   └── invoice.html
└── render.py
```

## Step 1: Base Template

Create `templates/base.html` with a shared layout:

```html
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}Notification{% end %}</title>
</head>
<body>
    <header>
        <h1>{{ company }}</h1>
    </header>

    <main>
        {% block content %}{% end %}
    </main>

    <footer>
        <p>Sent by {{ company }} on {{ date }}</p>
    </footer>
</body>
</html>
```

## Step 2: Child Templates

Create `templates/welcome.html` extending the base:

```html
{% extends "base.html" %}

{% block title %}Welcome, {{ user.name }}!{% end %}

{% block content %}
<h2>Welcome aboard, {{ user.name | title }}!</h2>

<p>Here's what you can do:</p>

<ul>
    {% for feature in features %}
    <li>{{ feature }}</li>
    {% end %}
</ul>

{% if user.role == "admin" %}
<p><strong>Admin panel:</strong> {{ admin_url }}</p>
{% end %}
{% end %}
```

Create `templates/invoice.html`:

```html
{% extends "base.html" %}

{% block title %}Invoice #{{ invoice.id }}{% end %}

{% block content %}
<h2>Invoice #{{ invoice.id }}</h2>

<table>
    <thead>
        <tr><th>Item</th><th>Qty</th><th>Price</th></tr>
    </thead>
    <tbody>
        {% for item in invoice.items %}
        <tr>
            <td>{{ item.name }}</td>
            <td>{{ item.qty }}</td>
            <td>${{ item.price }}</td>
        </tr>
        {% end %}
    </tbody>
</table>

<p><strong>Total: ${{ invoice.total }}</strong></p>
{% end %}
```

## Step 3: Render Script

Create `render.py`:

```python
from kida import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("templates/"))

# Add a custom filter
env.add_filter("currency", lambda v: f"${v:,.2f}")

# Render the welcome email
welcome = env.get_template("welcome.html")
print(welcome.render(
    company="Acme Inc",
    date="2026-02-08",
    user={"name": "alice", "role": "admin"},
    features=["Dashboard", "Reports", "API Access"],
    admin_url="https://admin.example.com",
))

print("---")

# Render the invoice email
invoice_tmpl = env.get_template("invoice.html")
print(invoice_tmpl.render(
    company="Acme Inc",
    date="2026-02-08",
    invoice={
        "id": "INV-001",
        "items": [
            {"name": "Widget", "qty": 3, "price": 9.99},
            {"name": "Gadget", "qty": 1, "price": 24.99},
        ],
        "total": 54.96,
    },
))
```

## Step 4: Run It

```bash
python render.py
```

Both templates share the same base layout, but each fills in its own title and content blocks.

## Key Takeaways

| Concept | What You Learned |
|---------|-----------------|
| `{% extends %}` | Child templates inherit a base layout |
| `{% block %}...{% end %}` | Named sections that children can override |
| `{{ obj.attr }}` | Dot access works on dicts and objects |
| `{{ value \| title }}` | Filters transform output inline |
| `env.add_filter()` | Register custom filters at startup |

## Next Steps

:::{cards}
:columns: 2
:gap: medium

:::{card} Template Inheritance
:icon: layers
:link: ../syntax/inheritance
:description: Extends, blocks, super()
Deep dive into Kida's inheritance model.
:::{/card}

:::{card} Filters Reference
:icon: filter
:link: ../reference/filters
:description: 40+ built-in filters
Browse all available filters with examples.
:::{/card}

:::{/cards}
