"""Tests for kida.render_capture — render-time content capture."""

from __future__ import annotations

import pytest

from kida import DictLoader, Environment, captured_render, get_capture
from kida.render_capture import Fragment, RenderCapture, _compute_content_hash

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def capture_env():
    """Environment with capture enabled and a simple template set."""
    return Environment(
        loader=DictLoader(
            {
                "page.html": (
                    "{% block header %}Header{% end %}"
                    "{% block content %}Hello {{ name }}{% end %}"
                    "{% block footer %}Footer{% end %}"
                ),
                "single.html": "{% block main %}Only block{% end %}",
                "no_blocks.html": "Plain text, no blocks.",
                "nested.html": (
                    "{% block outer %}Before{% block inner %}Inner {{ x }}{% end %}After{% end %}"
                ),
            }
        ),
        enable_capture=True,
    )


@pytest.fixture
def no_capture_env():
    """Environment with capture disabled (default)."""
    return Environment(
        loader=DictLoader(
            {
                "page.html": (
                    "{% block header %}Header{% end %}"
                    "{% block content %}Hello {{ name }}{% end %}"
                    "{% block footer %}Footer{% end %}"
                ),
            }
        ),
    )


# ---------------------------------------------------------------------------
# RenderCapture / Fragment unit tests
# ---------------------------------------------------------------------------


class TestFragment:
    def test_fragment_frozen(self):
        f = Fragment(
            name="x", role="content", html="hi", content_hash="abc", depends_on=frozenset()
        )
        with pytest.raises(AttributeError):
            f.name = "y"

    def test_content_hash_deterministic(self):
        h1 = _compute_content_hash("Hello World")
        h2 = _compute_content_hash("Hello World")
        assert h1 == h2
        assert len(h1) == 16

    def test_content_hash_differs(self):
        h1 = _compute_content_hash("Hello")
        h2 = _compute_content_hash("World")
        assert h1 != h2


class TestRenderCaptureUnit:
    def test_record_all_blocks(self):
        cap = RenderCapture()
        cap._record("content", "<p>Hi</p>")
        cap._record("nav", "<nav>Nav</nav>")
        assert "content" in cap.blocks
        assert "nav" in cap.blocks
        assert cap.blocks["content"].html == "<p>Hi</p>"

    def test_record_filtered_blocks(self):
        cap = RenderCapture(_capture_blocks=frozenset({"content"}))
        cap._record("content", "<p>Hi</p>")
        cap._record("nav", "<nav>Nav</nav>")
        assert "content" in cap.blocks
        assert "nav" not in cap.blocks

    def test_record_sets_content_hash(self):
        cap = RenderCapture()
        cap._record("x", "test")
        assert cap.blocks["x"].content_hash == _compute_content_hash("test")


class TestCapturedRenderContextManager:
    def test_sets_and_resets_contextvar(self):
        assert get_capture() is None
        with captured_render() as cap:
            assert get_capture() is cap
        assert get_capture() is None

    def test_nested_captures(self):
        with captured_render() as outer:
            assert get_capture() is outer
            with captured_render() as inner:
                assert get_capture() is inner
            assert get_capture() is outer
        assert get_capture() is None


# ---------------------------------------------------------------------------
# Integration tests — capture with actual template rendering
# ---------------------------------------------------------------------------


