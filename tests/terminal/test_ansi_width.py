"""Tests for kida.utils.ansi_width ANSI-aware string operations."""

from __future__ import annotations

from kida.utils.ansi_width import (
    ansi_center,
    ansi_ljust,
    ansi_rjust,
    ansi_truncate,
    ansi_wrap,
    visible_len,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RED = "\033[31m"
GREEN = "\033[32m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _red(text: str) -> str:
    return f"{RED}{text}{RESET}"


def _green(text: str) -> str:
    return f"{GREEN}{text}{RESET}"


def _bold(text: str) -> str:
    return f"{BOLD}{text}{RESET}"


# ===================================================================
# visible_len
# ===================================================================


class TestVisibleLen:
    """Tests for visible_len."""

    def test_plain_text(self) -> None:
        assert visible_len("hello") == 5
        assert visible_len("hello world") == 11

    def test_ansi_colored_text(self) -> None:
        assert visible_len("\033[31mhello\033[0m") == 5

    def test_multiple_ansi_codes(self) -> None:
        s = f"{RED}he{RESET}{GREEN}llo{RESET}"
        assert visible_len(s) == 5

    def test_empty_string(self) -> None:
        assert visible_len("") == 0

    def test_fast_path_no_escape(self) -> None:
        # No ESC byte means the fast path (plain len) is taken.
        plain = "abcdef"
        assert visible_len(plain) == len(plain)

    def test_only_ansi_codes(self) -> None:
        assert visible_len(f"{RED}{RESET}") == 0

    def test_nested_styles(self) -> None:
        s = f"{BOLD}{RED}hi{RESET}"
        assert visible_len(s) == 2


# ===================================================================
# ansi_ljust
# ===================================================================


class TestAnsiLjust:
    """Tests for ansi_ljust (left-justify / right-pad)."""

    def test_pads_right_with_spaces(self) -> None:
        assert ansi_ljust("hi", 5) == "hi   "

    def test_already_wide_enough(self) -> None:
        assert ansi_ljust("hello", 3) == "hello"
        assert ansi_ljust("hello", 5) == "hello"

    def test_custom_fillchar(self) -> None:
        assert ansi_ljust("hi", 6, fillchar=".") == "hi...."

    def test_ansi_text_pads_by_visible_width(self) -> None:
        colored = _red("hi")
        result = ansi_ljust(colored, 5)
        # Should have 3 padding spaces after the ANSI-wrapped text.
        assert result == colored + "   "
        assert visible_len(result) == 5

    def test_empty_string(self) -> None:
        assert ansi_ljust("", 4) == "    "


# ===================================================================
# ansi_rjust
# ===================================================================


class TestAnsiRjust:
    """Tests for ansi_rjust (right-justify / left-pad)."""

    def test_pads_left_with_spaces(self) -> None:
        assert ansi_rjust("hi", 5) == "   hi"

    def test_already_wide_enough(self) -> None:
        assert ansi_rjust("hello", 3) == "hello"
        assert ansi_rjust("hello", 5) == "hello"

    def test_ansi_text_pads_by_visible_width(self) -> None:
        colored = _green("ok")
        result = ansi_rjust(colored, 6)
        assert result == "    " + colored
        assert visible_len(result) == 6

    def test_custom_fillchar(self) -> None:
        assert ansi_rjust("x", 4, fillchar="-") == "---x"


# ===================================================================
# ansi_center
# ===================================================================


class TestAnsiCenter:
    """Tests for ansi_center."""

    def test_centers_with_equal_padding(self) -> None:
        result = ansi_center("hi", 6)
        assert result == "  hi  "

    def test_extra_padding_goes_right(self) -> None:
        # "hi" is 2 chars, width 5 -> 3 pad total -> 1 left, 2 right.
        result = ansi_center("hi", 5)
        assert result == " hi  "

    def test_already_wide_enough(self) -> None:
        assert ansi_center("hello", 3) == "hello"
        assert ansi_center("hello", 5) == "hello"

    def test_ansi_text(self) -> None:
        colored = _bold("ok")
        result = ansi_center(colored, 6)
        assert visible_len(result) == 6
        # 2 visible chars, 4 pad -> 2 left, 2 right.
        assert result == "  " + colored + "  "

    def test_custom_fillchar(self) -> None:
        assert ansi_center("x", 5, fillchar="*") == "**x**"


# ===================================================================
# ansi_truncate
# ===================================================================


class TestAnsiTruncate:
    """Tests for ansi_truncate."""

    def test_short_string_returns_as_is(self) -> None:
        assert ansi_truncate("hi", 10) == "hi"

    def test_truncates_with_ellipsis(self) -> None:
        result = ansi_truncate("hello world", 6)
        # 6 visible chars: 5 text + 1 ellipsis
        assert result == "hello\u2026"
        assert len(result) == 6

    def test_custom_suffix(self) -> None:
        result = ansi_truncate("hello world", 8, suffix="...")
        # 8 visible: 5 text + 3 dots
        assert result == "hello..."

    def test_width_leq_suffix_length(self) -> None:
        # Width 1 with default ellipsis (1 char) -> just the ellipsis truncated.
        result = ansi_truncate("hello world", 1)
        assert result == "\u2026"

        # Width 2 with "..." suffix -> "..."[:2] = ".."
        result = ansi_truncate("hello world", 2, suffix="...")
        assert result == ".."

    def test_width_zero(self) -> None:
        result = ansi_truncate("hello", 0)
        assert result == ""

    def test_ansi_text_truncation(self) -> None:
        colored = _red("hello world")
        result = ansi_truncate(colored, 6)
        # Should preserve ANSI codes before cutoff and append reset.
        assert visible_len(result) <= 6
        # Must end with reset code.
        assert result.endswith("\033[0m")
        # The visible portion should be 5 chars + ellipsis = 6.
        stripped = result.replace(RED, "").replace(RESET, "").replace("\033[0m", "")
        assert stripped == "hello\u2026"

    def test_fast_path_no_ansi(self) -> None:
        # Plain text that fits -> returned unchanged.
        assert ansi_truncate("abc", 5) == "abc"
        # Plain text truncated.
        assert ansi_truncate("abcdef", 4) == "abc\u2026"

    def test_ansi_text_fits(self) -> None:
        colored = _red("hi")
        assert ansi_truncate(colored, 10) == colored


# ===================================================================
# ansi_wrap
# ===================================================================


class TestAnsiWrap:
    """Tests for ansi_wrap."""

    def test_short_line_returns_as_is(self) -> None:
        assert ansi_wrap("hello", 20) == "hello"

    def test_wraps_at_word_boundaries(self) -> None:
        result = ansi_wrap("hello world foo", 11)
        assert result == "hello world\nfoo"

    def test_wraps_multiple_lines(self) -> None:
        result = ansi_wrap("one two three four", 9)
        lines = result.split("\n")
        for line in lines:
            assert visible_len(line) <= 9

    def test_ansi_styles_reapplied_after_break(self) -> None:
        # A colored phrase that must wrap.
        s = f"{RED}hello world{RESET}"
        result = ansi_wrap(s, 6)
        lines = result.split("\n")
        assert len(lines) >= 2
        # The second line should start with the RED code re-applied.
        assert RED in lines[1]

    def test_long_word_force_breaks(self) -> None:
        # Force-break only triggers in the ANSI path (_force_break_word).
        # Wrap a colored word longer than the width.
        long_word = f"{RED}abcdefghij{RESET}"
        result = ansi_wrap(long_word, 4)
        lines = result.split("\n")
        assert len(lines) >= 3
        for line in lines:
            assert visible_len(line) <= 4

    def test_plain_text_fast_path(self) -> None:
        # No ESC byte -> takes _wrap_plain fast path.
        result = ansi_wrap("aa bb cc dd", 5)
        lines = result.split("\n")
        for line in lines:
            assert len(line) <= 5

    def test_exact_width_no_wrap(self) -> None:
        assert ansi_wrap("abcde", 5) == "abcde"

    def test_single_space_between_words(self) -> None:
        result = ansi_wrap("a b c d e f", 3)
        lines = result.split("\n")
        for line in lines:
            assert visible_len(line) <= 3
