"""Render the app-owned local component example."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kida import Environment, FileSystemLoader, PrefixLoader

ROOT = Path(__file__).parent
TEMPLATES_DIR = ROOT / "templates"
STYLES_DIR = ROOT / "static"

env = Environment(
    loader=PrefixLoader({"app": FileSystemLoader(TEMPLATES_DIR)}),
    bytecode_cache=False,
)
template = env.get_template("app/pages/search.html")

RESULTS = [
    {
        "title": "Component authoring contract",
        "summary": "Choose boundaries with meaningful props, slots, or policy.",
        "url": "/docs/usage/components/",
    },
    {
        "title": "Framework integration",
        "summary": "Keep loader roots and response roles in the adapter.",
        "url": "/docs/usage/framework-integration/",
    },
]


def render_page(*, query: str, results: list[dict[str, Any]]) -> str:
    """Render one server-owned search state without client-side UI state."""
    return template.render(query=query, results=results)


output = render_page(query="components", results=RESULTS)


def main() -> None:
    """Print the complete example page."""
    print(output)


if __name__ == "__main__":
    main()
