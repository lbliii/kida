"""Provide / Consume -- implicit state passing across component boundaries.

{% provide key = value %} pushes state that any descendant can read with
consume("key").  No prop drilling required -- children, slots, includes,
and imported macros all see the provided value.

Run:
    python app.py
"""

from pathlib import Path

from kida import Environment, FileSystemLoader

templates_dir = Path(__file__).parent / "templates"
env = Environment(loader=FileSystemLoader(str(templates_dir)))

template = env.get_template("page.html")

output = template.render(
    title="Provide / Consume",
    members=[
        {"name": "Alice", "role": "Engineer", "status": "Active"},
        {"name": "Bob", "role": "Designer", "status": "Away"},
        {"name": "Carol", "role": "PM", "status": "Active"},
    ],
)


def main() -> None:
    print(output)


if __name__ == "__main__":
    main()
