"""Tests for HTMX test functions (Feature 1.2)."""

import pytest

from kida import Environment


class MockRequest:
    """Mock request object for testing."""

    def __init__(self, headers: dict):
        self.headers = headers


class TestHXRequestTest:
    """Test the 'is hx_request' test function."""

    def test_with_request_object_true(self):
        """Test 'is hx_request' with request object (HX-Request: true)."""
        env = Environment()
        template = env.from_string("{{ request is hx_request }}")

        request = MockRequest({"HX-Request": "true"})
        result = template.render(request=request)

        assert result == "True"

    def test_with_request_object_false(self):
        """Test 'is hx_request' with request object (no HX-Request header)."""
        env = Environment()
        template = env.from_string("{{ request is hx_request }}")

        request = MockRequest({})
        result = template.render(request=request)

        assert result == "False"

    def test_with_boolean_true(self):
        """Test 'is hx_request' with boolean True."""
        env = Environment()
        template = env.from_string("{{ value is hx_request }}")

        result = template.render(value=True)
        assert result == "True"

    def test_with_boolean_false(self):
        """Test 'is hx_request' with boolean False."""
        env = Environment()
        template = env.from_string("{{ value is hx_request }}")

        result = template.render(value=False)
        assert result == "False"

    def test_conditional_rendering(self):
        """Test conditional rendering based on 'is hx_request'."""
        env = Environment()
        template = env.from_string("""
{% if request is hx_request %}
  Fragment
{% else %}
  Full Page
{% end %}
        """.strip())

        # HTMX request
        request = MockRequest({"HX-Request": "true"})
        result = template.render(request=request)
        assert "Fragment" in result
        assert "Full Page" not in result

        # Regular request
        request = MockRequest({})
        result = template.render(request=request)
        assert "Full Page" in result
        assert "Fragment" not in result

    def test_negation(self):
        """Test 'is not hx_request' negation."""
        env = Environment()
        template = env.from_string("""
{% if request is not hx_request %}
  Standard HTML
{% end %}
        """.strip())

        request = MockRequest({})
        result = template.render(request=request)
        assert "Standard HTML" in result

    def test_case_insensitive_header_value(self):
        """Test that header value comparison is case-insensitive."""
        env = Environment()
        template = env.from_string("{{ request is hx_request }}")

        # Test various casings
        for value in ["true", "True", "TRUE", "tRuE"]:
            request = MockRequest({"HX-Request": value})
            result = template.render(request=request)
            assert result == "True", f"Failed for HX-Request: {value}"


class TestHXTargetTest:
    """Test the 'is hx_target' test function."""

    def test_with_request_object_matching(self):
        """Test 'is hx_target' with matching target."""
        env = Environment()
        template = env.from_string('{{ request is hx_target("user-list") }}')

        request = MockRequest({"HX-Target": "user-list"})
        result = template.render(request=request)

        assert result == "True"

    def test_with_request_object_not_matching(self):
        """Test 'is hx_target' with non-matching target."""
        env = Environment()
        template = env.from_string('{{ request is hx_target("user-list") }}')

        request = MockRequest({"HX-Target": "sidebar"})
        result = template.render(request=request)

        assert result == "False"

    def test_with_request_object_missing_header(self):
        """Test 'is hx_target' when HX-Target header is missing."""
        env = Environment()
        template = env.from_string('{{ request is hx_target("user-list") }}')

        request = MockRequest({})
        result = template.render(request=request)

        assert result == "False"

    def test_with_string_value_matching(self):
        """Test 'is hx_target' with string value."""
        env = Environment()
        template = env.from_string('{{ target is hx_target("sidebar") }}')

        result = template.render(target="sidebar")
        assert result == "True"

    def test_with_string_value_not_matching(self):
        """Test 'is hx_target' with non-matching string."""
        env = Environment()
        template = env.from_string('{{ target is hx_target("sidebar") }}')

        result = template.render(target="main")
        assert result == "False"

    def test_conditional_rendering_by_target(self):
        """Test conditional rendering based on target."""
        env = Environment()
        template = env.from_string("""
{% if request is hx_target("sidebar") %}
  Sidebar Content
{% elif request is hx_target("main") %}
  Main Content
{% else %}
  Unknown Target
{% end %}
        """.strip())

        # Sidebar target
        request = MockRequest({"HX-Target": "sidebar"})
        result = template.render(request=request)
        assert "Sidebar Content" in result

        # Main target
        request = MockRequest({"HX-Target": "main"})
        result = template.render(request=request)
        assert "Main Content" in result

        # No target
        request = MockRequest({})
        result = template.render(request=request)
        assert "Unknown Target" in result


