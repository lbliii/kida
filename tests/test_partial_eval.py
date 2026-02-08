"""Tests for compile-time partial evaluation.

Verifies that the PartialEvaluator correctly replaces static expressions
with constants in the template AST, and that the rendered output is
identical whether using partial evaluation or runtime context.

"""

from dataclasses import dataclass

from kida import Environment


@dataclass(frozen=True, slots=True)
class FakeSite:
    title: str
    url: str
    nav: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FakePage:
    title: str
    slug: str


def _env() -> Environment:
    return Environment(autoescape=False)


class TestBasicPartialEvaluation:
    """Static context values are folded into constants at compile time."""

    def test_simple_variable(self):
        env = _env()
        tmpl = env.from_string(
            "Hello, {{ name }}!",
            static_context={"name": "World"},
        )
        assert tmpl.render() == "Hello, World!"

    def test_attribute_access(self):
        env = _env()
        site = FakeSite(title="My Blog", url="https://example.com", nav=("Home", "About"))
        tmpl = env.from_string(
            "<title>{{ site.title }}</title>",
            static_context={"site": site},
        )
        assert tmpl.render() == "<title>My Blog</title>"

    def test_dict_access(self):
        env = _env()
        tmpl = env.from_string(
            "{{ config.theme }}",
            static_context={"config": {"theme": "dark"}},
        )
        assert tmpl.render() == "dark"

    def test_nested_access(self):
        env = _env()
        ctx = {"site": {"meta": {"author": "Jane"}}}
        tmpl = env.from_string(
            "By {{ site.meta.author }}",
            static_context=ctx,
        )
        assert tmpl.render() == "By Jane"

    def test_subscript_access(self):
        env = _env()
        tmpl = env.from_string(
            '{{ items["key"] }}',
            static_context={"items": {"key": "value"}},
        )
        assert tmpl.render() == "value"

    def test_integer_constant(self):
        env = _env()
        tmpl = env.from_string(
            "Count: {{ count }}",
            static_context={"count": 42},
        )
        assert tmpl.render() == "Count: 42"

    def test_none_value(self):
        env = _env()
        tmpl = env.from_string(
            "Value: {{ val }}",
            static_context={"val": None},
        )
        assert tmpl.render() == "Value: "


class TestMixedContext:
    """Static and runtime values coexist correctly."""

    def test_static_and_dynamic(self):
        env = _env()
        tmpl = env.from_string(
            "{{ site.title }} - {{ page.title }}",
            static_context={"site": FakeSite(title="Blog", url="", nav=())},
        )
        page = FakePage(title="Hello World", slug="hello")
        result = tmpl.render(page=page)
        assert result == "Blog - Hello World"

    def test_static_in_attribute(self):
        env = _env()
        tmpl = env.from_string(
            '<a href="{{ site.url }}">{{ page.title }}</a>',
            static_context={"site": FakeSite(title="Blog", url="https://example.com", nav=())},
        )
        result = tmpl.render(page=FakePage(title="Index", slug="index"))
        assert result == '<a href="https://example.com">Index</a>'


class TestExpressionEvaluation:
    """Compile-time evaluation of expression operators."""

    def test_string_concatenation(self):
        env = _env()
        tmpl = env.from_string(
            "{{ prefix ~ suffix }}",
            static_context={"prefix": "hello", "suffix": "world"},
        )
        assert tmpl.render() == "helloworld"

    def test_arithmetic(self):
        env = _env()
        tmpl = env.from_string(
            "{{ a + b }}",
            static_context={"a": 10, "b": 20},
        )
        assert tmpl.render() == "30"

    def test_comparison(self):
        env = _env()
        tmpl = env.from_string(
            "{% if threshold > 5 %}high{% end %}",
            static_context={"threshold": 10},
        )
        assert tmpl.render() == "high"

    def test_boolean_and(self):
        env = _env()
        tmpl = env.from_string(
            "{% if a and b %}yes{% end %}",
            static_context={"a": True, "b": True},
        )
        assert tmpl.render() == "yes"

    def test_boolean_or_short_circuit(self):
        env = _env()
        tmpl = env.from_string(
            "{% if a or b %}yes{% else %}no{% end %}",
            static_context={"a": False, "b": False},
        )
        assert tmpl.render() == "no"

    def test_negation(self):
        env = _env()
        tmpl = env.from_string(
            "{% if not flag %}off{% end %}",
            static_context={"flag": False},
        )
        assert tmpl.render() == "off"

    def test_ternary(self):
        env = _env()
        tmpl = env.from_string(
            "{{ 'yes' if enabled else 'no' }}",
            static_context={"enabled": True},
        )
        assert tmpl.render() == "yes"


