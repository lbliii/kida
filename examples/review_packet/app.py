"""Review packet example.

Renders one structured review payload to either Markdown or terminal text.

Run:
    python app.py
    python app.py --mode terminal
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

here = Path(__file__).parent
repo_src = here.parents[1] / "src"
if repo_src.exists() and str(repo_src) not in sys.path:
    sys.path.insert(0, str(repo_src))

from kida import FileSystemLoader  # noqa: E402
from kida.markdown import markdown_env  # noqa: E402
from kida.terminal import terminal_env  # noqa: E402

templates_dir = here / "templates"
data_path = here / "data.json"


def load_data() -> dict[str, object]:
    return json.loads(data_path.read_text(encoding="utf-8"))


def render(mode: str = "markdown") -> str:
    if mode == "terminal":
        env = terminal_env(loader=FileSystemLoader(str(templates_dir)), terminal_color="none")
        template = env.get_template("review_packet.txt")
    else:
        env = markdown_env(loader=FileSystemLoader(str(templates_dir)))
        template = env.get_template("review_packet.md")

    return template.render(**load_data())


output = render()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("markdown", "terminal"), default="markdown")
    args = parser.parse_args(argv)
    print(render(args.mode))


if __name__ == "__main__":
    main()
