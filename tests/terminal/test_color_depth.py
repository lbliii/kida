"""Tests for color depth fallback in terminal filters."""

from kida.environment.filters._terminal import make_terminal_filters


class TestColorDepthFallback:
    def test_truecolor_emits_rgb(self):
        f = make_terminal_filters(color_depth="truecolor")
        result = str(f["fg"]("hi", "#ff0000"))
        assert "38;2;255;0;0" in result

    def test_256_emits_index(self):
        f = make_terminal_filters(color_depth="256")
        result = str(f["fg"]("hi", "#ff0000"))
        assert "38;5;" in result
        assert "38;2;" not in result

    def test_basic_emits_sgr(self):
        f = make_terminal_filters(color_depth="basic")
        result = str(f["fg"]("hi", "#ff0000"))
        # Should be a basic SGR code (30-37 or 90-97)
        assert "38;5;" not in result
        assert "38;2;" not in result
        assert "\033[" in result

    def test_none_strips_color(self):
        f = make_terminal_filters(color_depth="none")
        result = str(f["fg"]("hi", "#ff0000"))
        assert result == "hi"

    def test_bg_truecolor(self):
        f = make_terminal_filters(color_depth="truecolor")
        result = str(f["bg"]("hi", "#00ff00"))
        assert "48;2;0;255;0" in result

    def test_bg_256(self):
        f = make_terminal_filters(color_depth="256")
        result = str(f["bg"]("hi", "#00ff00"))
        assert "48;5;" in result

    def test_bg_none(self):
        f = make_terminal_filters(color_depth="none")
        result = str(f["bg"]("hi", "#00ff00"))
        assert result == "hi"

    def test_named_color_works_at_all_depths(self):
        for depth in ("truecolor", "256", "basic"):
            f = make_terminal_filters(color_depth=depth)
            result = str(f["fg"]("hi", "red"))
            assert "\033[31m" in result

    def test_256_index_fallback_to_basic(self):
        f = make_terminal_filters(color_depth="basic")
        result = str(f["fg"]("hi", 196))
        # Should map 256-index to basic SGR
        assert "\033[" in result
        assert "38;5;" not in result

    def test_backward_compat_bool_color(self):
        # color=True without color_depth should default to truecolor
        f = make_terminal_filters(color=True)
        result = str(f["fg"]("hi", "#ff0000"))
        assert "38;2;" in result

    def test_backward_compat_bool_no_color(self):
        f = make_terminal_filters(color=False)
        result = str(f["fg"]("hi", "#ff0000"))
        assert result == "hi"
