"""Terminal dashboard example with file loader."""

import os

from kida import Environment, FileSystemLoader


def main():
    templates_dir = os.path.join(os.path.dirname(__file__), "templates")
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape="terminal",
        terminal_color="basic",
    )

    template = env.get_template("dashboard.txt")
    result = template.render(
        services=[
            {"name": "API Gateway", "status": "pass", "uptime": "99.9% (30d)"},
            {"name": "Auth Service", "status": "pass", "uptime": "99.7% (30d)"},
            {"name": "Worker Pool", "status": "warn", "uptime": "98.2% (30d)"},
            {"name": "Cache Layer", "status": "fail", "uptime": "94.1% (30d)"},
        ],
        resources=[
            {"name": "CPU", "usage": 0.62, "detail": "8/16 cores"},
            {"name": "Memory", "usage": 0.78, "detail": "12.5/16 GiB"},
            {"name": "Disk", "usage": 0.45, "detail": "180/400 GiB"},
            {"name": "Network", "usage": 0.23, "detail": "2.3 Gbps"},
        ],
        events=[
            {"time": "14:32:01", "level": "info", "message": "Deployment v2.4.1 complete"},
            {"time": "14:28:15", "level": "warn", "message": "Cache hit rate dropped below 80%"},
            {"time": "14:15:42", "level": "fail", "message": "Cache node-3 unreachable"},
            {"time": "13:58:00", "level": "pass", "message": "Health check restored for worker-7"},
        ],
        updated="2024-01-15 14:32:01 UTC",
    )
    print(result)


if __name__ == "__main__":
    main()
