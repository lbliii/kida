"""Tests for the FastAPI async integration example.

Skips gracefully if fastapi or httpx are not installed.
"""

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from starlette.testclient import TestClient


class TestFastApiAsyncApp:
    """Verify FastAPI streaming integration with kida."""

    @pytest.fixture
    def client(self, example_app) -> TestClient:
        """Create a test client from the example FastAPI app."""
        return TestClient(example_app.app)

    def test_streaming_endpoint_returns_html(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_streaming_endpoint_has_content(self, client: TestClient) -> None:
        response = client.get("/")
        assert "Dashboard" in response.text
        assert "Revenue" in response.text
        assert "$1.2M" in response.text

    def test_streaming_endpoint_has_all_items(self, client: TestClient) -> None:
        response = client.get("/")
        assert "Users" in response.text
        assert "Orders" in response.text

    def test_full_endpoint_returns_html(self, client: TestClient) -> None:
        response = client.get("/full")
        assert response.status_code == 200
        assert "Dashboard" in response.text

    def test_both_endpoints_produce_same_content(self, client: TestClient) -> None:
        streaming = client.get("/")
        full = client.get("/full")
        # Both should contain the same data items
        for item in ["Revenue", "Users", "Orders"]:
            assert item in streaming.text
            assert item in full.text
