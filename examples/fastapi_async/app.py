"""FastAPI async integration -- streaming template responses.

Demonstrates kida's render_stream_async() with FastAPI's StreamingResponse
for true streaming HTML delivery. Templates with {% async for %} can
consume async data sources while the response streams to the client.

Requires: fastapi, uvicorn, httpx (optional -- skips gracefully)

Run:
    uvicorn app:app --reload
"""

from collections.abc import AsyncIterator
from pathlib import Path

fastapi = None
try:
    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse

    fastapi = FastAPI  # sentinel for importskip
except ImportError:
    pass

from kida import Environment, FileSystemLoader

templates_dir = Path(__file__).parent / "templates"
env = Environment(loader=FileSystemLoader(str(templates_dir)))


async def fetch_items() -> AsyncIterator[dict]:
    """Simulate an async data source (database cursor, API, etc.)."""
    items = [
        {"name": "Revenue", "value": "$1.2M"},
        {"name": "Users", "value": "45,000"},
        {"name": "Orders", "value": "12,350"},
    ]
    for item in items:
        yield item


if fastapi is not None:
    app = FastAPI()

    @app.get("/")
    async def index() -> StreamingResponse:
        """Stream a kida template as an HTTP response."""
        template = env.get_template("index.html")
        return StreamingResponse(
            template.render_stream_async(
                title="Dashboard",
                items=fetch_items(),
            ),
            media_type="text/html",
        )

    @app.get("/full")
    async def full() -> StreamingResponse:
        """Render the full template (non-streaming) for comparison."""
        template = env.get_template("index.html")
        chunks: list[str] = []
        async for chunk in template.render_stream_async(
            title="Dashboard",
            items=fetch_items(),
        ):
            chunks.append(chunk)
        html = "".join(chunks)
        return StreamingResponse(
            iter([html]),
            media_type="text/html",
        )
else:
    app = None  # type: ignore[assignment]


# For test access via example_app fixture
output = "FastAPI example (run with uvicorn)"


def main() -> None:
    if fastapi is None:
        print("FastAPI not installed. Install with: pip install fastapi uvicorn")
        return
    print("Run with: uvicorn app:app --reload")
    print("Endpoints:")
    print("  GET /     -- streaming response")
    print("  GET /full -- full render response")


if __name__ == "__main__":
    main()
