"""Loop context -- loop.first, loop.last, loop.index, loop.length.

Demonstrates the loop variable in {% for %} blocks for styling
first/last items, row numbers, and progress indicators.

Run:
    python app.py
"""

from pathlib import Path

from kida import Environment, FileSystemLoader

templates_dir = Path(__file__).parent / "templates"
env = Environment(loader=FileSystemLoader(str(templates_dir)))
template = env.get_template("table.html")

items = ["Alpha", "Beta", "Gamma", "Delta"]
output = template.render(items=items)


def main() -> None:
    print(output)


if __name__ == "__main__":
    main()
