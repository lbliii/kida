"""Modern syntax -- features with no Jinja2 equivalent.

Demonstrates pattern matching ({% match %}), pipeline operator (|>),
null coalescing (??), and optional chaining (?.).

Run:
    python app.py
"""

from pathlib import Path

from kida import Environment, FileSystemLoader

templates_dir = Path(__file__).parent / "templates"
env = Environment(loader=FileSystemLoader(str(templates_dir)))

template = env.get_template("profile.html")

# Render with a complete user
complete_output = template.render(
    user={"name": "Alice", "role": "admin", "profile": {"avatar": "alice.png"}},
    status="active",
)

# Render with a minimal user (missing optional fields)
minimal_output = template.render(
    user={"name": "Bob", "role": "viewer", "profile": None},
    status="pending",
)

# Render with unknown status
unknown_output = template.render(
    user={"name": "Charlie", "role": "editor", "profile": {"avatar": "charlie.png"}},
    status="archived",
)


def main() -> None:
    print("=== Complete user (admin, active) ===")
    print(complete_output)
    print("\n=== Minimal user (viewer, pending) ===")
    print(minimal_output)
    print("\n=== Unknown status (editor, archived) ===")
    print(unknown_output)


if __name__ == "__main__":
    main()
