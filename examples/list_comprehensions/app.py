"""List comprehensions -- inline data transformation in templates.

Demonstrates [expr for x in iterable] and [expr for x in iterable if cond]
syntax for shaping data directly in templates.

Run:
    python app.py
"""

from kida import Environment

env = Environment()

# Basic: transform items inline
basic = env.from_string("{{ [x * 2 for x in numbers] }}")
output_basic = basic.render(numbers=[1, 2, 3, 4, 5])

# With filter: apply a filter to each element
with_filter = env.from_string(
    "{% set names = [n | title for n in raw_names] %}{% for n in names %}{{ n }} {% end %}"
)
output_filter = with_filter.render(raw_names=["alice", "bob", "charlie"])

# With condition: filter and transform in one expression
with_condition = env.from_string("{{ [item.name for item in products if item.in_stock] }}")
output_condition = with_condition.render(
    products=[
        {"name": "Widget", "in_stock": True},
        {"name": "Gadget", "in_stock": False},
        {"name": "Doohickey", "in_stock": True},
    ],
)

# Shaping data for components: build select options from a flat list
select_options = env.from_string(
    '{% set opts = [{"value": s, "label": s | capitalize} for s in styles] %}'
    "{% for opt in opts %}"
    '<option value="{{ opt.value }}">{{ opt.label }}</option>\n'
    "{% end %}"
)
output_select = select_options.render(styles=["bold", "italic", "underline"])

# Tuple unpacking: extract from pairs
unpacking = env.from_string("{{ [k for k, v in pairs if v > 10] }}")
output_unpacking = unpacking.render(pairs=[("a", 5), ("b", 15), ("c", 20)])


def main() -> None:
    print("=== Basic ===")
    print(output_basic)
    print()
    print("=== With Filter ===")
    print(output_filter)
    print()
    print("=== With Condition ===")
    print(output_condition)
    print()
    print("=== Select Options ===")
    print(output_select)
    print()
    print("=== Tuple Unpacking ===")
    print(output_unpacking)


if __name__ == "__main__":
    main()
