"""Design system -- component library with def/slot/call composition.

Demonstrates kida's {% def %}, {% slot %}, and {% call %} for building
reusable UI components with parameter defaults and content projection.
Components compose naturally: buttons inside cards, cards inside pages.

Run:
    python app.py
"""

from pathlib import Path

from kida import Environment, FileSystemLoader

templates_dir = Path(__file__).parent / "templates"
env = Environment(loader=FileSystemLoader(str(templates_dir)))

template = env.get_template("page.html")

context = {
    "title": "User Dashboard",
    "user": {
        "name": "Alice",
        "email": "alice@example.com",
    },
}

output = template.render(**context)


def main() -> None:
    print(output)


if __name__ == "__main__":
    main()
