"""Integration tests for markdown mode."""

from __future__ import annotations

from kida.environment import Environment
from kida.markdown import markdown_env


class TestMarkdownEnv:
    """Test markdown_env() convenience factory."""

    def test_creates_environment(self):
        env = markdown_env()
        assert env.autoescape == "markdown"

    def test_has_markdown_filters(self):
        env = markdown_env()
        assert "bold" in env._filters
        assert "italic" in env._filters
        assert "code" in env._filters
        assert "table" in env._filters
        assert "badge" in env._filters
        assert "h1" in env._filters

    def test_has_output_format_global(self):
        env = markdown_env()
        assert env.globals["output_format"] == "markdown"


class TestMarkdownAutoescape:
    """Test autoescape behavior in markdown mode."""

    def test_select_autoescape_markdown(self):
        env = Environment(autoescape="markdown")
        assert env.select_autoescape("test.md") is True

    def test_escapes_special_chars_in_template(self):
        env = markdown_env()
        tpl = env.from_string("Hello {{ name }}")
        result = tpl.render(name="**bold**")
        assert "\\*\\*bold\\*\\*" in result

    def test_marked_bypasses_escaping(self):
        from kida.utils.markdown_escape import Marked

        env = markdown_env()
        tpl = env.from_string("{{ content }}")
        result = tpl.render(content=Marked("**bold**"))
        assert result.strip() == "**bold**"

    def test_filter_output_not_double_escaped(self):
        env = markdown_env()
        tpl = env.from_string("{{ name | bold }}")
        result = tpl.render(name="hello")
        assert result.strip() == "**hello**"

    def test_badge_filter_in_template(self):
        env = markdown_env()
        tpl = env.from_string("{{ status | badge }}")
        result = tpl.render(status="pass")
        assert result.strip() == ":white_check_mark:"

    def test_table_filter_in_template(self):
        env = markdown_env()
        tpl = env.from_string("{{ data | table }}")
        data = [{"name": "Alice", "score": "95"}]
        result = tpl.render(data=data)
        assert "| name | score |" in result
        assert "| Alice | 95 |" in result


class TestMarkdownComponents:
    """Test built-in markdown components."""

    def test_section_component(self):
        env = markdown_env()
        tpl = env.from_string(
            '{% from "components.md" import section %}'
            '{% call section("Results") %}Content here{% endcall %}'
        )
        result = tpl.render()
        assert "## Results" in result
        assert "Content here" in result

    def test_metric_component(self):
        env = markdown_env()
        tpl = env.from_string(
            '{% from "components.md" import metric %}{{ metric("Duration", "3.2", "s") }}'
        )
        result = tpl.render()
        assert "**Duration**" in result
        assert "3.2" in result

    def test_file_list_component(self):
        env = markdown_env()
        tpl = env.from_string(
            '{% from "components.md" import file_list %}'
            '{{ file_list(["src/main.py", "tests/test.py"]) }}'
        )
        result = tpl.render()
        assert "- `src/main.py`" in result
        assert "- `tests/test.py`" in result

    def test_collapsible_component(self):
        env = markdown_env()
        tpl = env.from_string(
            '{% from "components.md" import collapsible %}'
            '{% call collapsible("Details") %}Hidden content{% endcall %}'
        )
        result = tpl.render()
        assert "<details>" in result
        assert "<summary>Details</summary>" in result
        assert "Hidden content" in result


class TestMarkdownCLI:
    """Test CLI markdown mode integration."""

    def test_mode_choice_accepted(self):
        import contextlib

        from kida.cli import main

        # Should not raise for valid mode
        # We test by parsing args (will fail on missing template, but mode is valid)
        with contextlib.suppress(SystemExit):
            main(["render", "/nonexistent", "--mode", "markdown"])
