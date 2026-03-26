"""Service status dashboard — demonstrates CLI render, color depth, and responsive layout.

This example can be run two ways:

    # Via Python:
    python examples/terminal_render/run.py

    # Via CLI (equivalent):
    kida render examples/terminal_render/template.txt \\
        --data examples/terminal_render/data.json

    # CLI with overrides:
    kida render examples/terminal_render/template.txt \\
        --data examples/terminal_render/data.json \\
        --width 60 --color basic
"""

import json
from pathlib import Path

from kida.terminal import terminal_env


def main():
    here = Path(__file__).parent
    data = json.loads((here / "data.json").read_text())

    env = terminal_env(
        loader=__import__(
            "kida.environment.loaders", fromlist=["FileSystemLoader"]
        ).FileSystemLoader(str(here)),
    )
    template = env.get_template("template.txt")
    print(template.render(**data))


if __name__ == "__main__":
    main()
