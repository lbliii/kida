"""Tests for the t_string example."""

import sys

import pytest


@pytest.mark.skipif(
    sys.version_info < (3, 14),
    reason="t-strings require Python 3.14+ (PEP 750)",
)
class TestTStringApp:
    """Verify the t_string example renders correctly."""

    def test_output(self, example_app) -> None:
        if example_app.k is None:
            pytest.skip("k is None (string.templatelib not available)")
        assert example_app.output == "Hello World!"

    def test_auto_escaping(self, example_app) -> None:
        if example_app.k is None:
            pytest.skip("k is None (string.templatelib not available)")
        assert "&lt;script&gt;" in example_app.output_escaped
        assert "alert(1)" in example_app.output_escaped

    def test_equivalent_to_template(self, example_app) -> None:
        if example_app.k is None:
            pytest.skip("k is None (string.templatelib not available)")
        assert example_app.output == example_app.template_equivalent
