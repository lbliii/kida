"""Tests for markdown filters."""

from __future__ import annotations

from kida.environment.filters._markdown import make_markdown_filters
from kida.utils.markdown_escape import Marked


class TestTextFilters:
    """Test text formatting filters."""

    def setup_method(self):
        self.filters = make_markdown_filters()

    def test_bold(self):
        result = self.filters["bold"]("hello")
        assert str(result) == "**hello**"
        assert isinstance(result, Marked)

    def test_italic(self):
        result = self.filters["italic"]("hello")
        assert str(result) == "*hello*"

    def test_code(self):
        result = self.filters["code"]("hello")
        assert str(result) == "`hello`"

    def test_code_with_backticks(self):
        result = self.filters["code"]("hello `world`")
        assert str(result) == "`` hello `world` ``"

    def test_strike(self):
        result = self.filters["strike"]("hello")
        assert str(result) == "~~hello~~"

    def test_bold_escapes_special_chars(self):
        result = self.filters["bold"]("*star*")
        assert str(result) == "**\\*star\\***"


class TestLinkFilter:
    """Test link filter."""

    def setup_method(self):
        self.filters = make_markdown_filters()

    def test_basic_link(self):
        result = self.filters["link"]("Click here", "https://example.com")
        assert str(result) == "[Click here](https://example.com)"

    def test_link_escapes_text(self):
        result = self.filters["link"]("[text]", "https://example.com")
        assert "\\[text\\]" in str(result)


class TestBadgeFilter:
    """Test badge filter."""

    def setup_method(self):
        self.filters = make_markdown_filters()

    def test_pass(self):
        assert str(self.filters["badge"]("pass")) == ":white_check_mark:"

    def test_fail(self):
        assert str(self.filters["badge"]("fail")) == ":x:"

    def test_warn(self):
        assert str(self.filters["badge"]("warn")) == ":warning:"

    def test_skip(self):
        assert str(self.filters["badge"]("skip")) == ":heavy_minus_sign:"

    def test_success(self):
        assert str(self.filters["badge"]("success")) == ":white_check_mark:"

    def test_unknown_status(self):
        result = self.filters["badge"]("custom")
        assert str(result) == ":custom:"

    def test_case_insensitive(self):
        assert str(self.filters["badge"]("PASS")) == ":white_check_mark:"


class TestTableFilter:
    """Test table filter."""

    def setup_method(self):
        self.filters = make_markdown_filters()

    def test_dict_data(self):
        data = [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}]
        result = str(self.filters["table"](data))
        assert "| name | age |" in result
        assert "| --- | --- |" in result
        assert "| Alice | 30 |" in result
        assert "| Bob | 25 |" in result

    def test_list_data(self):
        data = [["Alice", "30"], ["Bob", "25"]]
        result = str(self.filters["table"](data, headers=["Name", "Age"]))
        assert "| Name | Age |" in result
        assert "| Alice | 30 |" in result

    def test_empty_data(self):
        result = self.filters["table"]([])
        assert str(result) == ""

    def test_pipe_in_data(self):
        data = [{"cmd": "a | b"}]
        result = str(self.filters["table"](data))
        assert "a \\| b" in result

    def test_custom_headers(self):
        data = [{"a": "1", "b": "2"}]
        result = str(self.filters["table"](data, headers=["b", "a"]))
        lines = result.split("\n")
        assert lines[0] == "| b | a |"


class TestCodeblockFilter:
    """Test codeblock filter."""

    def setup_method(self):
        self.filters = make_markdown_filters()

    def test_basic(self):
        result = str(self.filters["codeblock"]("print('hi')"))
        assert result == "```\nprint('hi')\n```"

    def test_with_lang(self):
        result = str(self.filters["codeblock"]("x = 1", lang="python"))
        assert result == "```python\nx = 1\n```"


class TestDetailsFilter:
    """Test details filter."""

    def setup_method(self):
        self.filters = make_markdown_filters()

    def test_basic(self):
        result = str(self.filters["details"]("content", summary="Click"))
        assert "<details>" in result
        assert "<summary>Click</summary>" in result
        assert "content" in result
        assert "</details>" in result

    def test_default_summary(self):
        result = str(self.filters["details"]("content"))
        assert "<summary>Details</summary>" in result


class TestHeadingFilters:
    """Test heading filters."""

    def setup_method(self):
        self.filters = make_markdown_filters()

    def test_h1(self):
        assert str(self.filters["h1"]("Title")) == "# Title"

    def test_h2(self):
        assert str(self.filters["h2"]("Title")) == "## Title"

    def test_h3(self):
        assert str(self.filters["h3"]("Title")) == "### Title"

    def test_h4(self):
        assert str(self.filters["h4"]("Title")) == "#### Title"

    def test_heading_escapes(self):
        result = str(self.filters["h1"]("*bold*"))
        assert result == "# \\*bold\\*"
