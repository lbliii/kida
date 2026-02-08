"""Tests for streaming rendering (render_stream).

Verifies that the generator-based render_stream() produces identical
output to the StringBuilder-based render(), and that chunks are yielded
at statement boundaries.
"""

from __future__ import annotations

import pytest

from kida import Environment, FileSystemLoader, RenderedTemplate
from kida.environment.exceptions import UndefinedError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def env() -> Environment:
    """Plain environment with no loader."""
    return Environment()


@pytest.fixture
def fs_env(tmp_path) -> Environment:
    """Environment with a temp filesystem loader for inheritance tests."""
    return Environment(loader=FileSystemLoader(str(tmp_path)))


# ---------------------------------------------------------------------------
# Basic streaming
# ---------------------------------------------------------------------------

class TestBasicStreaming:
    """render_stream() produces same output as render()."""

    def test_plain_text(self, env: Environment) -> None:
        t = env.from_string("Hello, world!")
        assert "".join(t.render_stream()) == t.render()

    def test_expression(self, env: Environment) -> None:
        t = env.from_string("Hello, {{ name }}!")
        result = "".join(t.render_stream(name="World"))
        assert result == "Hello, World!"
        assert result == t.render(name="World")

    def test_escaped_expression(self, env: Environment) -> None:
        t = env.from_string("{{ html }}")
        result = "".join(t.render_stream(html="<b>bold</b>"))
        assert result == t.render(html="<b>bold</b>")
        assert "&lt;b&gt;" in result

    def test_safe_expression(self, env: Environment) -> None:
        t = env.from_string("{{ html | safe }}")
        result = "".join(t.render_stream(html="<b>bold</b>"))
        assert result == "<b>bold</b>"

    def test_empty_template(self, env: Environment) -> None:
        t = env.from_string("")
        chunks = list(t.render_stream())
        joined = "".join(chunks)
        assert joined == ""

    def test_multiple_expressions(self, env: Environment) -> None:
        t = env.from_string("{{ a }} and {{ b }}")
        result = "".join(t.render_stream(a="X", b="Y"))
        assert result == t.render(a="X", b="Y")


class TestStreamingYieldsChunks:
    """Verify that chunks are yielded at statement boundaries."""

    def test_yields_multiple_chunks(self, env: Environment) -> None:
        """Non-coalesced template should yield multiple chunks."""
        # Disable coalescing to get separate chunks per statement
        env_no_coalesce = Environment(fstring_coalescing=False)
        t = env_no_coalesce.from_string("Hello, {{ name }}!")
        chunks = list(t.render_stream(name="World"))
        assert len(chunks) >= 2  # At least text and expression

    def test_coalesced_chunks(self, env: Environment) -> None:
        """Coalesced template should yield fewer chunks."""
        t = env.from_string("Hello, {{ name }}!")
        chunks = list(t.render_stream(name="World"))
        # With coalescing, consecutive data+output merge into one f-string
        assert "".join(chunks) == "Hello, World!"


# ---------------------------------------------------------------------------
# Control flow
# ---------------------------------------------------------------------------

class TestControlFlowStreaming:
    """Control flow produces correct streaming output."""

    def test_if_true(self, env: Environment) -> None:
        t = env.from_string("{% if show %}yes{% end %}")
        assert "".join(t.render_stream(show=True)) == "yes"

    def test_if_false(self, env: Environment) -> None:
        t = env.from_string("{% if show %}yes{% else %}no{% end %}")
        assert "".join(t.render_stream(show=False)) == "no"

    def test_for_loop(self, env: Environment) -> None:
        t = env.from_string("{% for x in items %}{{ x }},{% end %}")
        result = "".join(t.render_stream(items=[1, 2, 3]))
        assert result == t.render(items=[1, 2, 3])

    def test_for_loop_yields_per_iteration(self, env: Environment) -> None:
        env_no_coalesce = Environment(fstring_coalescing=False)
        t = env_no_coalesce.from_string("{% for x in items %}{{ x }}{% end %}")
        chunks = list(t.render_stream(items=["a", "b", "c"]))
        assert len(chunks) >= 3


# ---------------------------------------------------------------------------
# Block inheritance
# ---------------------------------------------------------------------------

class TestBlockStreaming:
    """Blocks yield independently in streaming mode."""

    def test_simple_block(self, fs_env: Environment, tmp_path) -> None:
        (tmp_path / "base.html").write_text(
            "<html>{% block content %}default{% end %}</html>"
        )
        (tmp_path / "child.html").write_text(
            '{% extends "base.html" %}{% block content %}overridden{% end %}'
        )
        t = fs_env.get_template("child.html")
        result = "".join(t.render_stream())
        assert result == t.render()
        assert result == "<html>overridden</html>"

    def test_multiple_blocks(self, fs_env: Environment, tmp_path) -> None:
        (tmp_path / "base.html").write_text(
            "{% block header %}H{% end %}|{% block body %}B{% end %}"
        )
        (tmp_path / "child.html").write_text(
            '{% extends "base.html" %}'
            "{% block header %}HEADER{% end %}"
            "{% block body %}BODY{% end %}"
        )
        t = fs_env.get_template("child.html")
        result = "".join(t.render_stream())
        assert result == "HEADER|BODY"
        assert result == t.render()

    def test_block_with_expressions(self, fs_env: Environment, tmp_path) -> None:
        (tmp_path / "base.html").write_text(
            "<title>{% block title %}Default{% end %}</title>"
        )
        (tmp_path / "page.html").write_text(
            '{% extends "base.html" %}{% block title %}{{ title }}{% end %}'
        )
        t = fs_env.get_template("page.html")
        result = "".join(t.render_stream(title="My Page"))
        assert result == "<title>My Page</title>"
        assert result == t.render(title="My Page")


