"""Streaming rendering -- chunked output with render_stream().

render_stream() yields template output as string chunks at statement
boundaries. Ideal for chunked HTTP responses and Server-Sent Events.

Run:
    python app.py
"""

from pathlib import Path

from kida import Environment, FileSystemLoader

templates_dir = Path(__file__).parent / "templates"
env = Environment(loader=FileSystemLoader(str(templates_dir)))

template = env.get_template("report.html")

context = {
    "title": "Quarterly Report",
    "sections": [
        {"name": "Revenue", "value": "$1.2M", "trend": "up"},
        {"name": "Users", "value": "45,000", "trend": "up"},
        {"name": "Churn", "value": "2.1%", "trend": "down"},
    ],
}

# Collect chunks for testing
chunks = list(template.render_stream(**context))
output = "".join(chunks)


def main() -> None:
    print(f"Streaming {len(chunks)} chunks:\n")
    for i, chunk in enumerate(template.render_stream(**context)):
        print(f"[chunk {i}] {chunk!r}")
    print(f"\n--- Full output ({len(chunks)} chunks) ---\n")
    print(output)


if __name__ == "__main__":
    main()
