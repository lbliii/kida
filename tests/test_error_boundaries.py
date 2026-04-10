"""Tests for error boundaries — {% try %}...{% fallback %}...{% end %} blocks."""

from kida import DictLoader, Environment


class TestBasicErrorBoundary:
    """Basic error boundary functionality."""

    def test_undefined_variable_caught(self, env: Environment) -> None:
        """Undefined variable in try body renders fallback."""
        tmpl = env.from_string("{% try %}{{ missing_var }}{% fallback %}safe{% end %}")
        assert tmpl.render() == "safe"

    def test_no_error_renders_body(self, env: Environment) -> None:
        """When no error occurs, body renders normally."""
        tmpl = env.from_string("{% try %}hello{% fallback %}fallback{% end %}")
        assert tmpl.render() == "hello"

    def test_body_with_context(self, env: Environment) -> None:
        """Body can use context variables normally."""
        tmpl = env.from_string("{% try %}{{ name }}{% fallback %}unknown{% end %}")
        assert tmpl.render(name="Alice") == "Alice"

    def test_partial_output_discarded(self, env: Environment) -> None:
        """Partial output from try body is discarded on error."""
        tmpl = env.from_string("{% try %}before{{ missing }}after{% fallback %}fallback{% end %}")
        # "before" was rendered but should be discarded because missing triggered an error
        assert tmpl.render() == "fallback"


class TestErrorAccess:
    """Error binding in fallback scope."""

    def test_error_message(self, env: Environment) -> None:
        """Error dict exposes message."""
        tmpl = env.from_string(
            "{% try %}{{ missing_var }}{% fallback err %}{{ err.message }}{% end %}"
        )
        result = tmpl.render()
        assert "missing_var" in result

    def test_error_type(self, env: Environment) -> None:
        """Error dict exposes exception type name."""
        tmpl = env.from_string(
            "{% try %}{{ missing_var }}{% fallback err %}{{ err.type }}{% end %}"
        )
        assert tmpl.render() == "UndefinedError"

    def test_error_without_binding(self, env: Environment) -> None:
        """Fallback without error binding still works."""
        tmpl = env.from_string("{% try %}{{ missing }}{% fallback %}<fallback>{% end %}")
        assert tmpl.render() == "<fallback>"


class TestNestedTry:
    """Nested error boundaries."""

    def test_inner_catches_first(self, env: Environment) -> None:
        """Inner try catches before outer."""
        tmpl = env.from_string(
            "{% try %}"
            "{% try %}{{ missing }}{% fallback %}inner{% end %}"
            "{% fallback %}outer{% end %}"
        )
        assert tmpl.render() == "inner"

    def test_inner_fallback_throws_outer_catches(self, env: Environment) -> None:
        """If inner fallback also fails, outer catches."""
        tmpl = env.from_string(
            "{% try %}"
            "{% try %}{{ missing1 }}{% fallback %}{{ missing2 }}{% end %}"
            "{% fallback %}outer{% end %}"
        )
        assert tmpl.render() == "outer"


class TestTryWithComponents:
    """Error boundaries with slots, includes, etc."""

    def test_try_around_def_call(self, env: Environment) -> None:
        """Error inside a component caught by surrounding try."""
        tmpl = env.from_string(
            "{% def broken() %}{{ missing }}{% end %}"
            "{% try %}{{ broken() }}{% fallback %}caught{% end %}"
        )
        assert tmpl.render() == "caught"

    def test_try_with_include(self) -> None:
        """Error in included template caught by try."""
        loader = DictLoader(
            {
                "bad.html": "{{ undefined_var }}",
                "page.html": "{% try %}{% include 'bad.html' %}{% fallback %}caught{% end %}",
            }
        )
        env = Environment(loader=loader)
        assert env.get_template("page.html").render() == "caught"

    def test_try_in_for_loop(self, env: Environment) -> None:
        """Try inside a for loop catches per-iteration."""
        tmpl = env.from_string(
            "{% for item in items %}{% try %}{{ item.force_name }}{% fallback %}?{% end %}{% end %}"
        )

        # force_name is a method that raises on items without a name
        class Named:
            def __init__(self, n: str) -> None:
                self.force_name = n

        class Broken:
            @property
            def force_name(self) -> str:
                raise ValueError("no name")

        items = [Named("a"), Broken(), Named("c")]
        assert tmpl.render(items=items) == "a?c"

    def test_try_with_filter_error(self, env: Environment) -> None:
        """Filter TypeError caught by try."""
        tmpl = env.from_string('{% try %}{{ 42 | join(",") }}{% fallback %}caught{% end %}')
        assert tmpl.render() == "caught"


class TestTryStreaming:
    """Error boundaries in streaming mode."""

    def test_stream_no_partial_leak(self) -> None:
        """Streaming mode does not leak partial try-body output."""
        env = Environment()
        tmpl = env.from_string("{% try %}before{{ missing }}after{% fallback %}fallback{% end %}")
        chunks = list(tmpl.render_stream())
        result = "".join(chunks)
        # "before" should not appear — body was buffered and discarded
        assert "before" not in result
        assert "fallback" in result