class TestCaptureIntegration:
    def test_capture_all_blocks(self, capture_env):
        t = capture_env.get_template("page.html")
        with captured_render() as cap:
            html = t.render(name="World")

        assert html == "HeaderHello WorldFooter"
        assert sorted(cap.blocks.keys()) == ["content", "footer", "header"]
        assert cap.blocks["content"].html == "Hello World"
        assert cap.blocks["header"].html == "Header"
        assert cap.blocks["footer"].html == "Footer"

    def test_capture_filtered_blocks(self, capture_env):
        t = capture_env.get_template("page.html")
        with captured_render(capture_blocks=frozenset({"content"})) as cap:
            html = t.render(name="World")

        assert html == "HeaderHello WorldFooter"
        assert list(cap.blocks.keys()) == ["content"]
        assert cap.blocks["content"].html == "Hello World"

    def test_capture_context_keys(self, capture_env):
        t = capture_env.get_template("page.html")
        with captured_render(capture_context=frozenset({"name"})) as cap:
            t.render(name="Alice")

        assert cap.context_keys == {"name": "Alice"}

    def test_capture_context_missing_key_ignored(self, capture_env):
        t = capture_env.get_template("page.html")
        with captured_render(capture_context=frozenset({"name", "nonexistent"})) as cap:
            t.render(name="Bob")

        assert cap.context_keys == {"name": "Bob"}

    def test_capture_no_context_by_default(self, capture_env):
        t = capture_env.get_template("page.html")
        with captured_render() as cap:
            t.render(name="World")

        assert cap.context_keys == {}

    def test_template_name_set(self, capture_env):
        t = capture_env.get_template("page.html")
        with captured_render() as cap:
            t.render(name="World")

        assert cap.template_name == "page.html"

    def test_content_hash_stable(self, capture_env):
        t = capture_env.get_template("page.html")
        with captured_render() as cap1:
            t.render(name="World")
        with captured_render() as cap2:
            t.render(name="World")

        assert cap1.blocks["content"].content_hash == cap2.blocks["content"].content_hash

    def test_content_hash_changes_with_input(self, capture_env):
        t = capture_env.get_template("page.html")
        with captured_render() as cap1:
            t.render(name="Alice")
        with captured_render() as cap2:
            t.render(name="Bob")

        assert cap1.blocks["content"].content_hash != cap2.blocks["content"].content_hash

    def test_render_output_unchanged_with_capture(self, capture_env):
        """Capture must not alter the rendered HTML."""
        t = capture_env.get_template("page.html")
        html_without = t.render(name="World")
        with captured_render() as _:
            html_with = t.render(name="World")

        assert html_with == html_without

    def test_no_capture_active_no_error(self, capture_env):
        """Rendering without captured_render() must not error."""
        t = capture_env.get_template("page.html")
        html = t.render(name="World")
        assert html == "HeaderHello WorldFooter"

    def test_single_block_template(self, capture_env):
        t = capture_env.get_template("single.html")
        with captured_render() as cap:
            html = t.render()

        assert html == "Only block"
        assert cap.blocks["main"].html == "Only block"

    def test_no_blocks_template(self, capture_env):
        t = capture_env.get_template("no_blocks.html")
        with captured_render() as cap:
            html = t.render()

        assert html == "Plain text, no blocks."
        assert cap.blocks == {}


class TestCaptureDisabledEnv:
    """When enable_capture=False, captured_render() doesn't populate blocks."""

    def test_no_blocks_captured(self, no_capture_env):
        t = no_capture_env.get_template("page.html")
        with captured_render() as cap:
            html = t.render(name="World")

        assert html == "HeaderHello WorldFooter"
        # Blocks not captured because compiler didn't emit hooks
        assert cap.blocks == {}

    def test_context_still_captured(self, no_capture_env):
        """Context snapshot happens in _render_scaffold, not compiler.
        So it works even with enable_capture=False."""
        t = no_capture_env.get_template("page.html")
        with captured_render(capture_context=frozenset({"name"})) as cap:
            t.render(name="World")

        assert cap.context_keys == {"name": "World"}

    def test_template_name_still_set(self, no_capture_env):
        t = no_capture_env.get_template("page.html")
        with captured_render() as cap:
            t.render(name="World")

        assert cap.template_name == "page.html"


class TestCaptureWithProfiling:
    """Capture and profiling should work independently and together."""

    def test_capture_only(self):
        env = Environment(
            loader=DictLoader({"t.html": "{% block b %}Hi{% end %}"}),
            enable_capture=True,
            enable_profiling=False,
        )
        t = env.get_template("t.html")
        with captured_render() as cap:
            t.render()
        assert "b" in cap.blocks

    def test_profiling_only(self):
        from kida import profiled_render

        env = Environment(
            loader=DictLoader({"t.html": "{% block b %}Hi{% end %}"}),
            enable_capture=False,
            enable_profiling=True,
        )
        t = env.get_template("t.html")
        with profiled_render() as metrics:
            t.render()
        assert "b" in metrics.block_timings

    def test_both_active(self):
        from kida import profiled_render

        env = Environment(
            loader=DictLoader({"t.html": "{% block b %}Hi{% end %}"}),
            enable_capture=True,
            enable_profiling=True,
        )
        t = env.get_template("t.html")
        with profiled_render() as metrics, captured_render() as cap:
            t.render()

        assert "b" in cap.blocks
        assert cap.blocks["b"].html == "Hi"
        assert "b" in metrics.block_timings

    def test_neither_active(self):
        env = Environment(
            loader=DictLoader({"t.html": "{% block b %}Hi{% end %}"}),
            enable_capture=False,
            enable_profiling=False,
        )
        t = env.get_template("t.html")
        html = t.render()
        assert html == "Hi"


class TestCaptureFromString:
    """Templates created via from_string."""

    def test_from_string_capture(self):
        env = Environment(enable_capture=True)
        t = env.from_string("{% block greeting %}Hi {{ who }}{% end %}")
        with captured_render(capture_context=frozenset({"who"})) as cap:
            html = t.render(who="there")

        assert html == "Hi there"
        assert cap.blocks["greeting"].html == "Hi there"
        assert cap.context_keys == {"who": "there"}
