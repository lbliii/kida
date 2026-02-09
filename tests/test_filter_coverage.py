"""Coverage tests for environment.filters.

Targets uncovered filter functions to improve coverage from 59% toward 85%+.
"""

from __future__ import annotations

from kida import Environment
from kida.environment.loaders import DictLoader


class TestStringFilters:
    """Test string manipulation filters."""

    def test_title(self) -> None:
        env = Environment()
        assert env.from_string("{{ 'hello world' | title }}").render() == "Hello World"

    def test_capitalize(self) -> None:
        env = Environment()
        assert env.from_string("{{ 'hello' | capitalize }}").render() == "Hello"

    def test_trim(self) -> None:
        env = Environment()
        assert env.from_string("{{ '  hello  ' | trim }}").render() == "hello"

    def test_truncate_short(self) -> None:
        env = Environment()
        r = env.from_string("{{ 'Hello World' | truncate(5) }}").render()
        assert len(r) <= 8  # 5 + "..."

    def test_truncate_no_cut(self) -> None:
        env = Environment()
        r = env.from_string("{{ 'Hi' | truncate(255) }}").render()
        assert r == "Hi"

    def test_replace(self) -> None:
        env = Environment()
        r = env.from_string("{{ 'hello' | replace('l', 'r') }}").render()
        assert r == "herro"

    def test_center(self) -> None:
        env = Environment()
        r = env.from_string("{{ 'hi' | center(10) }}").render()
        assert len(r) == 10
        assert "hi" in r

    def test_wordwrap(self) -> None:
        env = Environment()
        r = env.from_string("{{ text | wordwrap(10) }}").render(
            text="Hello World this is a long sentence"
        )
        assert "\n" in r

    def test_indent(self) -> None:
        env = Environment()
        r = env.from_string("{{ text | indent(4) }}").render(text="line1\nline2\nline3")
        assert "    line2" in r

    def test_indent_first(self) -> None:
        env = Environment()
        r = env.from_string("{{ text | indent(4, first=true) }}").render(text="line1\nline2")
        assert "    line1" in r

    def test_striptags(self) -> None:
        env = Environment()
        r = env.from_string("{{ '<b>bold</b>' | striptags }}").render()
        assert r == "bold"

    def test_string_filter(self) -> None:
        env = Environment()
        r = env.from_string("{{ 42 | string }}").render()
        assert r == "42"

    def test_urlencode(self) -> None:
        env = Environment()
        r = env.from_string("{{ 'hello world' | urlencode }}").render()
        assert "hello" in r
        assert " " not in r


class TestCollectionFilters:
    """Test collection manipulation filters."""

    def test_take(self) -> None:
        env = Environment()
        r = env.from_string("{{ items | take(2) }}").render(items=[1, 2, 3, 4])
        assert "1" in r
        assert "2" in r

    def test_take_none(self) -> None:
        env = Environment()
        r = env.from_string("{{ items | take(2) }}").render(items=None)
        assert r == "[]"

    def test_skip(self) -> None:
        env = Environment()
        r = env.from_string("{{ items | skip(2) }}").render(items=[1, 2, 3, 4])
        assert "3" in r
        assert "4" in r

    def test_skip_none(self) -> None:
        env = Environment()
        r = env.from_string("{{ items | skip(2) }}").render(items=None)
        assert r == "[]"

    def test_compact_truthy(self) -> None:
        env = Environment()
        r = env.from_string("{{ items | compact }}").render(items=[0, None, "", False, "value"])
        assert "value" in r

    def test_compact_none_only(self) -> None:
        env = Environment()
        r = env.from_string("{{ items | compact(truthy=false) }}").render(
            items=[0, None, "", False, "value"]
        )
        assert "0" in r
        assert "value" in r

    def test_compact_none_input(self) -> None:
        env = Environment()
        r = env.from_string("{{ items | compact }}").render(items=None)
        assert r == "[]"

    def test_map_attribute(self) -> None:
        env = Environment()
        r = env.from_string("{{ items | map(attribute='name') | join(', ') }}").render(
            items=[{"name": "a"}, {"name": "b"}]
        )
        assert "a" in r
        assert "b" in r

    def test_map_none(self) -> None:
        env = Environment()
        r = env.from_string("{{ items | map(attribute='x') }}").render(items=None)
        assert r == "[]"

    def test_select_truthy(self) -> None:
        env = Environment()
        r = env.from_string("{{ items | select | list }}").render(items=[0, 1, "", "a", None])
        assert "1" in r
        assert "a" in r

    def test_reject_truthy(self) -> None:
        env = Environment()
        r = env.from_string("{{ items | reject | list }}").render(items=[0, 1, "", "a", None])
        assert "0" in r

    def test_unique(self) -> None:
        env = Environment()
        r = env.from_string("{{ items | unique | join(',') }}").render(items=["a", "b", "a", "c"])
        assert r == "a,b,c"

    def test_unique_case_insensitive(self) -> None:
        env = Environment()
        r = env.from_string("{{ items | unique | join(',') }}").render(items=["a", "A", "b"])
        assert r == "a,b"

    def test_min_simple(self) -> None:
        env = Environment()
        r = env.from_string("{{ items | min }}").render(items=[3, 1, 2])
        assert r == "1"

    def test_max_simple(self) -> None:
        env = Environment()
        r = env.from_string("{{ items | max }}").render(items=[3, 1, 2])
        assert r == "3"

    def test_groupby(self) -> None:
        env = Environment()
        r = env.from_string(
            "{% for g in items | groupby('type') %}"
            "{{ g.grouper }}:{{ g.list | length }};"
            "{% end %}"
        ).render(items=[{"type": "a", "v": 1}, {"type": "b", "v": 2}, {"type": "a", "v": 3}])
        assert "a:2" in r
        assert "b:1" in r

    def test_pprint(self) -> None:
        env = Environment()
        r = env.from_string("{{ data | pprint }}").render(data={"a": 1})
        assert "a" in r

    def test_xmlattr(self) -> None:
        env = Environment()
        r = env.from_string("{{ attrs | xmlattr }}").render(attrs={"class": "btn", "id": "submit"})
        assert "class" in r
        assert "btn" in r

    def test_sort_simple(self) -> None:
        env = Environment()
        r = env.from_string("{{ items | sort | join(',') }}").render(items=[3, 1, 2])
        assert r == "1,2,3"

    def test_sort_reverse(self) -> None:
        env = Environment()
        r = env.from_string("{{ items | sort(reverse=true) | join(',') }}").render(items=[1, 2, 3])
        assert r == "3,2,1"

    def test_sort_attribute(self) -> None:
        env = Environment()
        r = env.from_string(
            "{% for item in items | sort(attribute='name') %}"
            "{{ item.name }};"
            "{% end %}"
        ).render(items=[{"name": "c"}, {"name": "a"}, {"name": "b"}])
        assert r == "a;b;c;"

    def test_sort_with_none_values(self) -> None:
        """Sort with None values sorts them last."""
        env = Environment()
        r = env.from_string(
            "{{ items | sort | join(',') }}"
        ).render(items=[3, 1, None, 2])
        # None sorts last
        assert r.startswith("1,2,3")

    def test_batch(self) -> None:
        env = Environment()
        r = env.from_string(
            "{% for b in items | batch(2) %}[{{ b | join(',') }}]{% end %}"
        ).render(items=[1, 2, 3, 4, 5])
        assert "[1,2]" in r
        assert "[3,4]" in r


