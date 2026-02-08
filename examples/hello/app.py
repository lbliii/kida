"""Hello World -- the simplest kida example.

Compile a template from a string and render it with context variables.
No templates directory needed.

Run:
    python app.py
"""

from kida import Environment

env = Environment()

# Compile from string
template = env.from_string("Hello, {{ name }}!")

# Render with context
output = template.render(name="World")


def main() -> None:
    print(output)
    print()

    # Multiple renders with different context
    for name in ["Kida", "Bengal", "Python"]:
        print(template.render(name=name))


if __name__ == "__main__":
    main()
