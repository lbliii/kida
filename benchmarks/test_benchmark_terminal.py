"""Benchmark Phase 1 compiler optimizations on terminal-mode templates.

Validates that partial evaluation, dead branch elimination, and filter
constant folding benefit Milo-style templates where LiveRenderer re-renders
on every state change.

Run with: pytest benchmarks/test_benchmark_terminal.py --benchmark-only -v
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kida.terminal import terminal_env

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


# =============================================================================
# Milo-style dashboard template — realistic LiveRenderer hot path
# =============================================================================

DASHBOARD_TEMPLATE = """\
{%- set w = 64 -%}
{#- Static header: version/target known at compile time for Milo apps -#}
{{ app_icon | bold | bright_cyan }} {{ app_title | bold | bright_cyan | pad(24) }}{{ version | dim | pad(14) }}{{ target | yellow }}
{{ hr(w) }}

{#- Status section: static config, dynamic per-render data -#}
{% if show_metrics -%}
{% for metric in metrics -%}
{% if metric.status == "ok" -%}
  {{ icons.check | green }} {{ metric.name | pad(20) }}{{ metric.value | pad(10, align="right") }}{{ metric.status | badge }}
{% elif metric.status == "warn" -%}
  {{ icons.warn | yellow }} {{ metric.name | bold | pad(20) }}{{ metric.value | pad(10, align="right") }}{{ metric.status | badge }}
{% elif metric.status == "fail" -%}
  {{ icons.cross | red }} {{ metric.name | bold | pad(20) }}{{ metric.value | pad(10, align="right") }}{{ metric.status | badge }}
{% else -%}
  {{ icons.circle | dim }} {{ metric.name | dim | pad(20) }}{{ metric.value | dim | pad(10, align="right") }}{{ "pending" | badge }}
{% endif -%}
{% endfor -%}
{% endif -%}

{#- Progress section -#}
{{ hr(w) }}
{{ "Progress" | bold | cyan }}  {{ progress | bar(width=30) }}

{#- Debug panel: dead branch when debug=False (most Milo apps) -#}
{% if debug -%}
{{ hr(w, title="DEBUG") }}
  Render count: {{ render_count }}
  Frame time:   {{ frame_time_ms }}ms
  State size:   {{ state_size }} bytes
{% endif -%}

{#- Footer with static app info -#}
{{ hr(w) }}
{{ app_title | dim }} v{{ version | dim }}  {{ "│" | dim }}  {{ target | dim }}
"""


# Static context: known at Milo app init, never changes between renders
STATIC_CTX = {
    "app_title": "System Monitor",
    "app_icon": "⚙",
    "version": "2.4.1",
    "target": "prod-us-east-1",
    "show_metrics": True,
    "debug": False,
}

# Dynamic context: changes every LiveRenderer.update() call
DYNAMIC_CTX = {
    "metrics": [
        {"name": "CPU Usage", "value": "67%", "status": "ok"},
        {"name": "Memory", "value": "4.2 GB", "status": "ok"},
        {"name": "Disk I/O", "value": "128 MB/s", "status": "warn"},
        {"name": "Network", "value": "1.2 Gbps", "status": "ok"},
        {"name": "Error Rate", "value": "0.02%", "status": "ok"},
        {"name": "Latency P99", "value": "342ms", "status": "warn"},
        {"name": "Queue Depth", "value": "1,847", "status": "fail"},
        {"name": "Connections", "value": "2,401", "status": "ok"},
    ],
    "progress": 0.73,
    "render_count": 142,
    "frame_time_ms": 8.4,
    "state_size": 2048,
}


# =============================================================================
# Simpler template: status bar (minimal, high-frequency re-render)
# =============================================================================

STATUS_BAR_TEMPLATE = """\
{{ app_name | bold | cyan }} {{ separator | dim }} {{ status_text | bold }}{{ status_icon }}  {{ progress | bar(width=20) }}  {{ elapsed | dim }}  {{ message | truncate(40) | dim }}
"""

STATUS_STATIC = {
    "app_name": "deploy",
    "separator": "│",
}

STATUS_DYNAMIC = {
    "status_text": "Building",
    "status_icon": " ⣾",
    "progress": 0.45,
    "elapsed": "1m 23s",
    "message": "Compiling TypeScript modules (412/891)",
}


# =============================================================================
# Key-value list template (definition list pattern common in Milo)
# =============================================================================

KV_LIST_TEMPLATE = """\
{{ title | bold | underline | cyan }}
{% for item in items -%}
{{ item.label | kv(item.value, width=label_width, sep=separator) }}
{% endfor -%}
"""

KV_STATIC = {
    "title": "Server Info",
    "label_width": 50,
    "separator": " : ",
}

KV_DYNAMIC = {
    "items": [
        {"label": "Hostname", "value": "prod-web-01.us-east-1"},
        {"label": "IP Address", "value": "10.0.42.7"},
        {"label": "Uptime", "value": "42d 3h 17m"},
        {"label": "OS", "value": "Ubuntu 24.04 LTS"},
        {"label": "Kernel", "value": "6.8.0-45-generic"},
        {"label": "CPU", "value": "AMD EPYC 7763 (8 cores)"},
        {"label": "Memory", "value": "16 GB / 32 GB (50%)"},
        {"label": "Load Avg", "value": "2.34 / 1.87 / 1.42"},
    ],
}


# =============================================================================
# Benchmarks: Dashboard (Milo hot-path simulation)
# =============================================================================


class TestTerminalDashboardBenchmarks:
    """Simulate LiveRenderer.update() hot path with Milo-style dashboard."""

    def test_dashboard_no_static_context(self, benchmark: BenchmarkFixture) -> None:
        """Baseline: all context resolved at render time."""
        env = terminal_env(terminal_color="none", terminal_width=80)
        tpl = env.from_string(DASHBOARD_TEMPLATE)

        ctx = {**STATIC_CTX, **DYNAMIC_CTX}

        result = benchmark(tpl.render, **ctx)
        assert "System Monitor" in result
        # Debug panel should NOT appear (debug=False)
        assert "Render count" not in result

    def test_dashboard_with_static_context(self, benchmark: BenchmarkFixture) -> None:
        """Optimized: app config folded at compile time, debug branch eliminated."""
        env = terminal_env(terminal_color="none", terminal_width=80)
        tpl = env.from_string(
            DASHBOARD_TEMPLATE,
            static_context=STATIC_CTX,
        )

        # Static context still passed for runtime (terminal filters need it)
        ctx = {**STATIC_CTX, **DYNAMIC_CTX}

        result = benchmark(tpl.render, **ctx)
        assert "System Monitor" in result
        assert "Render count" not in result

    def test_dashboard_with_inlining(self, benchmark: BenchmarkFixture) -> None:
        """Optimized: static context + component inlining."""
        env = terminal_env(
            terminal_color="none",
            terminal_width=80,
            inline_components=True,
        )
        tpl = env.from_string(
            DASHBOARD_TEMPLATE,
            static_context=STATIC_CTX,
        )

        ctx = {**STATIC_CTX, **DYNAMIC_CTX}

        result = benchmark(tpl.render, **ctx)
        assert "System Monitor" in result
        assert "Render count" not in result


# =============================================================================
# Benchmarks: Status bar (high-frequency, minimal template)
# =============================================================================


class TestTerminalStatusBarBenchmarks:
    """Minimal status bar — simulates highest-frequency LiveRenderer updates."""

    def test_status_bar_no_static(self, benchmark: BenchmarkFixture) -> None:
        """Baseline: everything dynamic."""
        env = terminal_env(terminal_color="none", terminal_width=80)
        tpl = env.from_string(STATUS_BAR_TEMPLATE)

        ctx = {**STATUS_STATIC, **STATUS_DYNAMIC}

        result = benchmark(tpl.render, **ctx)
        assert "deploy" in result

    def test_status_bar_with_static(self, benchmark: BenchmarkFixture) -> None:
        """Optimized: app_name and separator folded at compile time."""
        env = terminal_env(terminal_color="none", terminal_width=80)
        tpl = env.from_string(
            STATUS_BAR_TEMPLATE,
            static_context=STATUS_STATIC,
        )

        ctx = {**STATUS_STATIC, **STATUS_DYNAMIC}

        result = benchmark(tpl.render, **ctx)
        assert "deploy" in result


# =============================================================================
# Benchmarks: Key-value list (definition list pattern)
# =============================================================================


class TestTerminalKVListBenchmarks:
    """Key-value definition list — common Milo pattern for info panels."""

    def test_kv_list_no_static(self, benchmark: BenchmarkFixture) -> None:
        """Baseline: title, width, separator all dynamic."""
        env = terminal_env(terminal_color="none", terminal_width=80)
        tpl = env.from_string(KV_LIST_TEMPLATE)

        ctx = {**KV_STATIC, **KV_DYNAMIC}

        result = benchmark(tpl.render, **ctx)
        assert "Server Info" in result

    def test_kv_list_with_static(self, benchmark: BenchmarkFixture) -> None:
        """Optimized: title, width, separator folded; only items dynamic."""
        env = terminal_env(terminal_color="none", terminal_width=80)
        tpl = env.from_string(
            KV_LIST_TEMPLATE,
            static_context=KV_STATIC,
        )

        ctx = {**KV_STATIC, **KV_DYNAMIC}

        result = benchmark(tpl.render, **ctx)
        assert "Server Info" in result


# =============================================================================
# Benchmarks: Color depth impact on terminal filter performance
# =============================================================================


class TestColorDepthBenchmarks:
    """Measure rendering cost across color depths (none vs truecolor)."""

    def test_dashboard_color_none(self, benchmark: BenchmarkFixture) -> None:
        """No ANSI codes emitted — filters return plain strings."""
        env = terminal_env(terminal_color="none", terminal_width=80)
        tpl = env.from_string(DASHBOARD_TEMPLATE)

        ctx = {**STATIC_CTX, **DYNAMIC_CTX}

        result = benchmark(tpl.render, **ctx)
        assert "System Monitor" in result

    def test_dashboard_color_basic(self, benchmark: BenchmarkFixture) -> None:
        """8-color ANSI codes."""
        env = terminal_env(terminal_color="basic", terminal_width=80)
        tpl = env.from_string(DASHBOARD_TEMPLATE)

        ctx = {**STATIC_CTX, **DYNAMIC_CTX}

        result = benchmark(tpl.render, **ctx)
        assert "System Monitor" in result

    def test_dashboard_color_truecolor(self, benchmark: BenchmarkFixture) -> None:
        """Full 24-bit ANSI codes — maximum escape sequence overhead."""
        env = terminal_env(terminal_color="truecolor", terminal_width=80)
        tpl = env.from_string(DASHBOARD_TEMPLATE)

        ctx = {**STATIC_CTX, **DYNAMIC_CTX}

        result = benchmark(tpl.render, **ctx)
        assert "System Monitor" in result