class TestNumberFilters:
    """Test number and conversion filters."""

    def test_abs(self) -> None:
        env = Environment()
        assert env.from_string("{{ -5 | abs }}").render() == "5"

    def test_round(self) -> None:
        env = Environment()
        assert env.from_string("{{ 3.14159 | round(2) }}").render() == "3.14"

    def test_int_filter(self) -> None:
        env = Environment()
        assert env.from_string("{{ '42' | int }}").render() == "42"

    def test_float_filter(self) -> None:
        env = Environment()
        assert env.from_string("{{ '3.14' | float }}").render() == "3.14"

    def test_filesizeformat_bytes(self) -> None:
        env = Environment()
        r = env.from_string("{{ 100 | filesizeformat }}").render()
        assert "Bytes" in r

    def test_filesizeformat_kb(self) -> None:
        env = Environment()
        r = env.from_string("{{ 1500 | filesizeformat }}").render()
        assert "kB" in r

    def test_filesizeformat_mb(self) -> None:
        env = Environment()
        r = env.from_string("{{ 1500000 | filesizeformat }}").render()
        assert "MB" in r

    def test_filesizeformat_gb(self) -> None:
        env = Environment()
        r = env.from_string("{{ 1500000000 | filesizeformat }}").render()
        assert "GB" in r

    def test_filesizeformat_binary(self) -> None:
        env = Environment()
        r = env.from_string("{{ 1500 | filesizeformat(binary=true) }}").render()
        assert "KiB" in r


class TestValidationFilters:
    """Test validation and safety filters."""

    def test_require_passes(self) -> None:
        env = Environment()
        r = env.from_string("{{ value | require }}").render(value="hello")
        assert r == "hello"

    def test_require_fails(self) -> None:
        import pytest

        from kida.environment.exceptions import TemplateRuntimeError

        env = Environment()
        tmpl = env.from_string("{{ value | require }}")
        with pytest.raises(TemplateRuntimeError):
            tmpl.render(value=None)

    def test_require_custom_message(self) -> None:
        import pytest

        from kida.environment.exceptions import TemplateRuntimeError

        env = Environment()
        tmpl = env.from_string("{{ value | require('name is required') }}")
        with pytest.raises(TemplateRuntimeError):
            tmpl.render(value=None)


class TestImpureFilters:
    """Test non-deterministic filters."""

    def test_random(self) -> None:
        env = Environment()
        r = env.from_string("{{ items | random }}").render(items=[1, 2, 3])
        assert r in ("1", "2", "3")

    def test_shuffle(self) -> None:
        env = Environment()
        r = env.from_string("{{ items | shuffle | join(',') }}").render(items=[1, 2, 3])
        # All items present
        assert "1" in r
        assert "2" in r
        assert "3" in r


