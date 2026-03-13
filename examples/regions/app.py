"""Regions — parameterized blocks for render_block() and {{ name(args) }}.

Demonstrates:
- Regions as blocks and callables
- Simple defaults (current_page=page)
- Complex defaults (meta=page.metadata, count=items | length, title=page?.title ?? "Default")
- Outer context access
- template_metadata().regions() and depends_on

Run:
    python app.py
"""

from pathlib import Path

from kida import Environment, FileSystemLoader

templates_dir = Path(__file__).parent / "templates"
env = Environment(loader=FileSystemLoader(str(templates_dir)))

template = env.get_template("page.html")

# Page object with metadata
page_cls = type("Page", (), {"title": "Products", "metadata": type("M", (), {})()})
page = page_cls()

context = {
    "page": page,
    "items": ["a", "b", "c"],
}

# Full render
full_output = template.render(**context)

# Partial renders via render_block
sidebar_output = template.render_block("sidebar", section="API", **context)
stats_output = template.render_block("stats", **context)
header_output = template.render_block("header", **context)

# Metadata
meta = template.template_metadata()
regions = meta.regions()


def main() -> None:
    print("=== Full Page ===")
    print(full_output)
    print("\n=== Sidebar Block (render_block) ===")
    print(sidebar_output)
    print("\n=== Stats Block (render_block) ===")
    print(stats_output)
    print("\n=== Header Block (render_block) ===")
    print(header_output)
    print("\n=== Regions (metadata) ===")
    for name in regions:
        block = meta.get_block(name)
        deps = block.depends_on if block else set()
        print(f"  {name}: depends_on={sorted(deps)}")


if __name__ == "__main__":
    main()