class TestHXBoostedTest:
    """Test the 'is hx_boosted' test function."""

    def test_with_request_object_true(self):
        """Test 'is hx_boosted' with boosted request."""
        env = Environment()
        template = env.from_string("{{ request is hx_boosted }}")

        request = MockRequest({"HX-Boosted": "true"})
        result = template.render(request=request)

        assert result == "True"

    def test_with_request_object_false(self):
        """Test 'is hx_boosted' with non-boosted request."""
        env = Environment()
        template = env.from_string("{{ request is hx_boosted }}")

        request = MockRequest({})
        result = template.render(request=request)

        assert result == "False"

    def test_with_boolean_value(self):
        """Test 'is hx_boosted' with boolean."""
        env = Environment()
        template = env.from_string("{{ value is hx_boosted }}")

        result = template.render(value=True)
        assert result == "True"

        result = template.render(value=False)
        assert result == "False"

    def test_conditional_rendering(self):
        """Test conditional rendering based on boosted status."""
        env = Environment()
        template = env.from_string("""
{% if request is hx_boosted %}
  Enhanced Navigation
{% else %}
  Standard Navigation
{% end %}
        """.strip())

        # Boosted request
        request = MockRequest({"HX-Boosted": "true"})
        result = template.render(request=request)
        assert "Enhanced Navigation" in result

        # Regular request
        request = MockRequest({})
        result = template.render(request=request)
        assert "Standard Navigation" in result


class TestCombinedHTMXTests:
    """Test combining multiple HTMX tests."""

    def test_multiple_conditions(self):
        """Test using multiple HTMX tests together."""
        env = Environment()
        template = env.from_string("""
{% if request is hx_request and request is hx_target("sidebar") %}
  HTMX Sidebar Update
{% elif request is hx_request %}
  HTMX Request (other target)
{% else %}
  Full Page
{% end %}
        """.strip())

        # HTMX request targeting sidebar
        request = MockRequest({"HX-Request": "true", "HX-Target": "sidebar"})
        result = template.render(request=request)
        assert "HTMX Sidebar Update" in result

        # HTMX request targeting something else
        request = MockRequest({"HX-Request": "true", "HX-Target": "main"})
        result = template.render(request=request)
        assert "HTMX Request (other target)" in result

        # Regular request
        request = MockRequest({})
        result = template.render(request=request)
        assert "Full Page" in result

    def test_boosted_vs_regular_htmx(self):
        """Test distinguishing boosted from regular HTMX requests."""
        env = Environment()
        template = env.from_string("""
{% if request is hx_boosted %}
  Boosted Link/Form
{% elif request is hx_request %}
  HTMX Component
{% else %}
  Full Page Load
{% end %}
        """.strip())

        # Boosted request
        request = MockRequest({"HX-Request": "true", "HX-Boosted": "true"})
        result = template.render(request=request)
        assert "Boosted Link/Form" in result

        # Regular HTMX (not boosted)
        request = MockRequest({"HX-Request": "true"})
        result = template.render(request=request)
        assert "HTMX Component" in result

        # Standard request
        request = MockRequest({})
        result = template.render(request=request)
        assert "Full Page Load" in result


class TestBackwardsCompatibility:
    """Ensure HTMX tests don't break existing functionality."""

    def test_existing_tests_still_work(self):
        """Test that existing test functions are unaffected."""
        env = Environment()
        template = env.from_string("""
{{ 5 is odd }}
{{ "hello" is string }}
{{ items is defined }}
        """.strip())

        result = template.render(items=[1, 2, 3])
        lines = result.strip().split("\n")
        assert lines[0].strip() == "True"
        assert lines[1].strip() == "True"
        assert lines[2].strip() == "True"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
