"""HTMX-style partial rendering -- render_block() for targeted updates.

Demonstrates rendering individual blocks from a single template, the
pattern used by HTMX, Turbo, and Unpoly for partial page updates.
Full page renders the entire template; partial renders extract just
the block needed for an AJAX response.

Run:
    python app.py
"""

from pathlib import Path

from kida import Environment, FileSystemLoader

templates_dir = Path(__file__).parent / "templates"
env = Environment(loader=FileSystemLoader(str(templates_dir)))

template = env.get_template("dashboard.html")

context = {
    "title": "Dashboard",
    "active_tab": "Overview",
    "tabs": ["Overview", "Analytics", "Settings"],
    "items": [
        {"name": "Revenue", "value": "$1.2M"},
        {"name": "Users", "value": "45,000"},
        {"name": "Orders", "value": "12,350"},
    ],
    "stats": [
        {"label": "Uptime", "value": "99.9%"},
        {"label": "Latency", "value": "42ms"},
    ],
}

# Full page render
full_output = template.render(**context)

# Partial renders (HTMX-style block extraction)
nav_output = template.render_block("nav", **context)
content_output = template.render_block("content", **context)
sidebar_output = template.render_block("sidebar", **context)

output = full_output


def main() -> None:
    print("=== Full Page ===")
    print(full_output)
    print("\n=== Nav Block ===")
    print(nav_output)
    print("\n=== Content Block ===")
    print(content_output)
    print("\n=== Sidebar Block ===")
    print(sidebar_output)


if __name__ == "__main__":
    main()
