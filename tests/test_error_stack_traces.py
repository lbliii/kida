"""Tests for template stack traces (Feature 2.1: Rich Error Messages)."""

import pytest

from kida import Environment, FileSystemLoader
from kida.environment.exceptions import TemplateRuntimeError, UndefinedError


class TestTemplateStackTraces:
    """Test template stack traces in error messages."""

    def test_single_template_no_stack(self):
        """Test error in single template has no stack."""
        env = Environment()
        template = env.from_string("{{ undefined_var }}")

        with pytest.raises(UndefinedError) as exc_info:
            template.render()

        error = exc_info.value
        # Single template should have empty stack
        assert error.template_stack == []
        # Error message should not contain "Template stack:"
        assert "Template stack:" not in str(error)

    def test_nested_include_shows_stack(self, tmp_path):
        """Test error in nested include shows full stack."""
        # Create base template
        base = tmp_path / "base.html"
        base.write_text(
            """
<html>
{% include "nav.html" %}
</html>
        """.strip()
        )

        # Create nav template with error
        nav = tmp_path / "nav.html"
        nav.write_text(
            """
<nav>{{ undefined_var }}</nav>
        """.strip()
        )

        env = Environment(loader=FileSystemLoader(str(tmp_path)))
        template = env.get_template("base.html")

        with pytest.raises(UndefinedError) as exc_info:
            template.render()

        error = exc_info.value
        error_str = str(error)

        # Should show the stack
        assert "Template stack:" in error_str
        # Stack should show base.html called nav.html
        assert "base.html" in error_str

    def test_deeply_nested_includes_full_stack(self, tmp_path):
        """Test deeply nested includes show full call chain."""
        # page.html → header.html → nav.html (error here)
        page = tmp_path / "page.html"
        page.write_text(
            """
<html>
{% include "header.html" %}
</html>
        """.strip()
        )

        header = tmp_path / "header.html"
        header.write_text(
            """
<header>
{% include "nav.html" %}
</header>
        """.strip()
        )

        nav = tmp_path / "nav.html"
        nav.write_text(
            """
<nav>{{ missing_variable }}</nav>
        """.strip()
        )

        env = Environment(loader=FileSystemLoader(str(tmp_path)))
        template = env.get_template("page.html")

        with pytest.raises(UndefinedError) as exc_info:
            template.render()

        error = exc_info.value
        error_str = str(error)

        # Should show full stack
        assert "Template stack:" in error_str
        # Both parent templates should be in stack
        assert "page.html" in error_str
        assert "header.html" in error_str

    def test_format_compact_includes_stack(self, tmp_path):
        """Test format_compact() includes stack trace."""
        base = tmp_path / "base.html"
        base.write_text(
            """
{% include "partial.html" %}
        """.strip()
        )

        partial = tmp_path / "partial.html"
        partial.write_text(
            """
{{ undefined_var }}
        """.strip()
        )

        env = Environment(loader=FileSystemLoader(str(tmp_path)))
        template = env.get_template("base.html")

        with pytest.raises(UndefinedError) as exc_info:
            template.render()

        error = exc_info.value
        compact = error.format_compact()

        # format_compact should include stack
        assert "Template stack:" in compact
        assert "base.html" in compact

    def test_runtime_error_includes_stack(self, tmp_path):
        """Test error in nested include has stack trace."""
        base = tmp_path / "base.html"
        base.write_text(
            """
{% include "content.html" %}
        """.strip()
        )

        # Create content with undefined variable
        content = tmp_path / "content.html"
        content.write_text(
            """
{{ undefined_in_content }}
        """.strip()
        )

        env = Environment(loader=FileSystemLoader(str(tmp_path)))
        template = env.get_template("base.html")

        # Trigger undefined variable error
        with pytest.raises(UndefinedError) as exc_info:
            template.render()

        # Verify stack exists
        error = exc_info.value
        assert len(error.template_stack) > 0
        # Should show base.html in the stack
        stack_str = str(error)
        assert "Template stack:" in stack_str or "base.html" in error.template_stack[0][0]

    def test_stack_with_line_numbers(self, tmp_path):
        """Test stack includes line numbers of include calls."""
        base = tmp_path / "base.html"
        base.write_text(
            """
<html>
<head><title>Test</title></head>
<body>
{% include "content.html" %}
</body>
</html>
        """.strip()
        )

        content = tmp_path / "content.html"
        content.write_text(
            """
{{ undefined_var }}
        """.strip()
        )

        env = Environment(loader=FileSystemLoader(str(tmp_path)))
        template = env.get_template("base.html")

        with pytest.raises(UndefinedError) as exc_info:
            template.render()

        error = exc_info.value
        # Stack should have entries
        assert len(error.template_stack) > 0
        # Each entry should be (template_name, line_num)
        for entry in error.template_stack:
            assert isinstance(entry, tuple)
            assert len(entry) == 2
            template_name, line_num = entry
            assert isinstance(template_name, str)
            assert isinstance(line_num, int)
            assert line_num > 0

    def test_multiple_includes_same_level(self, tmp_path):
        """Test multiple includes at same level don't accumulate incorrectly."""
        base = tmp_path / "base.html"
        base.write_text(
            """
{% include "header.html" %}
{% include "footer.html" %}
        """.strip()
        )

        header = tmp_path / "header.html"
        header.write_text("<header>Header</header>")

        # Footer has the error
        footer = tmp_path / "footer.html"
        footer.write_text("{{ undefined_var }}")

        env = Environment(loader=FileSystemLoader(str(tmp_path)))
        template = env.get_template("base.html")

        with pytest.raises(UndefinedError) as exc_info:
            template.render()

        error = exc_info.value
        # Stack should show base → footer, not include header.html
        # (since header rendered successfully before footer)
        assert "base.html" in str(error)
        # header.html should NOT be in the stack since it didn't call footer
        stack_str = str(error.template_stack)
        assert "footer.html" not in stack_str or "header.html" not in stack_str