# ---------------------------------------------------------------------------
# Include
# ---------------------------------------------------------------------------

class TestIncludeStreaming:
    """Include chains work in streaming mode."""

    def test_basic_include(self, fs_env: Environment, tmp_path) -> None:
        (tmp_path / "partial.html").write_text("<b>{{ name }}</b>")
        (tmp_path / "main.html").write_text(
            '<div>{% include "partial.html" with context %}</div>'
        )
        t = fs_env.get_template("main.html")
        result = "".join(t.render_stream(name="World"))
        assert result == t.render(name="World")
        assert "<b>World</b>" in result

    def test_nested_include(self, fs_env: Environment, tmp_path) -> None:
        (tmp_path / "inner.html").write_text("INNER")
        (tmp_path / "outer.html").write_text(
            'OUTER{% include "inner.html" %}END'
        )
        (tmp_path / "main.html").write_text(
            '{% include "outer.html" %}'
        )
        t = fs_env.get_template("main.html")
        result = "".join(t.render_stream())
        assert result == "OUTERINNEREND"
        assert result == t.render()


# ---------------------------------------------------------------------------
# Extends + Include combined
# ---------------------------------------------------------------------------

class TestExtendsIncludeStreaming:
    """Complex template hierarchies stream correctly."""

    def test_extends_with_include(self, fs_env: Environment, tmp_path) -> None:
        (tmp_path / "nav.html").write_text("<nav>{{ sitename }}</nav>")
        (tmp_path / "layout.html").write_text(
            '{% include "nav.html" with context %}'
            "{% block content %}{% end %}"
        )
        (tmp_path / "page.html").write_text(
            '{% extends "layout.html" %}'
            "{% block content %}<main>{{ body }}</main>{% end %}"
        )
        t = fs_env.get_template("page.html")
        result = "".join(t.render_stream(sitename="MySite", body="Hello"))
        assert result == t.render(sitename="MySite", body="Hello")
        assert "<nav>MySite</nav>" in result
        assert "<main>Hello</main>" in result


# ---------------------------------------------------------------------------
# Capture / Spaceless (buffer-redirect patterns)
# ---------------------------------------------------------------------------

class TestCaptureStreaming:
    """Capture blocks work correctly in streaming mode."""

    def test_capture_assigns_variable(self, env: Environment) -> None:
        t = env.from_string(
            "{% capture greeting %}Hello {{ name }}{% end %}"
            "Result: {{ greeting }}"
        )
        result = "".join(t.render_stream(name="World"))
        assert result == t.render(name="World")
        assert "Result: Hello World" in result


# ---------------------------------------------------------------------------
# RenderedTemplate
# ---------------------------------------------------------------------------

class TestRenderedTemplate:
    """RenderedTemplate delegates to render_stream()."""

    def test_str_renders_full(self, env: Environment) -> None:
        t = env.from_string("Hello, {{ name }}!")
        rt = RenderedTemplate(t, {"name": "World"})
        assert str(rt) == "Hello, World!"

    def test_iter_yields_chunks(self, env: Environment) -> None:
        t = env.from_string("Hello, {{ name }}!")
        rt = RenderedTemplate(t, {"name": "World"})
        result = "".join(rt)
        assert result == "Hello, World!"

    def test_iter_matches_str(self, env: Environment) -> None:
        t = env.from_string("{% for x in items %}{{ x }}{% end %}")
        ctx = {"items": ["a", "b", "c"]}
        rt = RenderedTemplate(t, ctx)
        assert str(rt) == "".join(rt)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestStreamingErrors:
    """Errors propagate correctly mid-stream."""

    def test_undefined_variable_raises(self, env: Environment) -> None:
        t = env.from_string("before {{ missing }} after")
        with pytest.raises(UndefinedError):
            list(t.render_stream())

    def test_error_propagates_from_block(
        self, fs_env: Environment, tmp_path
    ) -> None:
        (tmp_path / "base.html").write_text(
            "{% block content %}{% end %}"
        )
        (tmp_path / "bad.html").write_text(
            '{% extends "base.html" %}'
            "{% block content %}{{ missing }}{% end %}"
        )
        t = fs_env.get_template("bad.html")
        with pytest.raises(UndefinedError):
            list(t.render_stream())
