"""Git log viewer with diff output and branch decoration."""

from kida.terminal import terminal_env
from kida.utils.terminal_escape import Styled


def format_refs(refs):
    """Format git refs with colors — pre-computed to avoid loop.last in caller blocks."""
    if not refs:
        return ""
    parts = []
    for ref in refs:
        if ref == "HEAD":
            parts.append("\033[96m\033[1mHEAD\033[0m")
        elif ref.startswith("origin/"):
            parts.append(f"\033[31m{ref}\033[0m")
        elif ref.startswith("tag:"):
            parts.append(f"\033[93m\033[1m{ref}\033[0m")
        else:
            parts.append(f"\033[32m\033[1m{ref}\033[0m")
    inner = Styled("\033[2m, \033[0m".join(parts))
    return Styled(f"\033[2m(\033[0m{inner}\033[2m)\033[0m")


def main():
    env = terminal_env(terminal_color="basic")
    env.globals["format_refs"] = format_refs

    template = env.from_string("""\
{% from "components.txt" import panel %}
{{ icons.spark | bright_cyan }} {{ "git log" | bold | bright_cyan }} {{ "--oneline --graph --decorate" | dim }}
{{ hr(60) }}

{% for commit in commits -%}

{% call panel(width=60) -%}
{{ commit.hash | yellow | bold | pad(10) }}{% if commit.refs %} {{ format_refs(commit.refs) }}{% endif %}

  {{ commit.message | bold }}

  {{ icons.bullet | dim }} {{ commit.author | cyan | pad(24) }} {{ commit.date | dim | pad(24, align="right") }}
{% if commit.files -%}
  {{ icons.bullet | dim }} {{ (commit.files | length ~ " files changed") | dim | pad(20) }} {{ commit.insertions | green | pad(12) }} {{ commit.deletions | red | pad(14, align="right") }}
{% endif -%}
{% endcall %}
{% if commit.diff %}
{{ commit.old_content | diff(commit.new_content) }}
{% endif -%}
{% if not loop.last %}  {{ icons.tri_d | dim }}
{% endif -%}
{% endfor %}

{{ hr(60) }}
{{ (commits | length ~ " commits shown") | dim }} {{ icons.ellipsis | dim }}
""")

    commits = [
        {
            "hash": "c27bbe6",
            "message": "feat: comprehensive engine improvements",
            "author": "lbliii",
            "date": "2 hours ago",
            "refs": ["HEAD", "lbliii/nairobi", "origin/main"],
            "files": ["compiler.py", "engine.py", "filters.py"],
            "insertions": "+342",
            "deletions": "-89",
            "diff": None,
            "old_content": None,
            "new_content": None,
        },
        {
            "hash": "8b57dc4",
            "message": "feat: add terminal rendering mode",
            "author": "lbliii",
            "date": "5 hours ago",
            "refs": ["tag: v0.2.8"],
            "files": ["terminal.py", "filters.py", "escape.py", "icons.py", "boxes.py"],
            "insertions": "+1,247",
            "deletions": "-12",
            "diff": True,
            "old_content": """\
class Environment:
    def __init__(self, autoescape=True):
        self.autoescape = autoescape
        self._filters = {}""",
            "new_content": """\
class Environment:
    def __init__(self, autoescape=True, terminal_color=None):
        self.autoescape = autoescape
        self.terminal_color = terminal_color
        self._filters = {}
        if autoescape == "terminal":
            self._init_terminal_mode()""",
        },
        {
            "hash": "90fc0ca",
            "message": "Bump bengal 0.2.6",
            "author": "dependabot[bot]",
            "date": "1 day ago",
            "refs": None,
            "files": ["pyproject.toml"],
            "insertions": "+1",
            "deletions": "-1",
            "diff": None,
            "old_content": None,
            "new_content": None,
        },
        {
            "hash": "5d0a5f5",
            "message": "updates",
            "author": "lbliii",
            "date": "2 days ago",
            "refs": None,
            "files": None,
            "insertions": None,
            "deletions": None,
            "diff": None,
            "old_content": None,
            "new_content": None,
        },
    ]

    print(template.render(commits=commits))


if __name__ == "__main__":
    main()