class TestBranchElimination:
    """Static If/elif/else branches are eliminated at compile time."""

    def test_true_branch(self):
        env = _env()
        tmpl = env.from_string(
            "{% if show_nav %}NAV{% else %}HIDDEN{% end %}",
            static_context={"show_nav": True},
        )
        assert tmpl.render() == "NAV"

    def test_false_branch(self):
        env = _env()
        tmpl = env.from_string(
            "{% if show_nav %}NAV{% else %}HIDDEN{% end %}",
            static_context={"show_nav": False},
        )
        assert tmpl.render() == "HIDDEN"

    def test_false_no_else(self):
        env = _env()
        tmpl = env.from_string(
            "before{% if debug %} DEBUG{% end %} after",
            static_context={"debug": False},
        )
        assert tmpl.render() == "before after"

    def test_elif_branch(self):
        env = _env()
        tmpl = env.from_string(
            "{% if mode == 'a' %}A{% elif mode == 'b' %}B{% else %}C{% end %}",
            static_context={"mode": "b"},
        )
        assert tmpl.render() == "B"


class TestBlockHandling:
    """Partial evaluation works inside template blocks."""

    def test_static_in_block(self):
        env = _env()
        tmpl = env.from_string(
            "{% block title %}{{ site.title }}{% end %}",
            static_context={"site": FakeSite(title="Blog", url="", nav=())},
        )
        assert tmpl.render() == "Blog"


class TestForLoopRecursion:
    """Partial evaluation recurses into for loop bodies."""

    def test_static_inside_loop(self):
        env = _env()
        tmpl = env.from_string(
            "{% for item in items %}{{ site.title }}: {{ item }}; {% end %}",
            static_context={"site": FakeSite(title="Blog", url="", nav=())},
        )
        result = tmpl.render(items=["a", "b"])
        assert result == "Blog: a; Blog: b; "


class TestNoStaticContext:
    """Without static_context, templates work normally."""

    def test_no_static_context(self):
        env = _env()
        tmpl = env.from_string("{{ name }}")
        assert tmpl.render(name="World") == "World"

    def test_empty_static_context(self):
        env = _env()
        tmpl = env.from_string("{{ name }}", static_context={})
        assert tmpl.render(name="World") == "World"


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_missing_attribute_stays_dynamic(self):
        """If static context doesn't have the attr, expression stays dynamic."""
        env = _env()
        tmpl = env.from_string(
            "{{ site.title }} {{ page.title }}",
            static_context={"site": FakeSite(title="Blog", url="", nav=())},
        )
        # page is dynamic, site.title is static
        result = tmpl.render(page=FakePage(title="Post", slug="post"))
        assert result == "Blog Post"

    def test_data_merging(self):
        """Adjacent static Data nodes are merged."""
        env = _env()
        tmpl = env.from_string(
            "{{ a }}{{ b }}{{ c }}",
            static_context={"a": "x", "b": "y", "c": "z"},
        )
        assert tmpl.render() == "xyz"

    def test_numeric_types_preserved(self):
        env = _env()
        tmpl = env.from_string(
            "{{ x * 2 }}",
            static_context={"x": 21},
        )
        assert tmpl.render() == "42"
