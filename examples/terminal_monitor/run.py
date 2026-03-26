"""Multi-panel system monitor with sparkline bars, tables, and status panels.

Uses RGB hex colors via fg() — these degrade gracefully:
    truecolor: full 24-bit RGB
    256:       nearest xterm-256 palette entry
    basic:     nearest ANSI 16-color
    none:      plain text, no color
"""

from kida.terminal import terminal_env
from kida.utils.terminal_escape import Styled


def main():
    env = terminal_env(terminal_color="basic")

    template = env.from_string("""\
{% from "components.txt" import header, panel %}
{% set w = 70 -%}

{% call header(width=w) -%}
{{ icons.gear | bright_cyan }} {{ "SYSTEM MONITOR" | bold | bright_cyan | pad(24) }}{{ hostname | yellow | pad(16) }}{{ uptime | dim }}
{% endcall %}

{% call panel(title="CPU & Memory", width=w) -%}

{% for core in cores -%}
  {{ core.name | pad(8) }} {{ core.usage | bar(width=28) }}  {{ core.temp | fg(core.temp_color) | pad(6) }}
{% endfor %}

  {{ "Memory" | pad(8) }} {{ mem.usage | bar(width=28) }}  {{ mem.detail | dim }}
  {{ "Swap" | pad(8) }} {{ swap.usage | bar(width=28) }}  {{ swap.detail | dim }}
{% endcall %}

{% call panel(title="Network I/O", width=w) -%}

{% for iface in interfaces -%}
  {{ iface.name | bold | pad(8) }} {{ icons.arrow_u | green }} {{ iface.tx | pad(12) }} {{ icons.arrow_d | cyan }} {{ iface.rx | pad(12) }}  {{ iface.status | badge }}
{% endfor %}

{% endcall %}

{% call panel(title="Disk Usage", width=w) -%}

{% for disk in disks -%}
  {{ disk.mount | bold | pad(12) }} {{ disk.usage | bar(width=22) }}  {{ disk.used | pad(10, align="right") }} / {{ disk.total | pad(8) }}
{% endfor %}

{% endcall %}

{% call panel(title="Top Processes", width=w) -%}

  {{ "PID" | underline | pad(8) }} {{ "COMMAND" | underline | pad(20) }} {{ "CPU%" | underline | pad(8, align="right") }} {{ "MEM%" | underline | pad(8, align="right") }} {{ "STATUS" | underline | pad(8) }}
{% for proc in processes -%}
  {{ proc.pid | dim | pad(8) }} {{ proc.command | bold | pad(20) }} {{ proc.cpu_fmt | pad(8, align="right") }} {{ (proc.mem ~ "%") | pad(8, align="right") }} {{ proc.status | badge | pad(8) }}
{% endfor %}

{% endcall %}

{{ icons.reload | dim }} {{ "Refreshed" | dim }} {{ timestamp | dim }}
""")

    # RGB hex colors — degrade to 256/basic via color depth fallback
    cores = [
        {"name": "Core 0", "usage": 0.92, "temp": "78°C", "temp_color": "#ff4444"},
        {"name": "Core 1", "usage": 0.67, "temp": "64°C", "temp_color": "#ffaa00"},
        {"name": "Core 2", "usage": 0.34, "temp": "52°C", "temp_color": "#44cc44"},
        {"name": "Core 3", "usage": 0.88, "temp": "74°C", "temp_color": "#ff4444"},
        {"name": "Core 4", "usage": 0.15, "temp": "44°C", "temp_color": "#44cc44"},
        {"name": "Core 5", "usage": 0.55, "temp": "58°C", "temp_color": "#ffaa00"},
        {"name": "Core 6", "usage": 0.71, "temp": "66°C", "temp_color": "#ffaa00"},
        {"name": "Core 7", "usage": 0.43, "temp": "54°C", "temp_color": "#44cc44"},
    ]

    processes = [
        {"pid": "1842", "command": "postgres", "cpu": 67.2, "mem": 24.1, "status": "pass"},
        {"pid": "2103", "command": "node (api-server)", "cpu": 34.8, "mem": 18.7, "status": "pass"},
        {"pid": "892", "command": "nginx", "cpu": 12.4, "mem": 3.2, "status": "pass"},
        {"pid": "3301", "command": "redis-server", "cpu": 8.1, "mem": 12.8, "status": "warn"},
        {"pid": "4417", "command": "celery-worker", "cpu": 52.3, "mem": 8.4, "status": "pass"},
    ]

    # Pre-format CPU with color
    for proc in processes:
        pct = f"{proc['cpu']}%"
        if proc["cpu"] > 50:
            proc["cpu_fmt"] = Styled(f"\033[31m\033[1m{pct}\033[0m")
        elif proc["cpu"] > 20:
            proc["cpu_fmt"] = Styled(f"\033[33m{pct}\033[0m")
        else:
            proc["cpu_fmt"] = Styled(f"\033[32m{pct}\033[0m")

    print(
        template.render(
            hostname="prod-app-01",
            uptime="up 42d 7h 23m",
            cores=cores,
            mem={"usage": 0.78, "detail": "12.5 / 16.0 GiB"},
            swap={"usage": 0.12, "detail": "0.5 / 4.0 GiB"},
            interfaces=[
                {"name": "eth0", "tx": "142.3 MB/s", "rx": "891.2 MB/s", "status": "pass"},
                {"name": "eth1", "tx": "2.1 MB/s", "rx": "0.4 MB/s", "status": "pass"},
                {"name": "lo", "tx": "44.8 MB/s", "rx": "44.8 MB/s", "status": "pass"},
                {"name": "wg0", "tx": "0.0 MB/s", "rx": "0.0 MB/s", "status": "warn"},
            ],
            disks=[
                {"mount": "/", "usage": 0.42, "used": "84.2 GiB", "total": "200 GiB"},
                {"mount": "/data", "usage": 0.87, "used": "1.74 TiB", "total": "2.0 TiB"},
                {"mount": "/var/log", "usage": 0.63, "used": "31.5 GiB", "total": "50 GiB"},
                {"mount": "/tmp", "usage": 0.08, "used": "0.8 GiB", "total": "10 GiB"},
            ],
            processes=processes,
            timestamp="2026-03-25 14:32:01 UTC",
        )
    )


if __name__ == "__main__":
    main()
