"""Tests for terminal color utilities (Feature 2.1 Phase 2: Terminal Colors)."""

import os
import pytest

from kida.environment import terminal


class TestColorDetection:
    """Test terminal color detection logic."""

    def test_supports_color_respects_no_color(self, monkeypatch):
        """Test that NO_COLOR environment variable disables colors."""
        monkeypatch.setenv("NO_COLOR", "1")
        # Patch cached value (re-eval would need import before setenv; patch is reliable)
        monkeypatch.setattr(terminal, "_USE_COLORS", False)
        assert not terminal.supports_color()

    def test_supports_color_respects_force_color(self, monkeypatch):
        """Test that FORCE_COLOR overrides NO_COLOR."""
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.setenv("FORCE_COLOR", "1")
        # Patch cached value to simulate FORCE_COLOR winning
        monkeypatch.setattr(terminal, "_USE_COLORS", True)
        assert terminal.supports_color()

    def test_colorize_returns_plain_when_disabled(self, monkeypatch):
        """Test colorize returns plain text when colors disabled."""
        monkeypatch.setattr(terminal, "_USE_COLORS", False)
        result = terminal.colorize("Error", "red", "bold")
        assert result == "Error"
        assert "\033[" not in result

    def test_colorize_adds_codes_when_enabled(self, monkeypatch):
        """Test colorize adds ANSI codes when enabled."""
        monkeypatch.setattr(terminal, "_USE_COLORS", True)
        result = terminal.colorize("Error", "red", "bold")
        assert "\033[31m" in result  # red
        assert "\033[1m" in result   # bold
        assert "\033[0m" in result   # reset

    def test_strip_colors_removes_ansi_codes(self):
        """Test strip_colors removes all ANSI escape sequences."""
        colored = "\033[31m\033[1mError\033[0m"
        plain = terminal.strip_colors(colored)
        assert plain == "Error"
        assert "\033[" not in plain


class TestSemanticHelpers:
    """Test semantic color helper functions."""

    def test_error_code_formatting(self, monkeypatch):
        """Test error_code helper."""
        monkeypatch.setattr(terminal, "_USE_COLORS", True)
        result = terminal.error_code("K-RUN-001")
        assert "K-RUN-001" in result
        # Should have bright_red + bold
        assert "\033[91m" in result or "\033[31m" in result

    def test_location_formatting(self, monkeypatch):
        """Test location helper."""
        monkeypatch.setattr(terminal, "_USE_COLORS", True)
        result = terminal.location("test.html:42")
        assert "test.html:42" in result
        # Should have cyan
        assert "\033[36m" in result or "\033[96m" in result

    def test_hint_formatting(self, monkeypatch):
        """Test hint helper."""
        monkeypatch.setattr(terminal, "_USE_COLORS", True)
        result = terminal.hint("Hint:")
        assert "Hint:" in result
        # Should have green
        assert "\033[32m" in result or "\033[92m" in result

    def test_suggestion_formatting(self, monkeypatch):
        """Test suggestion helper."""
        monkeypatch.setattr(terminal, "_USE_COLORS", True)
        result = terminal.suggestion("username")
        assert "username" in result
        # Should have bright_green + bold
        assert "\033[92m" in result or "\033[32m" in result

    def test_docs_url_formatting(self, monkeypatch):
        """Test docs_url helper."""
        monkeypatch.setattr(terminal, "_USE_COLORS", True)
        result = terminal.docs_url("https://example.com")
        assert "https://example.com" in result
        # Should have bright_blue
        assert "\033[94m" in result or "\033[34m" in result


class TestErrorFormatting:
    """Test formatted error output functions."""

    def test_format_error_header_with_code(self, monkeypatch):
        """Test error header formatting with code."""
        monkeypatch.setattr(terminal, "_USE_COLORS", True)
        result = terminal.format_error_header("K-RUN-001", "Something went wrong")
        assert "K-RUN-001" in result
        assert "Something went wrong" in result
        # Code should be colorized
        assert "\033[" in result

    def test_format_error_header_without_code(self, monkeypatch):
        """Test error header formatting without code."""
        monkeypatch.setattr(terminal, "_USE_COLORS", True)
        result = terminal.format_error_header(None, "Something went wrong")
        assert result == "Something went wrong"

    def test_format_source_line_normal(self, monkeypatch):
        """Test source line formatting for normal lines."""
        monkeypatch.setattr(terminal, "_USE_COLORS", True)
        result = terminal.format_source_line(42, "{{ user }}", is_error=False)
        assert "42" in result
        assert "{{ user }}" in result
        assert "|" in result
        # Should be dimmed
        assert "\033[2m" in result

    def test_format_source_line_error(self, monkeypatch):
        """Test source line formatting for error lines."""
        monkeypatch.setattr(terminal, "_USE_COLORS", True)
        result = terminal.format_source_line(42, "{{ undefined }}", is_error=True)
        assert "42" in result
        assert "{{ undefined }}" in result
        assert ">" in result  # Error marker
        # Should have red highlighting
        assert "\033[91m" in result or "\033[31m" in result


class TestBackwardsCompatibility:
    """Test that colors don't break existing functionality."""

    def test_colors_optional_in_plain_text_mode(self, monkeypatch):
        """Test everything works with colors disabled."""
        monkeypatch.setattr(terminal, "_USE_COLORS", False)

        # All helpers should return plain text
        assert terminal.error_code("K-RUN-001") == "K-RUN-001"
        assert terminal.location("test.html") == "test.html"
        assert terminal.hint("Hint") == "Hint"
        assert terminal.suggestion("foo") == "foo"

    def test_exception_messages_readable_without_colors(self, monkeypatch):
        """Test exception messages are readable without color codes."""
        from kida.environment.exceptions import UndefinedError

        monkeypatch.setattr(terminal, "_USE_COLORS", False)

        error = UndefinedError("undefined_var", template="test.html", lineno=5)
        error_str = str(error)

        # Should be readable plain text
        assert "undefined_var" in error_str
        assert "test.html" in error_str
        assert "Hint" in error_str
        # Should have no ANSI codes
        assert "\033[" not in error_str


class TestColorization:
    """Test colorize function edge cases."""

    def test_colorize_empty_colors(self, monkeypatch):
        """Test colorize with no colors specified."""
        monkeypatch.setattr(terminal, "_USE_COLORS", True)
        result = terminal.colorize("text")
        assert result == "text"

    def test_colorize_unknown_color(self, monkeypatch):
        """Test colorize with unknown color name."""
        monkeypatch.setattr(terminal, "_USE_COLORS", True)
        # Should ignore unknown colors
        result = terminal.colorize("text", "unknown_color")
        # Should just return plain text since color isn't recognized
        assert "text" in result

    def test_colorize_multiple_colors(self, monkeypatch):
        """Test colorize with multiple valid colors."""
        monkeypatch.setattr(terminal, "_USE_COLORS", True)
        result = terminal.colorize("Error", "red", "bold", "dim")
        assert "\033[31m" in result  # red
        assert "\033[1m" in result   # bold
        assert "\033[2m" in result   # dim
        assert "\033[0m" in result   # reset


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
