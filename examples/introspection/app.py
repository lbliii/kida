"""Template introspection -- static analysis API.

Demonstrates kida's analysis API: required_context(), block_metadata(),
validate_context(), depends_on(), and template_metadata(). These enable
pre-render validation, dependency tracking, and cacheability checks
without executing the template.

Run:
    python app.py
"""

from pathlib import Path

from kida import Environment, FileSystemLoader

templates_dir = Path(__file__).parent / "templates"
env = Environment(loader=FileSystemLoader(str(templates_dir)))

template = env.get_template("page.html")

# What context variables does this template need?
required = template.required_context()

# What does each block depend on?
block_meta = template.block_metadata()

# Full template metadata (extends, blocks, top-level deps)
meta = template.template_metadata()

# Validate a context dict before rendering -- catches missing vars early
missing_vars = template.validate_context({"page": {"title": "Test"}})

# Validate with a complete context
complete_context = {
    "page": {"title": "Hello", "author": "Alice", "body": "...", "tags": []},
    "site_name": "My Site",
    "copyright": "(c) 2026",
}
no_missing = template.validate_context(complete_context)

# All dependency paths (dotted names like "page.title")
deps = template.depends_on()

# Build output for testing
lines = [
    f"Required context: {sorted(required)}",
    f"Blocks: {sorted(block_meta.keys())}",
    f"Extends: {meta.extends if meta else None}",
    f"Dependencies: {sorted(deps)}",
    f"Missing (partial): {missing_vars}",
    f"Missing (complete): {no_missing}",
]
output = "\n".join(lines)


def main() -> None:
    print("=== Template Introspection ===\n")
    for line in lines:
        print(f"  {line}")

    if meta:
        print(f"\n  All dependencies: {sorted(meta.all_dependencies())}")

    print(f"\n  Cacheable (title): {template.is_cacheable('title')}")
    print(f"  Cacheable (all):   {template.is_cacheable()}")


if __name__ == "__main__":
    main()
