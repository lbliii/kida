"""DictLoader -- in-memory templates without filesystem.

Templates from a dictionary. No templates directory needed.
Use case: tests, generated templates, single-file apps.

Run:
    python app.py
"""

from kida import DictLoader, Environment

templates = {
    "base.html": """\
<!DOCTYPE html>
<html>
<head><title>{{ title }}</title></head>
<body>
    <nav>
    {% for item in nav_items %}
        <a href="{{ item.url }}">{{ item.label }}</a>
    {% end %}
    </nav>
    <main>{% block content %}{% end %}</main>
</body>
</html>
""",
    "page.html": """\
{% extends "base.html" %}
{% block content %}
    <h1>{{ heading }}</h1>
    <p>{{ message }}</p>
{% end %}
""",
}

env = Environment(loader=DictLoader(templates))
template = env.get_template("page.html")

output = template.render(
    title="DictLoader Demo",
    nav_items=[
        {"url": "/", "label": "Home"},
        {"url": "/about", "label": "About"},
    ],
    heading="In-Memory Templates",
    message="No filesystem required. Templates loaded from a dict.",
)


def main() -> None:
    print(output)


if __name__ == "__main__":
    main()
