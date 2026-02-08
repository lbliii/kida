"""Concurrent rendering -- free-threading proof with 8 threads.

Kida renders templates concurrently without GIL contention. Each thread
gets its own render context via ContextVar, so there is zero
cross-contamination between simultaneous renders.

Run:
    python app.py
"""

from concurrent.futures import ThreadPoolExecutor

from kida import Environment

env = Environment()

# Each thread renders a different template with different context
TEMPLATE_SOURCE = """\
<article id="page-{{ page_id }}">
  <h1>{{ title }}</h1>
  <ul>
  {% for tag in tags %}
    <li>{{ tag }}</li>
  {% end %}
  </ul>
</article>"""

template = env.from_string(TEMPLATE_SOURCE)

pages = [
    {"page_id": i, "title": f"Page {i}", "tags": [f"tag-{i}-a", f"tag-{i}-b", f"tag-{i}-c"]}
    for i in range(8)
]


def render_page(page: dict) -> str:
    """Render a single page -- called from a worker thread."""
    return template.render(**page)


# Concurrent rendering -- no GIL contention
with ThreadPoolExecutor(max_workers=8) as pool:
    results = list(pool.map(render_page, pages))

output = "\n".join(results)


def main() -> None:
    print(f"Rendered {len(results)} pages across 8 threads:\n")
    for i, html in enumerate(results):
        print(f"--- Thread {i} ---")
        print(html)
        print()


if __name__ == "__main__":
    main()