class TestJsonFilter:
    """Test JSON serialization."""

    def test_tojson(self) -> None:
        env = Environment()
        r = env.from_string("{{ data | tojson }}").render(data={"key": "value"})
        assert '"key"' in r
        assert '"value"' in r


class TestLoaderCoverage:
    """Test ChoiceLoader and PrefixLoader for coverage."""

    def test_choice_loader_fallback(self) -> None:
        from kida import ChoiceLoader

        primary = DictLoader({"a.html": "primary"})
        fallback = DictLoader({"a.html": "fallback", "b.html": "fallback-b"})
        loader = ChoiceLoader([primary, fallback])
        env = Environment(loader=loader)

        assert env.get_template("a.html").render() == "primary"
        assert env.get_template("b.html").render() == "fallback-b"

    def test_choice_loader_not_found(self) -> None:
        import pytest

        from kida import ChoiceLoader
        from kida.environment.exceptions import TemplateNotFoundError

        loader = ChoiceLoader([DictLoader({})])
        env = Environment(loader=loader)
        with pytest.raises(TemplateNotFoundError):
            env.get_template("missing.html")

    def test_choice_loader_list_templates(self) -> None:
        from kida import ChoiceLoader

        a = DictLoader({"x.html": "", "y.html": ""})
        b = DictLoader({"y.html": "", "z.html": ""})
        loader = ChoiceLoader([a, b])
        templates = loader.list_templates()
        assert templates == ["x.html", "y.html", "z.html"]

    def test_prefix_loader_basic(self) -> None:
        from kida import PrefixLoader

        loader = PrefixLoader({
            "app": DictLoader({"index.html": "app-index"}),
            "admin": DictLoader({"index.html": "admin-index"}),
        })
        env = Environment(loader=loader)
        assert env.get_template("app/index.html").render() == "app-index"
        assert env.get_template("admin/index.html").render() == "admin-index"

    def test_prefix_loader_not_found_prefix(self) -> None:
        import pytest

        from kida import PrefixLoader
        from kida.environment.exceptions import TemplateNotFoundError

        loader = PrefixLoader({"app": DictLoader({})})
        env = Environment(loader=loader)
        with pytest.raises(TemplateNotFoundError, match="no loader for prefix"):
            env.get_template("unknown/index.html")

    def test_prefix_loader_list_templates(self) -> None:
        from kida import PrefixLoader

        loader = PrefixLoader({
            "a": DictLoader({"x.html": ""}),
            "b": DictLoader({"y.html": ""}),
        })
        templates = loader.list_templates()
        assert "a/x.html" in templates
        assert "b/y.html" in templates


# ── classes filter ───────────────────────────────────────────────────────


class TestClassesFilter:
    """Test the classes filter that joins CSS class names."""

    def test_drops_falsy_values(self) -> None:
        env = Environment()
        t = env.from_string('{{ ["a", "", "b", none, "c"] | classes }}')
        assert t.render() == "a b c"

    def test_conditional_classes(self) -> None:
        env = Environment()
        t = env.from_string('{{ ["card", "active" if a, "done" if d] | classes }}')
        assert t.render(a=True, d=False) == "card active"
        assert t.render(a=True, d=True) == "card active done"
        assert t.render(a=False, d=False) == "card"

    def test_empty_list(self) -> None:
        env = Environment()
        t = env.from_string("{{ [] | classes }}")
        assert t.render() == ""

    def test_none_input(self) -> None:
        env = Environment()
        t = env.from_string("{{ x | classes }}")
        assert t.render(x=None) == ""

    def test_nested_list_flattened(self) -> None:
        env = Environment()
        from kida.environment.filters import _filter_classes

        assert _filter_classes([["a", "b"], "c"]) == "a b c"

    def test_drops_false_and_zero(self) -> None:
        from kida.environment.filters import _filter_classes

        assert _filter_classes(["a", False, 0, "b"]) == "a b"


# ── decimal filter ───────────────────────────────────────────────────────


class TestDecimalFilter:
    """Test the decimal filter for number formatting."""

    def test_default_two_places(self) -> None:
        env = Environment()
        assert env.from_string("{{ 3.1 | decimal }}").render() == "3.10"

    def test_custom_places(self) -> None:
        env = Environment()
        assert env.from_string("{{ 3.14159 | decimal(1) }}").render() == "3.1"
        assert env.from_string("{{ 3.14159 | decimal(3) }}").render() == "3.142"

    def test_zero_places(self) -> None:
        env = Environment()
        assert env.from_string("{{ 42.7 | decimal(0) }}").render() == "43"

    def test_integer_input(self) -> None:
        env = Environment()
        assert env.from_string("{{ 100 | decimal }}").render() == "100.00"

    def test_non_numeric_passthrough(self) -> None:
        from kida.environment.filters import _filter_decimal

        assert _filter_decimal("not a number") == "not a number"
