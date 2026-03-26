"""Test suite report — coverage, failures, timing, and summary.

Uses the stack() component for responsive layout — side-by-side when wide,
stacked vertically when the terminal is narrow.
"""

from kida.terminal import terminal_env
from kida.utils.terminal_escape import Styled


def main():
    env = terminal_env(terminal_color="basic")

    template = env.from_string("""\
{% from "components.txt" import header, panel, footer, stack %}
{% set w = 66 -%}

{% call header(width=w, style="heavy") -%}
{{ icons.spark | bright_cyan }} {{ "TEST REPORT" | bold | bright_cyan | pad(20) }}{{ project | bold }}
{{ run_id | dim }}
{% endcall %}

{% call panel(title="Results", width=w) -%}

  {{ icons.check | green }} {{ "Passed" | green | bold | pad(12) }}{{ passed | pad(6, align="right") }}
  {{ icons.cross | red }} {{ "Failed" | red | bold | pad(12) }}{{ failed | pad(6, align="right") }}
  {{ icons.circle | dim }} {{ "Skipped" | dim | pad(12) }}{{ skipped | pad(6, align="right") }}
  {{ icons.dash | dim }} {{ "Total" | bold | pad(12) }}{{ total | pad(6, align="right") }}

  {{ "Pass Rate" | kv((pass_rate ~ "%"), width=30) }}
  {{ "Duration" | kv(duration, width=30) }}

{% endcall %}

{% if failures -%}
{% call panel(title="Failures", width=w, style="round") -%}
{% for fail in failures %}
 {{ icons.cross | red }} {{ fail.test | bold | red }}
   {{ fail.file | cyan }}:{{ fail.line | yellow }}

   {{ "Expected:" | dim | pad(12) }} {{ fail.expected | green }}
   {{ "Actual:" | dim | pad(12) }} {{ fail.actual | red }}
{% if fail.message -%}
   {{ "Message:" | dim | pad(12) }} {{ fail.message | yellow }}
{% endif -%}
{% endfor %}
{% endcall %}
{% endif %}

{% call panel(title="Coverage", width=w) -%}

{% for mod in coverage -%}
  {{ mod.name | pad(20) }} {{ mod.pct | bar(width=22) }}  {{ mod.lines_fmt }}
{% endfor %}

  {{ hr(w - 6) }}
  {{ "Total Coverage" | bold | pad(20) }} {{ total_coverage | bar(width=22) }}

{% endcall %}

{% call stack(threshold=60, sep="   ") %}
{{ icons.warn | yellow }} {{ "Slowest Tests" | bold }}
{% for t in slowest -%}
  {{ t.name | truncate(24, end="") | pad(24) }} {{ t.duration | bold }}
{% endfor -%}
|||
{{ icons.gear | dim }} {{ "Environment" | bold }}
  {{ "Python" | kv(python_version, width=24) }}
  {{ "Runner" | kv("pytest 8.3", width=24) }}
  {{ "Workers" | kv("4 (xdist)", width=24) }}
  {{ "Platform" | kv("linux-x86_64", width=24) }}
{% endcall %}

{% if failed > 0 -%}
{% call footer(width=w) -%}
{{ icons.cross | red }} {{ "FAILED" | bold | red }}{{ " — " | dim }}{{ failed ~ " test" ~ ("s" if failed > 1 else "") ~ " failed" }}
{% endcall -%}
{% else -%}
{% call footer(width=w) -%}
{{ icons.check | green }} {{ "ALL TESTS PASSED" | bold | green }}
{% endcall -%}
{% endif -%}
""")

    coverage = [
        {"name": "kida.compiler", "pct": 0.94, "lines": "1,247"},
        {"name": "kida.environment", "pct": 0.88, "lines": "892"},
        {"name": "kida.template", "pct": 0.91, "lines": "634"},
        {"name": "kida.utils", "pct": 0.76, "lines": "1,102"},
        {"name": "kida.terminal", "pct": 0.68, "lines": "510"},
    ]

    # Pre-format coverage lines with color
    for mod in coverage:
        n = mod["lines"]
        if mod["pct"] >= 0.9:
            mod["lines_fmt"] = Styled(f"\033[32m{n} lines\033[0m")
        elif mod["pct"] >= 0.7:
            mod["lines_fmt"] = Styled(f"\033[33m{n} lines\033[0m")
        else:
            mod["lines_fmt"] = Styled(f"\033[31m{n} lines\033[0m")

    print(
        template.render(
            project="kida",
            run_id="Run #4821 — 2026-03-25 14:30:00 UTC — Python 3.14.0",
            passed=408,
            failed=4,
            skipped=12,
            total=424,
            pass_rate=96.2,
            duration="47.3s",
            total_coverage=0.84,
            failures=[
                {
                    "test": "test_async_render_concurrent",
                    "file": "tests/test_async.py",
                    "line": 142,
                    "expected": "['a', 'b', 'c']",
                    "actual": "['a', 'c', 'b']",
                    "message": "Non-deterministic ordering in async gather",
                },
                {
                    "test": "test_cache_ttl_expiry",
                    "file": "tests/test_cache.py",
                    "line": 87,
                    "expected": "None",
                    "actual": "'stale-value'",
                    "message": "TTL not honored under high contention",
                },
                {
                    "test": "test_terminal_truecolor_fg",
                    "file": "tests/terminal/test_filters.py",
                    "line": 203,
                    "expected": r"'\033[38;2;255;128;0mhello\033[0m'",
                    "actual": r"'\033[38;5;208mhello\033[0m'",
                    "message": None,
                },
                {
                    "test": "test_wordwrap_cjk_width",
                    "file": "tests/terminal/test_ansi_width.py",
                    "line": 318,
                    "expected": "3 lines",
                    "actual": "2 lines",
                    "message": "CJK double-width chars miscounted",
                },
            ],
            python_version="3.14.0",
            coverage=coverage,
            slowest=[
                {"name": "test_concurrent_render_100_threads", "duration": "4.21s"},
                {"name": "test_large_template_compilation", "duration": "2.87s"},
                {"name": "test_bytecode_cache_roundtrip", "duration": "1.93s"},
                {"name": "test_recursive_include_depth", "duration": "1.44s"},
                {"name": "test_streaming_backpressure", "duration": "1.12s"},
            ],
        )
    )


if __name__ == "__main__":
    main()
