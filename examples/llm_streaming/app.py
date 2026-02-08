"""LLM token streaming -- async rendering of AI responses.

Demonstrates {% async for %} consuming a simulated LLM token stream.
The template renders progressively as tokens arrive, yielding HTML
chunks via render_stream_async(). This is O(n) total work instead of
the O(n^2) re-render-per-token pattern.

Run:
    python app.py
"""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

from kida import Environment, FileSystemLoader

templates_dir = Path(__file__).parent / "templates"
env = Environment(loader=FileSystemLoader(str(templates_dir)))

template = env.get_template("chat.html")


async def simulated_llm_stream() -> AsyncIterator[str]:
    """Simulate LLM tokens arriving one at a time.

    In production this would be an API call to OpenAI, Anthropic, etc.
    Each yield represents a single token from the language model.
    """
    tokens = [
        "Kida",
        " is",
        " a",
        " modern",
        " template",
        " engine",
        " built",
        " for",
        " Python",
        " 3.14t.",
    ]
    for token in tokens:
        yield token


async def render() -> tuple[str, list[str]]:
    """Render the chat template, collecting chunks as they stream."""
    chunks: list[str] = []
    async for chunk in template.render_stream_async(
        prompt="What is Kida?",
        stream=simulated_llm_stream(),
    ):
        chunks.append(chunk)
    return "".join(chunks), chunks


# Run at import time for test access
output, chunks = asyncio.run(render())


def main() -> None:
    print(f"Streamed {len(chunks)} chunks:\n")
    for i, chunk in enumerate(chunks):
        print(f"  [chunk {i}] {chunk!r}")
    print(f"\n--- Full output ---\n")
    print(output)


if __name__ == "__main__":
    main()
