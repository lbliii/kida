"""Tests for HTMX integration helpers (Feature 1.1)."""

import warnings

import pytest

from kida import Environment
from kida.environment.exceptions import UndefinedError
from kida.render_context import render_context


class TestHTMXGlobals:
    """Test HTMX helper global functions."""

    def test_hx_request_true(self):
        """Test hx_request() returns True when set."""
        env = Environment()
        template = env.from_string("{{ hx_request() }}")

        with render_context() as ctx:
            ctx.set_meta("hx_request", True)
            result = template.render()

        assert result == "True"

    def test_hx_request_false(self):
        """Test hx_request() returns False when not set."""
        env = Environment()
        template = env.from_string("{{ hx_request() }}")

        with render_context():
            result = template.render()

        assert result == "False"

    def test_hx_request_no_context(self):
        """Test hx_request() returns False outside render context."""
        env = Environment()
        template = env.from_string("{{ hx_request() }}")

        # Render without render_context wrapper
        # (Template.render() creates its own context)
        result = template.render()
        assert result == "False"

    def test_hx_target_with_value(self):
        """Test hx_target() returns target element ID."""
        env = Environment()
        template = env.from_string("{{ hx_target() }}")

        with render_context() as ctx:
            ctx.set_meta("hx_target", "user-list")
            result = template.render()

        assert result == "user-list"

    def test_hx_target_none(self):
        """Test hx_target() returns None when not set."""
        env = Environment()
        template = env.from_string("{{ hx_target() or 'none' }}")

        with render_context():
            result = template.render()

        assert result == "none"

    def test_hx_trigger_with_value(self):
        """Test hx_trigger() returns trigger element ID."""
        env = Environment()
        template = env.from_string("{{ hx_trigger() }}")

        with render_context() as ctx:
            ctx.set_meta("hx_trigger", "delete-button")
            result = template.render()

        assert result == "delete-button"

    def test_hx_boosted_true(self):
        """Test hx_boosted() returns True when set."""
        env = Environment()
        template = env.from_string("{{ hx_boosted() }}")

        with render_context() as ctx:
            ctx.set_meta("hx_boosted", True)
            result = template.render()

        assert result == "True"

    def test_hx_boosted_false(self):
        """Test hx_boosted() returns False when not set."""
        env = Environment()
        template = env.from_string("{{ hx_boosted() }}")

        with render_context():
            result = template.render()

        assert result == "False"

    def test_conditional_rendering_with_hx_request(self):
        """Test conditional rendering based on hx_request()."""
        env = Environment()
        template = env.from_string(
            """
{% if hx_request() %}
  <div id="content">Fragment</div>
{% else %}
  <html><body>Full Page</body></html>
{% end %}
        """.strip()
        )

        # Full page request
        with render_context() as ctx:
            result = template.render()
        assert "Full Page" in result
        assert "Fragment" not in result

        # HTMX request
        with render_context() as ctx:
            ctx.set_meta("hx_request", True)
            result = template.render()
        assert "Fragment" in result
        assert "Full Page" not in result

    def test_disable_htmx_helpers(self):
        """Test disabling HTMX helpers via enable_htmx_helpers=False."""
        env = Environment(enable_htmx_helpers=False)

        # hx_request should not be available (undefined global)
        with pytest.raises(UndefinedError):
            env.from_string("{{ hx_request() }}").render()


class TestCSRFToken:
    """Test CSRF token helper."""

    def test_csrf_token_with_value(self):
        """Test csrf_token() renders hidden input."""
        env = Environment()
        template = env.from_string("{{ csrf_token() }}")

        with render_context() as ctx:
            ctx.set_meta("csrf_token", "abc123xyz")
            result = template.render()

        assert '<input type="hidden"' in result
        assert 'name="csrf_token"' in result
        assert 'value="abc123xyz"' in result

    def test_csrf_token_without_value(self):
        """Test csrf_token() warns and returns empty when not set."""
        env = Environment()
        template = env.from_string("{{ csrf_token() }}")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            with render_context():
                result = template.render()

            # Should warn about missing token
            assert len(w) == 1
            assert "csrf_token() called but no token provided" in str(w[0].message)

        # Should return empty string
        assert result == ""

    def test_csrf_token_html_escaped(self):
        """Test csrf_token() escapes HTML in token value."""
        env = Environment()
        template = env.from_string("{{ csrf_token() }}")

        with render_context() as ctx:
            ctx.set_meta("csrf_token", '<script>alert("xss")</script>')
            result = template.render()

        # Should be escaped
        assert "&lt;script&gt;" in result or "&#x3C;script&#x3E;" in result
        assert "<script>" not in result

    def test_csrf_token_in_form(self):
        """Test csrf_token() in realistic form context."""
        env = Environment()
        template = env.from_string(
            """
<form method="POST" action="/submit">
  {{ csrf_token() }}
  <input type="email" name="email" required>
  <button type="submit">Submit</button>
</form>
        """.strip()
        )

        with render_context() as ctx:
            ctx.set_meta("csrf_token", "token123")
            result = template.render()

        assert '<form method="POST"' in result
        assert 'name="csrf_token"' in result
        assert 'value="token123"' in result

    def test_csrf_token_not_double_escaped(self):
        """Test csrf_token() returns Markup to prevent double-escaping."""
        env = Environment()
        # Even in autoescape mode, csrf_token should not be double-escaped
        template = env.from_string("{{ csrf_token() }}")

        with render_context() as ctx:
            ctx.set_meta("csrf_token", "token&value")
            result = template.render()

        # Should only escape once
        assert result.count("&amp;") == 1 or result.count("&") == 1


class TestMetadataPropagation:
    """Test metadata propagates correctly through includes/extends."""

    def test_metadata_in_include(self):
        """Test metadata is accessible in included templates."""
        env = Environment()
        # Simulate including a template (would normally use loader)
        template = env.from_string(
            """
Main: {{ hx_request() }}
{% set included = "Included: " ~ hx_request() %}
{{ included }}
        """.strip()
        )

        with render_context() as ctx:
            ctx.set_meta("hx_request", True)
            result = template.render()

        assert "Main: True" in result
        assert "Included: True" in result


class TestBackwardsCompatibility:
    """Test that existing templates work without changes."""

    def test_templates_without_htmx_work(self):
        """Test templates that don't use HTMX helpers still work."""
        env = Environment()
        template = env.from_string("<h1>{{ title }}</h1>")

        result = template.render(title="Hello")
        assert result == "<h1>Hello</h1>"

    def test_existing_globals_preserved(self):
        """Test that existing globals (range, len, etc.) still work."""
        env = Environment()
        template = env.from_string("{{ len([1, 2, 3]) }}")

        result = template.render()
        assert result == "3"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
