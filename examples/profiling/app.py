"""Render profiling -- RenderAccumulator performance metrics.

Demonstrates profiled_render() to collect block timings, filter usage,
and macro call counts during rendering. Zero overhead when profiling
is not enabled.

Run:
    python app.py
"""

from pathlib import Path

from kida import Environment, FileSystemLoader, profiled_render

templates_dir = Path(__file__).parent / "templates"
env = Environment(loader=FileSystemLoader(str(templates_dir)))

template = env.get_template("report.html")

context = {
    "title": "Quarterly Report",
    "subtitle": "Q4 2025 Performance Summary",
    "timestamp": "2026-02-08T12:00:00Z",
    "sections": [
        {
            "name": "revenue",
            "description": "Overall revenue grew by 15% compared to Q3, "
            "driven primarily by enterprise subscriptions and platform fees.",
            "entries": ["subscriptions", "platform", "services"],
        },
        {
            "name": "users",
            "description": "Active users increased to 45,000 with strong retention.",
            "entries": ["signups", "active", "churned"],
        },
    ],
}

# Normal render (no profiling overhead)
normal_output = template.render(**context)

# Profiled render (opt-in metrics collection)
with profiled_render() as metrics:
    profiled_output = template.render(**context)

summary = metrics.summary()

output = profiled_output


def main() -> None:
    import json

    print("=== Render Output ===\n")
    print(output[:200], "...\n")
    print("=== Profiling Summary ===\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
