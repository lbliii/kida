---
title: Django Integration
description: Use Kida as a Django template backend with kida.contrib.django
draft: false
weight: 25
lang: en
type: doc
tags:
  - tutorials
  - django
  - framework
keywords:
  - Django
  - template backend
  - contrib
  - integration
icon: globe
---

# Django Integration

Use Kida as a drop-in Django template backend with `kida.contrib.django`. The integration provides `KidaTemplates` -- a backend class that plugs into Django's `TEMPLATES` setting and works with `django.shortcuts.render`, template loaders, and the Django debug toolbar.

## Installation

```bash
pip install django kida
```

## Django Settings

Add the Kida backend to your `TEMPLATES` list in `settings.py`:

```python
# settings.py
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

TEMPLATES = [
    {
        "BACKEND": "kida.contrib.django.KidaTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "OPTIONS": {
            "autoescape": True,
            "extensions": [],
        },
    },
]
```

| Key | Description |
|-----|-------------|
| `BACKEND` | Must be `"kida.contrib.django.KidaTemplates"` |
| `DIRS` | List of directories to search for templates |
| `OPTIONS.autoescape` | Enable HTML autoescaping (default: `True`) |
| `OPTIONS.extensions` | List of Kida extensions to load |

## Usage in Views

Once configured, use Django's standard rendering functions. The `request` object is automatically added to the template context:

```python
from django.shortcuts import render

def home(request):
    return render(request, "home.html", {"title": "Home"})

def user_profile(request, username):
    user = get_user(username)
    return render(request, "profile.html", {"user": user})
```

You can also load templates directly through the backend:

```python
from django.template import loader

def home(request):
    template = loader.get_template("home.html")
    html = template.render({"title": "Home"}, request)
    return HttpResponse(html)
```

Or create templates from strings:

```python
from django.template import engines

kida = engines["kida"]  # Name matches BACKEND path
template = kida.from_string("Hello {{ name }}!")
html = template.render({"name": "World"})
```

## Template Syntax Differences

If you're coming from Django's built-in template language, note these Kida syntax differences:

| Feature | Django | Kida |
|---------|--------|------|
| Block end tags | `{% endblock %}` | `{% end %}` |
| For loop end | `{% endfor %}` | `{% end %}` |
| If end | `{% endif %}` | `{% end %}` |
| Comments | `{# comment #}` | `{# comment #}` |
| Variable output | `{{ var }}` | `{{ var }}` |
| Filters | `{{ var\|filter }}` | `{{ var \| filter }}` |
| Extends | `{% extends "base.html" %}` | `{% extends "base.html" %}` |

### Template Example

**templates/base.html:**

```kida
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}My Site{% end %}</title>
</head>
<body>
    <nav>{% block nav %}{% end %}</nav>
    <main>{% block content %}{% end %}</main>
</body>
</html>
```

**templates/home.html:**

```kida
{% extends "base.html" %}

{% block title %}{{ title }}{% end %}

{% block content %}
    <h1>{{ title }}</h1>
    <p>Welcome to the site!</p>
{% end %}
```

## Custom Filters and Globals

Access the Kida `Environment` through the backend to register custom filters and globals:

```python
# templatetags.py (or in your AppConfig.ready())
from django.template import engines

def setup_kida():
    backend = engines["kida"]
    env = backend.env

    # Register a custom filter
    @env.filter()
    def format_datetime(value, fmt="%Y-%m-%d"):
        return value.strftime(fmt)

    # Register a global
    env.add_global("SITE_NAME", "My Django Site")
```

Use in templates:

```kida
<p>Published: {{ post.date | format_datetime("%B %d, %Y") }}</p>
<footer>{{ SITE_NAME }}</footer>
```

## Complete Example

```python
# settings.py
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

TEMPLATES = [
    {
        "BACKEND": "kida.contrib.django.KidaTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "OPTIONS": {
            "autoescape": True,
        },
    },
]
```

```python
# views.py
from django.shortcuts import render

def home(request):
    return render(request, "home.html", {
        "title": "Home",
        "items": ["Alpha", "Bravo", "Charlie"],
    })
```

```kida
{# templates/home.html #}
{% extends "base.html" %}

{% block title %}{{ title }}{% end %}

{% block content %}
    <h1>{{ title }}</h1>
    <ul>
    {% for item in items %}
        <li>{{ item }}</li>
    {% end %}
    </ul>
{% end %}
```

## See Also

- [[docs/tutorials/flask-integration|Flask Integration]] -- Flask setup guide
- [[docs/tutorials/starlette-integration|Starlette & FastAPI Integration]] -- Async framework setup
- [[docs/advanced/csp|Content Security Policy]] -- CSP nonce injection
- [[docs/usage/escaping|Escaping]] -- HTML security and autoescaping
