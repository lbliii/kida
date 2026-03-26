"""Nested layout system — uses built-in components from kida.terminal.

Demonstrates the layered approach using kida's built-in component library:
  row(), cols(), rule()                — primitives
  header(), panel(), footer(), connector() — bordered panels
  banner(), two_col(), dl()            — layout helpers

Every bordered line uses ANSI-aware padding, so right edges always align.
"""

from kida.terminal import terminal_env


def main():
    env = terminal_env(terminal_color="basic")

    template = env.from_string("""\
{% from "components.txt" import header, panel, footer, connector %}
{% set w = 64 -%}

{% call header(width=w) -%}
{{ icons.gear | bright_cyan }} {{ "DEPLOY PIPELINE" | bold | bright_cyan | pad(20) }}{{ version | dim | pad(10) }}{{ target | yellow }}
{{ "Triggered by" | dim }} {{ author | bold }}{{ " " * 7 }}{{ branch | cyan }}{{ " @ " | dim }}{{ sha | yellow }}
{% endcall %}

{% for stage in stages -%}
{% if stage.status == "pass" -%}
{% let icon = icons.check | green -%}
{% elif stage.status == "running" -%}
{% let icon = icons.play | cyan -%}
{% else -%}
{% let icon = icons.circle | dim -%}
{% endif -%}

{% call panel(title=stage.name, width=w) -%}
{{ icon }} {{ stage.name | bold | pad(26) }}{{ stage.status | badge | pad(10) }}{{ stage.duration | dim | pad(14, align="right") }}
{{ hr(w - 6) }}
{% for step in stage.steps -%}
  {% if step.status == "pass" %}{{ icons.check | green }}{% elif step.status == "running" %}{{ icons.play | cyan }}{% else %}{{ icons.circle | dim }}{% endif %} {{ step.name | pad(24) }}{{ step.status | badge | pad(10) }}{{ step.duration | dim | pad(14, align="right") }}
{% endfor -%}
{% endcall %}
{% if not loop.last -%}
{{ connector() }}
{% endif -%}
{% endfor %}

{% call footer(width=w) -%}
{{ icons.zap | yellow }} {{ "SUMMARY" | bold | yellow }}{{ " " * 9 }}{{ "Duration" | kv(total_duration, width=32) }}
{{ " " * 20 }}{{ "Stages" | kv(stages | length ~ " / " ~ stages | length, width=32) }}
{{ " " * 20 }}{{ "Status" | kv(final_status, width=32) }}
{% endcall -%}
""")

    result = template.render(
        version="v3.8.0",
        target="prod-us-east-1",
        author="@lbliii",
        branch="main",
        sha="c27bbe6",
        final_status="running",
        total_duration="8m 01s",
        stages=[
            {
                "name": "Build",
                "status": "pass",
                "duration": "1m 42s",
                "steps": [
                    {"name": "Install deps", "status": "pass", "duration": "32s"},
                    {"name": "Compile TS", "status": "pass", "duration": "28s"},
                    {"name": "Bundle assets", "status": "pass", "duration": "42s"},
                ],
            },
            {
                "name": "Test",
                "status": "pass",
                "duration": "3m 18s",
                "steps": [
                    {"name": "Unit tests (412)", "status": "pass", "duration": "1m 04s"},
                    {"name": "Integration (87)", "status": "pass", "duration": "1m 52s"},
                    {"name": "E2E tests (24)", "status": "pass", "duration": "22s"},
                ],
            },
            {
                "name": "Security",
                "status": "pass",
                "duration": "0m 48s",
                "steps": [
                    {"name": "SAST analysis", "status": "pass", "duration": "31s"},
                    {"name": "Dep audit", "status": "pass", "duration": "12s"},
                    {"name": "License check", "status": "pass", "duration": "5s"},
                ],
            },
            {
                "name": "Deploy",
                "status": "running",
                "duration": "2m 11s...",
                "steps": [
                    {"name": "Push image", "status": "pass", "duration": "48s"},
                    {"name": "DB migrations", "status": "pass", "duration": "15s"},
                    {"name": "Rolling (3/5)", "status": "running", "duration": "1m 08s..."},
                    {"name": "Health checks", "status": "skip", "duration": "—"},
                    {"name": "DNS cutover", "status": "skip", "duration": "—"},
                ],
            },
        ],
    )
    print(result)


if __name__ == "__main__":
    main()
