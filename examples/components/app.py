"""Reusable components -- def/call/slot pattern.

Kida's component model: define a component with {% def %} and {% slot %},
then use it with {% call %}...{% end %} to inject content into the slot.

Run:
    python app.py
"""

from pathlib import Path

from kida import Environment, FileSystemLoader

templates_dir = Path(__file__).parent / "templates"
env = Environment(loader=FileSystemLoader(str(templates_dir)))

template = env.get_template("page.html")

output = template.render(
    title="Component Demo",
    features=[
        {"name": "AST-native", "desc": "Compiles to Python AST directly"},
        {"name": "Free-threading", "desc": "Safe for concurrent execution"},
        {"name": "Zero deps", "desc": "Pure Python, no dependencies"},
    ],
    warning_message="This is an alpha release. API may change.",
)


def main() -> None:
    print(output)


if __name__ == "__main__":
    main()
