"""CI/CD pipeline visualization — multi-stage deploy with nested steps."""

from kida.terminal import terminal_env


def main():
    env = terminal_env(terminal_color="basic")

    template = env.from_string("""\
{% from "components.txt" import header, panel, footer, connector %}
{% set w = 64 -%}

{% call header(width=w) -%}
{{ icons.gear | cyan }} {{ "DEPLOY PIPELINE" | bold | bright_cyan }}{{ " " * 7 }}{{ "v3.8.0" | dim }}{{ " " * 6 }}{{ "prod-us-east-1" | yellow }}
{{ "Triggered by" | dim }} {{ "@lbliii" | bold }}{{ " " * 8 }}{{ "main" | cyan }}{{ " @ " | dim }}{{ "c27bbe6" | yellow }}
{% endcall %}

{% for stage in stages -%}
{% if stage.status == "pass" -%}
{% let color = "green" -%}
{% let icon = icons.check -%}
{% elif stage.status == "running" -%}
{% let color = "cyan" -%}
{% let icon = icons.play -%}
{% elif stage.status == "fail" -%}
{% let color = "red" -%}
{% let icon = icons.cross -%}
{% else -%}
{% let color = "dim" -%}
{% let icon = icons.circle -%}
{% endif -%}

{% call panel(title=stage.name, width=w) -%}
{{ icon | fg(color) }} {{ stage.name | bold | fg(color) | pad(26) }}{{ stage.status | badge | pad(10) }}{{ stage.duration | dim | pad(16, align="right") }}
{{ hr(w - 6) }}
{% for step in stage.steps -%}
  {% if step.status == "pass" %}{{ icons.check | green }}{% elif step.status == "fail" %}{{ icons.cross | red }}{% elif step.status == "running" %}{{ icons.play | cyan }}{% else %}{{ icons.circle | dim }}{% endif %} {{ step.name | pad(24) }}{{ step.status | badge | pad(10) }}{{ step.duration | dim | pad(16, align="right") }}
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

    stages = [
        {
            "name": "Build",
            "status": "pass",
            "duration": "1m 42s",
            "steps": [
                {"name": "Install dependencies", "status": "pass", "duration": "32s"},
                {"name": "Compile TypeScript", "status": "pass", "duration": "28s"},
                {"name": "Bundle assets", "status": "pass", "duration": "42s"},
            ],
        },
        {
            "name": "Test",
            "status": "pass",
            "duration": "3m 18s",
            "steps": [
                {"name": "Unit tests (412)", "status": "pass", "duration": "1m 04s"},
                {"name": "Integration tests (87)", "status": "pass", "duration": "1m 52s"},
                {"name": "E2E tests (24)", "status": "pass", "duration": "22s"},
            ],
        },
        {
            "name": "Security Scan",
            "status": "pass",
            "duration": "0m 48s",
            "steps": [
                {"name": "SAST analysis", "status": "pass", "duration": "31s"},
                {"name": "Dependency audit", "status": "pass", "duration": "12s"},
                {"name": "License check", "status": "pass", "duration": "5s"},
            ],
        },
        {
            "name": "Deploy",
            "status": "running",
            "duration": "2m 11s...",
            "steps": [
                {"name": "Push container image", "status": "pass", "duration": "48s"},
                {"name": "Database migrations", "status": "pass", "duration": "15s"},
                {"name": "Rolling update (3/5)", "status": "running", "duration": "1m 08s..."},
                {"name": "Health checks", "status": "skip", "duration": "—"},
                {"name": "DNS cutover", "status": "skip", "duration": "—"},
            ],
        },
    ]

    print(
        template.render(
            stages=stages,
            total_duration="8m 01s",
            final_status="running",
        )
    )


if __name__ == "__main__":
    main()
