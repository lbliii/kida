---
title: Flask Integration
description: Use Kida templates with Flask web framework
draft: false
weight: 20
lang: en
type: doc
tags:
- tutorial
- flask
- web
keywords:
- flask
- fastapi
- web framework
- integration
icon: globe
---

# Flask Integration

Integrate Kida templates into your Flask application.

## Prerequisites

- Python 3.14+
- Flask installed
- Basic Flask knowledge

## Step 1: Install Dependencies

```bash
pip install flask kida-templates
```

## Step 2: Configure Kida with Flask

Register Kida on a Flask app. This keeps Flask's Jinja environment intact and
adds a separate Kida environment at `app.extensions["kida"]`:

```python
from flask import Flask
from kida.contrib.flask import init_kida, render_template

app = Flask(__name__)
kida_env = init_kida(app)
```

`init_kida()` uses `app.template_folder` by default. Pass
`template_folder="other-templates"` to override it, or pass Kida
`Environment` keyword arguments such as `cache_size=400`.

## Step 3: Use the Render Helper

Import the adapter's `render_template()` inside routes. It reads the Kida
environment from Flask's current app and returns the rendered HTML string:

```python
from kida.contrib.flask import render_template
```

## Step 4: Use in Routes

```python
@app.route("/")
def home():
    return render_template("home.html", title="Welcome")

@app.route("/users/<name>")
def user_profile(name):
    user = get_user(name)
    return render_template("profile.html", user=user)
```

## Step 5: Create Templates

**templates/base.html:**

```kida
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}My App{% end %}</title>
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

## Complete Example

```python
from flask import Flask
from kida.contrib.flask import init_kida, render_template

app = Flask(__name__)

kida_env = init_kida(
    app,
    cache_size=100,
    auto_reload=app.debug,  # Only reload in debug mode
)

@app.route("/")
def home():
    return render_template("home.html", title="Home")

@app.route("/about")
def about():
    return render_template("about.html", title="About")

if __name__ == "__main__":
    app.run(debug=True)
```

## Custom Filters for Flask

```python
from datetime import datetime
from flask import url_for as flask_url_for

# Add Flask's url_for
kida_env.add_global("url_for", flask_url_for)

# Add custom filters
@kida_env.filter()
def format_datetime(value, format="%Y-%m-%d"):
    if isinstance(value, datetime):
        return value.strftime(format)
    return value

@kida_env.filter()
def pluralize(count, singular, plural=None):
    if plural is None:
        plural = singular + "s"
    return singular if count == 1 else plural
```

Use in templates:

```kida
{{ post.date | format_datetime("%B %d, %Y") }}
{{ count }} {{ count | pluralize("item") }}
```

## Error Handling

```python
from kida import TemplateError

@app.errorhandler(TemplateError)
def handle_template_error(error):
    app.logger.error(f"Template error: {error}")
    return render_template("error.html", error=str(error)), 500
```

## Production Configuration

```python
# Production settings
kida_env = Environment(
    loader=FileSystemLoader("templates/"),
    autoescape=True,
    auto_reload=False,      # Don't check for changes
    cache_size=400,         # Larger cache
)

# Clear cache on deploy
@app.cli.command()
def clear_cache():
    """Clear template cache."""
    kida_env.clear_cache()
    print("Template cache cleared.")
```

## FastAPI Integration

Kida works similarly with FastAPI:

```python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from kida import Environment, FileSystemLoader

app = FastAPI()
kida_env = Environment(loader=FileSystemLoader("templates/"))

@app.get("/", response_class=HTMLResponse)
def home():
    template = kida_env.get_template("home.html")
    return template.render(title="FastAPI + Kida")
```

## Next Steps

- [[docs/extending/custom-filters|Custom Filters]] — Build domain-specific filters
- [[docs/usage/escaping|Escaping]] — HTML security
- [[docs/about/performance|Performance]] — Production optimization
