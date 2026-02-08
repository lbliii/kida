"""Fragment caching -- built-in {% cache %} directive.

Demonstrates caching expensive template fragments. The {% cache "key" %}
block computes its content once and returns the cached result on subsequent
renders (within the same Environment).

Run:
    python app.py
"""

from pathlib import Path

from kida import Environment, FileSystemLoader

templates_dir = Path(__file__).parent / "templates"
env = Environment(loader=FileSystemLoader(str(templates_dir)))

template = env.get_template("dashboard.html")

# Mutable counter to prove caching works -- the template reads compute_count
# but the cached block only evaluates it on the first render.
call_count = 0


def expensive_computation() -> str:
    """Simulate an expensive operation that should be cached."""
    global call_count  # noqa: PLW0603
    call_count += 1
    return f"Result (computed {call_count} time(s))"


# First render -- populates the cache
first_output = template.render(
    title="Dashboard",
    compute=expensive_computation,
    stats={"users": 1200, "revenue": "$45K"},
)
count_after_first = call_count

# Second render -- cache hit, expensive_computation should NOT run again
second_output = template.render(
    title="Dashboard",
    compute=expensive_computation,
    stats={"users": 9999, "revenue": "$99K"},  # different data, but cache wins
)
count_after_second = call_count


def main() -> None:
    print("=== First render ===")
    print(first_output)
    print(f"\nexpensive_computation called {count_after_first} time(s)")

    print("\n=== Second render (cached) ===")
    print(second_output)
    print(f"\nexpensive_computation called {count_after_second} time(s) total")

    if count_after_first == count_after_second:
        print("\nCache hit! The expensive block was not recomputed.")
    else:
        print("\nCache miss -- block was recomputed.")


if __name__ == "__main__":
    main()
