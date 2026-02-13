"""Custom filters and tests -- extending Kida with add_filter and add_test.

Demonstrates add_filter(), @env.filter() decorator, and add_test() for
building domain-specific template helpers.

Run:
    python app.py
"""

from pathlib import Path

from kida import Environment, FileSystemLoader

templates_dir = Path(__file__).parent / "templates"
env = Environment(loader=FileSystemLoader(str(templates_dir)))

# Custom filter: add_filter()
def money(amount: float, currency: str = "$") -> str:
    """Format amount as currency."""
    return f"{currency}{amount:,.2f}"


env.add_filter("money", money)


# Custom filter: @env.filter() decorator
@env.filter()
def pluralize(n: int, singular: str, plural: str) -> str:
    """Return singular or plural form based on count."""
    return singular if n == 1 else plural


# Custom test: add_test()
def is_prime(n: int) -> bool:
    """Test if integer is prime."""
    if n < 2:
        return False
    return all(n % i != 0 for i in range(2, int(n**0.5) + 1))


env.add_test("prime", is_prime)

template = env.get_template("invoice.html")

output = template.render(
    total=1234.56,
    item_count=3,
    items=[
        {"name": "Widget A", "price": 19.99, "qty": 2},
        {"name": "Widget B", "price": 5.00, "qty": 1},
    ],
)


def main() -> None:
    print(output)


if __name__ == "__main__":
    main()
