"""Refactor-safety demo.

Renders a passing dashboard and exposes missing-context analysis for the same
template. The sibling tests run `kida check` against the intentionally broken
templates to lock the diagnostic examples.
"""

from __future__ import annotations

import sys
from pathlib import Path

here = Path(__file__).parent
repo_src = here.parents[1] / "src"
if repo_src.exists() and str(repo_src) not in sys.path:
    sys.path.insert(0, str(repo_src))

from kida import Environment, FileSystemLoader  # noqa: E402

templates_dir = here / "templates" / "good"
env = Environment(loader=FileSystemLoader(str(templates_dir)))
template = env.get_template("pages/dashboard.html")

complete_context = {
    "page": {"title": "Ops Dashboard"},
    "owner": {"name": "Mina"},
    "stats": {
        "open_issues": 7,
        "closed_issues": 42,
        "updated_at": "2026-05-10",
    },
    "users": [
        {"name": "Ari", "role": "SRE"},
        {"name": "Bo", "role": "Developer"},
    ],
}

partial_context = {
    "page": {"title": "Ops Dashboard"},
}

output = template.render(**complete_context)
missing_context = sorted(
    name
    for name in template.validate_context(partial_context)
    if name not in {"stat_card", "user_table"}
)


def main() -> None:
    print(output)
    print("\nMissing context caught before render:")
    for name in missing_context:
        print(f"- {name}")


if __name__ == "__main__":
    main()
