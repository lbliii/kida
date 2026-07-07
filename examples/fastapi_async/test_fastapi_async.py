"""Tests for the FastAPI async integration example.

Skips gracefully if fastapi or httpx are not installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")


class TestFastApiAsyncApp:
    """Verify FastAPI streaming integration with kida."""

    @pytest.fixture
    async def client(self, example_app) -> AsyncIterator[httpx.AsyncClient]:
        """Create an HTTPX client over the example's ASGI transport."""
        transport = httpx.ASGITransport(app=example_app.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client

    async def test_streaming_endpoint_returns_html(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    async def test_streaming_endpoint_has_content(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/")
        assert "Dashboard" in response.text
        assert "Revenue" in response.text
        assert "$1.2M" in response.text

    async def test_streaming_endpoint_has_all_items(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/")
        assert "Users" in response.text
        assert "Orders" in response.text

    async def test_full_endpoint_returns_html(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/full")
        assert response.status_code == 200
        assert "Dashboard" in response.text

    async def test_both_endpoints_produce_same_content(self, client: httpx.AsyncClient) -> None:
        streaming = await client.get("/")
        full = await client.get("/full")
        # Both should contain the same data items
        for item in ["Revenue", "Users", "Orders"]:
            assert item in streaming.text
            assert item in full.text
