"""Async rendering -- native async for and await in templates.

Demonstrates {% async for %} consuming async iterables and {{ await }}
resolving coroutines inline. Uses render_stream_async() for async output.

Run:
    python app.py
"""

import asyncio
from collections.abc import AsyncIterator

from kida import DictLoader, Environment

# -- Simulated async data sources ----------------------------------------


async def fetch_items() -> AsyncIterator[dict]:
    """Simulate an async data stream (e.g., database cursor, API pagination)."""
    items = [
        {"id": 1, "title": "AST-native compilation"},
        {"id": 2, "title": "Free-threading support"},
        {"id": 3, "title": "Zero dependencies"},
    ]
    for item in items:
        yield item


async def fetch_count() -> int:
    """Simulate an async API call that returns a value."""
    return 3


# -- Template setup -------------------------------------------------------

TEMPLATE_SOURCE = """\
<h1>{{ await fetch_title() }}</h1>
<p>Total: {{ await fetch_count() }} features</p>
<ul>
{% async for item in fetch_items() %}
    <li>#{{ item.id }}: {{ item.title }}</li>
{% empty %}
    <li>No items found</li>
{% end %}
</ul>
"""

env = Environment()
template = env.from_string(TEMPLATE_SOURCE)


async def fetch_title() -> str:
    """Simulate fetching a page title."""
    return "Kida Features"


async def render() -> str:
    """Render the async template by collecting all chunks."""
    chunks = []
    async for chunk in template.render_stream_async(
        fetch_items=fetch_items,
        fetch_count=fetch_count,
        fetch_title=fetch_title,
    ):
        chunks.append(chunk)
    return "".join(chunks)


# Run at import time for test access
output = asyncio.run(render())


def main() -> None:
    print(output)


if __name__ == "__main__":
    main()