class TestStackFormatting:
    """Test template stack formatting helpers."""

    def test_format_template_stack_empty(self):
        """Test formatting empty stack."""
        from kida.environment.exceptions import format_template_stack

        result = format_template_stack([])
        assert result == ""

    def test_format_template_stack_single_entry(self):
        """Test formatting stack with single entry."""
        from kida.environment.exceptions import format_template_stack

        stack = [("base.html", 42)]
        result = format_template_stack(stack)

        assert "Template stack:" in result
        assert "base.html:42" in result
        assert "•" in result  # Bullet point

    def test_format_template_stack_multiple_entries(self):
        """Test formatting stack with multiple entries."""
        from kida.environment.exceptions import format_template_stack

        stack = [
            ("page.html", 15),
            ("layout.html", 8),
            ("nav.html", 3),
        ]
        result = format_template_stack(stack)

        assert "Template stack:" in result
        assert "page.html:15" in result
        assert "layout.html:8" in result
        assert "nav.html:3" in result
        # Should be in order
        lines = result.split("\n")
        assert any("page.html:15" in line for line in lines)
        assert any("layout.html:8" in line for line in lines)
        assert any("nav.html:3" in line for line in lines)


class TestBackwardsCompatibility:
    """Test that stack traces don't break existing error handling."""

    def test_errors_still_work_without_stack(self):
        """Test errors work without template_stack parameter."""
        from kida.environment.exceptions import UndefinedError

        # UndefinedError without stack
        error = UndefinedError("undefined_var", template="test.html", lineno=1)
        assert "undefined_var" in str(error)
        assert error.template_stack == []

        # TemplateRuntimeError without stack
        error = TemplateRuntimeError(
            "Something went wrong",
            template_name="test.html",
            lineno=5,
        )
        assert "Something went wrong" in str(error)
        assert error.template_stack == []

    def test_existing_error_catching_still_works(self):
        """Test existing try/except blocks still work."""
        env = Environment()
        template = env.from_string("{{ undefined }}")

        caught = False
        try:
            template.render()
        except UndefinedError:
            caught = True

        assert caught


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
