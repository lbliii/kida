"""Animated deploy pipeline — stages transition from pending → running → done.

Demonstrates LiveRenderer for in-place terminal re-rendering with spinners,
progress bars, and animated state transitions.

    python examples/terminal_live/run.py
"""

import time

from kida.terminal import LiveRenderer, terminal_env

TEMPLATE = """\
{% from "components.txt" import header, panel, footer, connector %}
{% set w = 64 -%}

{% call header(width=w) -%}
{{ icons.gear | bright_cyan }} {{ "DEPLOY PIPELINE" | bold | bright_cyan | pad(20) }}{{ version | dim | pad(12) }}{{ target | yellow }}
{% endcall %}

{% for stage in stages -%}
{% if stage.status == "pass" -%}
{% let icon = icons.check | green -%}
{% let label = stage.name | bold | green -%}
{% elif stage.status == "running" -%}
{% let icon = spinner() | cyan -%}
{% let label = stage.name | bold | cyan -%}
{% elif stage.status == "fail" -%}
{% let icon = icons.cross | red -%}
{% let label = stage.name | bold | red -%}
{% else -%}
{% let icon = icons.circle | dim -%}
{% let label = stage.name | dim -%}
{% endif -%}

{% call panel(title=stage.name, width=w) -%}
{{ icon }} {{ label | pad(26) }}{{ stage.status | badge | pad(10) }}{{ stage.duration | dim | pad(14, align="right") }}
{% if stage.status != "pending" -%}
{{ hr(w - 6) }}
{% for step in stage.steps -%}
{% if step.status == "pass" -%}
  {{ icons.check | green }} {{ step.name | pad(24) }}{{ step.status | badge | pad(10) }}{{ step.duration | dim | pad(14, align="right") }}
{% elif step.status == "running" -%}
  {{ spinner() | cyan }} {{ step.name | bold | pad(24) }}{{ step.status | badge | pad(10) }}{{ step.duration | dim | pad(14, align="right") }}
{% elif step.status == "fail" -%}
  {{ icons.cross | red }} {{ step.name | pad(24) }}{{ step.status | badge | pad(10) }}{{ step.duration | dim | pad(14, align="right") }}
{% else -%}
  {{ icons.circle | dim }} {{ step.name | dim | pad(24) }}{{ "" | pad(10) }}{{ "" | pad(14) }}
{% endif -%}
{% endfor -%}
{% endif -%}
{% endcall %}
{% if not loop.last -%}
{{ connector() }}
{% endif -%}
{% endfor %}

{% call footer(width=w) -%}
{{ icons.zap | yellow }} {{ "PROGRESS" | bold | yellow }}{{ " " * 8 }}{{ overall_progress | bar(width=28) }}
{% endcall -%}
"""


def main():
    env = terminal_env()
    tpl = env.from_string(TEMPLATE, name="live-deploy")

    stages = [
        {
            "name": "Build",
            "status": "pending",
            "duration": "",
            "steps": [
                {"name": "Install dependencies", "status": "pending", "duration": ""},
                {"name": "Compile TypeScript", "status": "pending", "duration": ""},
                {"name": "Bundle assets", "status": "pending", "duration": ""},
            ],
        },
        {
            "name": "Test",
            "status": "pending",
            "duration": "",
            "steps": [
                {"name": "Unit tests (412)", "status": "pending", "duration": ""},
                {"name": "Integration (87)", "status": "pending", "duration": ""},
                {"name": "E2E tests (24)", "status": "pending", "duration": ""},
            ],
        },
        {
            "name": "Security",
            "status": "pending",
            "duration": "",
            "steps": [
                {"name": "SAST analysis", "status": "pending", "duration": ""},
                {"name": "Dependency audit", "status": "pending", "duration": ""},
                {"name": "License check", "status": "pending", "duration": ""},
            ],
        },
        {
            "name": "Deploy",
            "status": "pending",
            "duration": "",
            "steps": [
                {"name": "Push container image", "status": "pending", "duration": ""},
                {"name": "Database migrations", "status": "pending", "duration": ""},
                {"name": "Rolling update", "status": "pending", "duration": ""},
                {"name": "Health checks", "status": "pending", "duration": ""},
            ],
        },
    ]

    # Simulated step durations and total completion times
    step_durations = [
        ["32s", "28s", "42s"],
        ["1m 04s", "1m 52s", "22s"],
        ["31s", "12s", "5s"],
        ["48s", "15s", "1m 08s", "12s"],
    ]
    stage_durations = ["1m 42s", "3m 18s", "0m 48s", "2m 23s"]

    base_ctx = {
        "version": "v3.8.0",
        "target": "prod-us-east-1",
        "stages": stages,
        "overall_progress": 0.0,
    }

    total_steps = sum(len(s["steps"]) for s in stages)
    completed_steps = 0

    with LiveRenderer(tpl, refresh_rate=0.1) as live:
        # Initial render — everything pending
        live.update(**base_ctx)
        time.sleep(0.8)

        for i, stage in enumerate(stages):
            # Stage starts running
            stage["status"] = "running"
            live.start_auto(**base_ctx)
            time.sleep(0.4)

            for j, step in enumerate(stage["steps"]):
                # Step starts running
                step["status"] = "running"
                step["duration"] = "..."
                time.sleep(0.3 + 0.2 * (j % 3))  # Varying step times

                # Step completes
                step["status"] = "pass"
                step["duration"] = step_durations[i][j]
                completed_steps += 1
                base_ctx["overall_progress"] = completed_steps / total_steps

            # Stage completes
            live.stop_auto()
            stage["status"] = "pass"
            stage["duration"] = stage_durations[i]
            live.update(**base_ctx)
            time.sleep(0.3)

    print()  # Final newline after live render


if __name__ == "__main__":
    main()
