"""Test filter functionality in Kida template engine.

Based on Jinja2's test_filters.py.
Tests all built-in filters for correctness.
"""

import html
import json

import pytest

from kida import Environment, Markup
from kida.environment.filters._type_conversion import _filter_tojson


@pytest.fixture
def env():
    """Create a Kida environment for testing."""
    return Environment(autoescape=True)


@pytest.fixture
def env_no_autoescape():
    """Create a Kida environment without autoescape."""
    return Environment(autoescape=False)


class TestStringFilters:
    """String manipulation filters."""

    def test_upper(self, env):
        """upper filter."""
        tmpl = env.from_string('{{ "hello"|upper }}')
        assert tmpl.render() == "HELLO"

    def test_lower(self, env):
        """lower filter."""
        tmpl = env.from_string('{{ "HELLO"|lower }}')
        assert tmpl.render() == "hello"

    def test_capitalize(self, env):
        """capitalize filter."""
        tmpl = env.from_string('{{ "foo bar"|capitalize }}')
        assert tmpl.render() == "Foo bar"

    def test_title(self, env):
        """title filter."""
        tmpl = env.from_string('{{ "foo bar"|title }}')
        assert tmpl.render() == "Foo Bar"

    def test_trim(self, env):
        """trim filter."""
        tmpl = env.from_string('{{ "  hello  "|trim }}')
        assert tmpl.render() == "hello"

    def test_trim_with_chars(self, env):
        """trim filter with custom characters."""
        tmpl = env.from_string('{{ "..hello.."|trim(".") }}')
        assert tmpl.render() == "hello"

    def test_strip(self, env):
        """strip filter (alias for trim)."""
        tmpl = env.from_string('{{ "  hello  "|strip }}')
        assert tmpl.render() == "hello"

    def test_center(self, env):
        """center filter."""
        tmpl = env.from_string('{{ "foo"|center(9) }}')
        assert tmpl.render() == "   foo   "

    def test_replace(self, env):
        """replace filter."""
        tmpl = env.from_string('{{ "hello world"|replace("world", "there") }}')
        assert tmpl.render() == "hello there"

    def test_wordcount(self, env):
        """wordcount filter."""
        tmpl = env.from_string('{{ "hello world foo"|wordcount }}')
        assert tmpl.render() == "3"

    def test_truncate(self, env):
        """truncate filter."""
        tmpl = env.from_string('{{ "hello world this is long"|truncate(11) }}')
        result = tmpl.render()
        assert len(result) <= 14  # truncate may add ellipsis

    def test_striptags(self, env):
        """striptags filter."""
        tmpl = env.from_string('{{ "<p>hello <b>world</b></p>"|striptags }}')
        assert tmpl.render() == "hello world"

    def test_wordwrap(self, env):
        """wordwrap filter."""
        tmpl = env.from_string('{{ "hello world foo bar"|wordwrap(10) }}')
        result = tmpl.render()
        assert "\n" in result

    def test_indent(self, env):
        """indent filter."""
        tmpl = env.from_string('{{ "hello\nworld"|indent(4) }}')
        result = tmpl.render()
        assert "    world" in result


class TestStringFilterEdges:
    """Edge cases for slug, pluralize, format, wordcount, trim, replace."""

    # ─── slug ──────────────────────────────────────────────────
    def test_slug_basic(self, env):
        tmpl = env.from_string('{{ "Hello World" | slug }}')
        assert tmpl.render() == "hello-world"

    def test_slug_collapses_runs(self, env):
        tmpl = env.from_string('{{ "  foo   bar  " | slug }}')
        assert tmpl.render() == "foo-bar"

    def test_slug_strips_leading_trailing_hyphens(self, env):
        tmpl = env.from_string('{{ "!!!hello!!!" | slug }}')
        assert tmpl.render() == "hello"

    def test_slug_drops_non_ascii(self, env):
        tmpl = env.from_string('{{ "café résumé" | slug }}')
        assert tmpl.render() == "caf-r-sum"

    def test_slug_none(self, env):
        tmpl = env.from_string("{{ none | slug }}")
        assert tmpl.render() == ""

    def test_slug_numeric_preserved(self, env):
        tmpl = env.from_string('{{ "Item 42" | slug }}')
        assert tmpl.render() == "item-42"

    def test_slug_only_punctuation(self, env):
        tmpl = env.from_string('{{ "!!!" | slug }}')
        assert tmpl.render() == ""

    # ─── pluralize ────────────────────────────────────────────
    def test_pluralize_one(self, env):
        tmpl = env.from_string("{{ 1 | pluralize }}")
        assert tmpl.render() == ""

    def test_pluralize_zero_uses_plural(self, env):
        # Django convention: 0 → plural
        tmpl = env.from_string("{{ 0 | pluralize }}")
        assert tmpl.render() == "s"

    def test_pluralize_many(self, env):
        tmpl = env.from_string("{{ 5 | pluralize }}")
        assert tmpl.render() == "s"

    def test_pluralize_custom_suffix(self, env):
        tmpl = env.from_string("{{ 3 | pluralize('es') }}")
        assert tmpl.render() == "es"

    def test_pluralize_comma_split_one(self, env):
        # _string.py:172-174 — comma in suffix means singular,plural
        tmpl = env.from_string("{{ 1 | pluralize('y,ies') }}")
        assert tmpl.render() == "y"

    def test_pluralize_comma_split_many(self, env):
        tmpl = env.from_string("{{ 2 | pluralize('y,ies') }}")
        assert tmpl.render() == "ies"

    def test_pluralize_comma_split_strips_whitespace(self, env):
        # ' y , ies ' → singular 'y', plural 'ies' (split parts are .strip()ped)
        tmpl = env.from_string("{{ 1 | pluralize(' y , ies ') }}")
        assert tmpl.render() == "y"

    def test_pluralize_none_returns_suffix(self, env):
        tmpl = env.from_string("{{ none | pluralize }}")
        assert tmpl.render() == "s"

    def test_pluralize_string_numeric_coerced(self, env):
        tmpl = env.from_string("{{ '5' | pluralize }}")
        assert tmpl.render() == "s"

    def test_pluralize_non_numeric_raises(self, env):
        tmpl = env.from_string('{{ "abc" | pluralize }}')
        with pytest.raises(Exception, match="pluralize expects a number"):
            tmpl.render()

    # ─── format ───────────────────────────────────────────────
    def test_format_positional(self, env):
        tmpl = env.from_string('{{ "{} + {} = {}" | format(1, 2, 3) }}')
        assert tmpl.render() == "1 + 2 = 3"

    def test_format_keyword(self, env):
        tmpl = env.from_string('{{ "{name} is {age}" | format(name="Alice", age=30) }}')
        assert tmpl.render() == "Alice is 30"

    def test_format_numeric_spec(self, env):
        tmpl = env.from_string('{{ "{:.2f}" | format(3.14159) }}')
        assert tmpl.render() == "3.14"

    def test_format_no_args(self, env):
        # No placeholders, no args — just returns the string
        tmpl = env.from_string('{{ "plain text" | format }}')
        assert tmpl.render() == "plain text"

    def test_format_percent_with_args_raises(self, env):
        # %-style format passed with args is a likely bug — should raise
        tmpl = env.from_string('{{ "%.2f" | format(3.14) }}')
        with pytest.raises(Exception, match=r"format filter uses str\.format"):
            tmpl.render()

    def test_format_percent_no_args_passes(self, env):
        # %-style with no args — Python's str.format leaves it untouched
        tmpl = env.from_string('{{ "50%" | format }}')
        assert tmpl.render() == "50%"

    def test_format_braces_no_args(self, env):
        # has {} but no args — has_args is False, so no early error;
        # str.format raises IndexError, which Kida wraps as TemplateRuntimeError
        tmpl = env.from_string('{{ "{}" | format }}')
        with pytest.raises(Exception, match="Replacement index"):
            tmpl.render()

    # ─── wordcount ────────────────────────────────────────────
    def test_wordcount_empty(self, env):
        tmpl = env.from_string('{{ "" | wordcount }}')
        assert tmpl.render() == "0"

    def test_wordcount_whitespace_only(self, env):
        tmpl = env.from_string('{{ "   \t\n  " | wordcount }}')
        assert tmpl.render() == "0"

    def test_wordcount_multiple_spaces_collapsed(self, env):
        # str.split() with no args collapses runs of whitespace
        tmpl = env.from_string('{{ "a    b\t\tc" | wordcount }}')
        assert tmpl.render() == "3"

    def test_wordcount_non_string_coerced(self, env):
        tmpl = env.from_string("{{ 42 | wordcount }}")
        assert tmpl.render() == "1"


class TestEscapeFilters:
    """HTML escaping filters."""

    def test_escape(self, env):
        """escape filter."""
        tmpl = env.from_string("{{ text|escape }}")
        assert tmpl.render(text="<script>") == "&lt;script&gt;"

    def test_e(self, env):
        """e filter (alias for escape)."""
        tmpl = env.from_string("{{ text|e }}")
        assert tmpl.render(text="<b>") == "&lt;b&gt;"

    def test_safe(self, env):
        """safe filter prevents escaping."""
        tmpl = env.from_string("{{ text|safe }}")
        assert tmpl.render(text="<b>bold</b>") == "<b>bold</b>"

    def test_safe_preserves_markup(self, env):
        """safe filter with Markup input."""
        tmpl = env.from_string("{{ text|safe }}")
        result = tmpl.render(text=Markup("<b>already safe</b>"))
        assert result == "<b>already safe</b>"

    def test_safe_with_reason(self, env):
        """safe filter accepts optional reason for documentation."""
        tmpl = env.from_string('{{ html|safe(reason="sanitized by bleach") }}')
        result = tmpl.render(html="<b>trusted</b>")
        assert result == "<b>trusted</b>"

    def test_urlencode(self, env):
        """urlencode filter."""
        tmpl = env.from_string('{{ "hello world"|urlencode }}')
        assert tmpl.render() == "hello%20world"


class TestListFilters:
    """List manipulation filters."""

    def test_first(self, env):
        """first filter."""
        tmpl = env.from_string("{{ items|first }}")
        assert tmpl.render(items=[1, 2, 3]) == "1"

    def test_last(self, env):
        """last filter."""
        tmpl = env.from_string("{{ items|last }}")
        assert tmpl.render(items=[1, 2, 3]) == "3"

    def test_length(self, env):
        """length filter."""
        tmpl = env.from_string("{{ items|length }}")
        assert tmpl.render(items=[1, 2, 3]) == "3"

    def test_count(self, env):
        """count filter (alias for length)."""
        tmpl = env.from_string("{{ items|count }}")
        assert tmpl.render(items=[1, 2, 3]) == "3"

    def test_list(self, env):
        """list filter."""
        tmpl = env.from_string("{{ items|list }}")
        result = tmpl.render(items=range(3))
        assert "[0, 1, 2]" in result

    def test_reverse(self, env):
        """reverse filter."""
        tmpl = env.from_string("{{ items|reverse|list }}")
        result = tmpl.render(items=[1, 2, 3])
        assert "3" in result and result.index("3") < result.index("1")

    def test_sort(self, env):
        """sort filter."""
        tmpl = env.from_string("{{ items|sort|list }}")
        result = tmpl.render(items=[3, 1, 2])
        # Check order: 1 comes before 2, 2 before 3
        assert result.index("1") < result.index("2") < result.index("3")

    def test_join(self, env):
        """join filter."""
        tmpl = env.from_string("{{ items|join(', ') }}")
        assert tmpl.render(items=[1, 2, 3]) == "1, 2, 3"

    def test_join_default(self, env):
        """join filter with default separator."""
        tmpl = env.from_string("{{ items|join }}")
        assert tmpl.render(items=["a", "b", "c"]) == "abc"

    def test_unique(self, env):
        """unique filter."""
        tmpl = env.from_string("{{ items|unique|list }}")
        result = tmpl.render(items=[1, 2, 1, 3, 2])
        # Result should have unique values
        assert result.count("1") == 1
        assert result.count("2") == 1

    def test_batch(self, env):
        """batch filter."""
        tmpl = env.from_string("{{ foo|batch(3)|list }}")
        result = tmpl.render(foo=list(range(10)))
        assert "[[0, 1, 2]" in result

    def test_batch_with_fill(self, env):
        """batch filter with fill value."""
        tmpl = env.from_string("{{ foo|batch(3, 'X')|list }}")
        result = tmpl.render(foo=list(range(10)))
        assert "X" in result

    def test_slice(self, env):
        """slice filter."""
        tmpl = env.from_string("{{ foo|slice(3)|list }}")
        result = tmpl.render(foo=list(range(10)))
        # Slice divides into 3 roughly equal parts
        assert "[[" in result


class TestNumericFilters:
    """Numeric manipulation filters."""

    def test_int(self, env):
        """int filter."""
        tmpl = env.from_string("{{ '42'|int }}")
        assert tmpl.render() == "42"

    def test_int_default(self, env):
        """int filter with default on error."""
        tmpl = env.from_string("{{ 'abc'|int(0) }}")
        assert tmpl.render() == "0"

    def test_int_strict_mode(self, env):
        """int filter with strict mode raises error on conversion failure."""
        from kida.environment.exceptions import TemplateRuntimeError

        tmpl = env.from_string("{{ 'abc'|int(strict=true) }}")
        with pytest.raises(TemplateRuntimeError) as exc_info:
            tmpl.render()

        error_msg = str(exc_info.value)
        assert "Cannot convert" in error_msg
        assert "str to int" in error_msg
        assert "'abc'" in error_msg
        assert "suggestion" in error_msg.lower() or "Suggestion" in error_msg

    def test_float(self, env):
        """float filter."""
        tmpl = env.from_string("{{ '3.14'|float }}")
        assert tmpl.render() == "3.14"

    def test_float_default(self, env):
        """float filter with default on error."""
        tmpl = env.from_string("{{ 'abc'|float(0.0) }}")
        assert tmpl.render() == "0.0"

    def test_float_strict_mode(self, env):
        """float filter with strict mode raises error on conversion failure."""
        from kida.environment.exceptions import TemplateRuntimeError

        tmpl = env.from_string("{{ 'abc'|float(strict=true) }}")
        with pytest.raises(TemplateRuntimeError) as exc_info:
            tmpl.render()

        error_msg = str(exc_info.value)
        assert "Cannot convert" in error_msg
        assert "str to float" in error_msg
        assert "'abc'" in error_msg
        assert "suggestion" in error_msg.lower() or "Suggestion" in error_msg

    def test_abs(self, env):
        """abs filter."""
        tmpl = env.from_string("{{ -42|abs }}")
        assert tmpl.render() == "42"

    def test_round(self, env):
        """round filter."""
        tmpl = env.from_string("{{ 3.14159|round(2) }}")
        assert tmpl.render() == "3.14"

    def test_sum(self, env):
        """sum filter."""
        tmpl = env.from_string("{{ items|sum }}")
        assert tmpl.render(items=[1, 2, 3]) == "6"

    def test_min(self, env):
        """min filter."""
        tmpl = env.from_string("{{ items|min }}")
        assert tmpl.render(items=[3, 1, 2]) == "1"

    def test_max(self, env):
        """max filter."""
        tmpl = env.from_string("{{ items|max }}")
        assert tmpl.render(items=[3, 1, 2]) == "3"


class TestMappingFilters:
    """Dict and mapping filters."""

    def test_dictsort(self, env):
        """dictsort filter."""
        tmpl = env.from_string("{{ d|dictsort }}")
        result = tmpl.render(d={"b": 2, "a": 1, "c": 3})
        # Should be sorted by key
        assert result.index("a") < result.index("b") < result.index("c")

    def test_items(self, env):
        """items filter (returns list of key-value pairs)."""
        tmpl = env.from_string("{{ d.items()|list }}")
        result = tmpl.render(d={"a": 1})
        assert "a" in result and "1" in result


class TestAttributeFilters:
    """Attribute and mapping filters."""

    def test_attr(self, env):
        """attr filter."""

        class Obj:
            name = "test"

        tmpl = env.from_string("{{ obj|attr('name') }}")
        assert tmpl.render(obj=Obj()) == "test"

    def test_map(self, env):
        """map filter."""
        tmpl = env.from_string("{{ items|map('upper')|list }}")
        result = tmpl.render(items=["a", "b"])
        assert "A" in result and "B" in result

    def test_map_attribute(self, env):
        """map filter with attribute."""

        class Item:
            def __init__(self, name):
                self.name = name

        tmpl = env.from_string("{{ items|map(attribute='name')|list }}")
        result = tmpl.render(items=[Item("foo"), Item("bar")])
        assert "foo" in result and "bar" in result

    def test_select(self, env):
        """select filter."""
        tmpl = env.from_string("{{ items|select('odd')|list }}")
        result = tmpl.render(items=[1, 2, 3, 4, 5])
        assert "1" in result and "3" in result and "5" in result
        assert "2" not in result and "4" not in result

    def test_reject(self, env):
        """reject filter."""
        tmpl = env.from_string("{{ items|reject('odd')|list }}")
        result = tmpl.render(items=[1, 2, 3, 4, 5])
        assert "2" in result and "4" in result
        assert "1" not in result

    def test_selectattr(self, env):
        """selectattr filter."""

        class Item:
            def __init__(self, active):
                self.active = active

        tmpl = env.from_string("{{ items|selectattr('active')|list|length }}")
        result = tmpl.render(items=[Item(True), Item(False), Item(True)])
        assert result == "2"

    def test_rejectattr(self, env):
        """rejectattr filter."""

        class Item:
            def __init__(self, active):
                self.active = active

        tmpl = env.from_string("{{ items|rejectattr('active')|list|length }}")
        result = tmpl.render(items=[Item(True), Item(False), Item(True)])
        assert result == "1"

    def test_groupby(self, env):
        """groupby filter."""

        class Item:
            def __init__(self, category, name):
                self.category = category
                self.name = name

        items = [
            Item("fruit", "apple"),
            Item("fruit", "banana"),
            Item("vegetable", "carrot"),
        ]
        tmpl = env.from_string(
            "{% for group in items|groupby('category') %}"
            "{{ group.grouper }}: {{ group.list|map(attribute='name')|join(', ') }}; "
            "{% endfor %}"
        )
        result = tmpl.render(items=items)
        assert "fruit:" in result and "apple" in result


class TestDefaultFilter:
    """Test default filter variations."""

    def test_default_missing(self, env):
        """default filter with missing variable."""
        tmpl = env.from_string("{{ missing|default('fallback') }}")
        assert tmpl.render() == "fallback"

    def test_default_none(self, env):
        """default filter with None value."""
        tmpl = env.from_string("{{ value|default('fallback') }}")
        # Note: behavior with None may vary - Jinja2 keeps None unless boolean=True
        result = tmpl.render(value=None)
        # Kida may treat None as falsy for default
        assert result in ["fallback", "None"]

    def test_default_false(self, env):
        """default filter with False value."""
        tmpl = env.from_string("{{ value|default('fallback') }}")
        assert tmpl.render(value=False) == "False"

    def test_default_boolean_true(self, env):
        """default filter with boolean=True."""
        tmpl = env.from_string("{{ value|default('fallback', true) }}")
        assert tmpl.render(value=False) == "fallback"

    def test_d_alias(self, env):
        """d filter (alias for default)."""
        tmpl = env.from_string("{{ missing|d('fallback') }}")
        assert tmpl.render() == "fallback"


class TestJsonFilter:
    """Test tojson filter."""

    def test_tojson_dict(self, env):
        """tojson filter with dict."""
        tmpl = env.from_string("{{ data|tojson }}")
        result = tmpl.render(data={"key": "value"})
        assert '"key"' in result and '"value"' in result

    def test_tojson_list(self, env):
        """tojson filter with list."""
        tmpl = env.from_string("{{ data|tojson }}")
        result = tmpl.render(data=[1, 2, 3])
        assert "[1, 2, 3]" in result

    def test_tojson_no_double_escape(self, env):
        """tojson output should not be HTML-escaped."""
        tmpl = env.from_string("{{ data|tojson }}")
        result = tmpl.render(data={"key": "value"})
        # Should NOT contain &quot;
        assert "&quot;" not in result
        assert '"' in result

    def test_tojson_with_indent(self, env):
        """tojson filter with indent."""
        tmpl = env.from_string("{{ data|tojson(2) }}")
        result = tmpl.render(data={"a": 1})
        assert "\n" in result  # Indented JSON has newlines

    def test_tojson_attr_basic(self, env):
        """tojson(attr=true) entity-encodes quotes for HTML attributes."""
        tmpl = env.from_string("{{ data|tojson(attr=true) }}")
        result = tmpl.render(data={"key": "value"})
        assert result == "{&quot;key&quot;: &quot;value&quot;}"
        assert '"' not in result

    def test_tojson_attr_round_trip(self, env):
        """Decoded attr-mode output is valid JSON matching input."""
        data = {"rows": 6, "nested": {"a": 1}, "msg": 'He said "hello"'}
        tmpl = env.from_string("{{ data|tojson(attr=true) }}")
        result = tmpl.render(data=data)
        assert json.loads(html.unescape(result)) == data

    def test_tojson_attr_special_html_chars(self, env):
        """tojson(attr=true) encodes <, >, & in JSON text."""
        data = {"x": "a < b & c > d"}
        tmpl = env.from_string("{{ data|tojson(attr=true) }}")
        result = tmpl.render(data=data)
        assert "&lt;" in result and "&gt;" in result and "&amp;" in result
        assert json.loads(html.unescape(result)) == data

    def test_tojson_attr_none(self, env):
        """tojson(attr=true) with None serializes to null."""
        tmpl = env.from_string("{{ data|tojson(attr=true) }}")
        assert tmpl.render(data=None) == "null"

    def test_tojson_attr_with_indent(self, env):
        """tojson with indent and attr encodes quotes in indented JSON."""
        tmpl = env.from_string("{{ data|tojson(2, attr=true) }}")
        result = tmpl.render(data={"a": 1})
        assert "&quot;" in result
        assert "\n" in result
        assert json.loads(html.unescape(result)) == {"a": 1}

    def test_tojson_attr_markup_type(self, env):
        """tojson(attr=true) returns Markup."""
        out = _filter_tojson({"x": 1}, attr=True)
        assert isinstance(out, Markup)

    def test_tojson_indent_keyword_attr(self, env):
        """tojson(indent=2, attr=true) works."""
        tmpl = env.from_string("{{ data|tojson(indent=2, attr=true) }}")
        result = tmpl.render(data={"a": 1})
        assert json.loads(html.unescape(result)) == {"a": 1}

    # -- Edge cases --------------------------------------------------------

    def test_tojson_empty_dict(self, env):
        """tojson with empty dict."""
        tmpl = env.from_string("{{ data|tojson }}")
        assert tmpl.render(data={}) == "{}"

    def test_tojson_empty_list(self, env):
        """tojson with empty list."""
        tmpl = env.from_string("{{ data|tojson }}")
        assert tmpl.render(data=[]) == "[]"

    def test_tojson_bool(self, env):
        """tojson with booleans (no quotes to encode)."""
        tmpl = env.from_string("{{ data|tojson }}")
        assert tmpl.render(data=True) == "true"
        assert tmpl.render(data=False) == "false"

    def test_tojson_attr_bool(self, env):
        """tojson(attr=true) with booleans — no entities needed."""
        tmpl = env.from_string("{{ data|tojson(attr=true) }}")
        assert tmpl.render(data=True) == "true"

    def test_tojson_attr_number(self, env):
        """tojson(attr=true) with numbers — no entities needed."""
        tmpl = env.from_string("{{ data|tojson(attr=true) }}")
        assert tmpl.render(data=42) == "42"
        assert tmpl.render(data=3.14) == "3.14"

    def test_tojson_attr_empty_string(self, env):
        """tojson(attr=true) with empty string."""
        tmpl = env.from_string("{{ data|tojson(attr=true) }}")
        result = tmpl.render(data="")
        assert json.loads(html.unescape(result)) == ""

    def test_tojson_non_serializable_default_str(self, env):
        """tojson falls back to str() for non-JSON-serializable types."""
        from pathlib import PurePosixPath

        tmpl = env.from_string("{{ data|tojson }}")
        result = tmpl.render(data={"path": PurePosixPath("/tmp/foo")})
        parsed = json.loads(result)
        assert parsed == {"path": "/tmp/foo"}

    def test_tojson_attr_single_quotes_in_values(self, env):
        """tojson(attr=true) encodes single quotes (&#39;) for safety."""
        tmpl = env.from_string("{{ data|tojson(attr=true) }}")
        result = tmpl.render(data={"msg": "it's fine"})
        # Single quote must be encoded so it's safe in both ' and " attributes
        assert "'" not in result
        assert json.loads(html.unescape(result)) == {"msg": "it's fine"}

    def test_tojson_no_double_escape_with_autoescape(self, env):
        """tojson Markup output is not double-escaped by autoescape."""
        tmpl = env.from_string('<script type="application/json">{{ data|tojson }}</script>')
        result = tmpl.render(data={"key": "val"})
        assert "&quot;" not in result
        assert '"key"' in result

    def test_tojson_no_double_escape_without_autoescape(self, env_no_autoescape):
        """tojson behaves the same with autoescape off."""
        tmpl = env_no_autoescape.from_string("{{ data|tojson }}")
        result = tmpl.render(data={"key": "val"})
        assert '"key"' in result

    def test_tojson_attr_without_autoescape(self, env_no_autoescape):
        """tojson(attr=true) works correctly even with autoescape off."""
        tmpl = env_no_autoescape.from_string("{{ data|tojson(attr=true) }}")
        result = tmpl.render(data={"a": 1})
        assert "&quot;" in result
        assert json.loads(html.unescape(result)) == {"a": 1}

    # -- Security ----------------------------------------------------------

    def test_tojson_attr_xss_attribute_breakout(self, env):
        """tojson(attr=true) prevents attribute breakout via crafted values."""
        # An attacker might try to break out of an attribute with " onmouseover=...
        data = {"x": '" onmouseover="alert(1)'}
        tmpl = env.from_string("{{ data|tojson(attr=true) }}")
        result = tmpl.render(data=data)
        # No raw " should appear — all encoded as &quot;
        assert '"' not in result
        assert json.loads(html.unescape(result)) == data

    def test_tojson_attr_xss_html_injection(self, env):
        """tojson(attr=true) encodes angle brackets to prevent tag injection."""
        data = {"x": "<img src=x onerror=alert(1)>"}
        tmpl = env.from_string("{{ data|tojson(attr=true) }}")
        result = tmpl.render(data=data)
        assert "<img" not in result
        assert "&lt;img" in result
        assert json.loads(html.unescape(result)) == data

    def test_tojson_escapes_script_close_tag(self, env):
        """tojson escapes </script> to prevent XSS in <script> context."""
        data = {"x": "</script><script>alert(1)</script>"}
        tmpl = env.from_string("{{ data|tojson }}")
        result = tmpl.render(data=data)
        # "</" replaced with "\u003c/" so it can't close <script> tags
        assert "</script>" not in result
        assert "\\u003c/" in result
        # Round-trip: JSON.parse decodes \u003c back to <
        assert json.loads(result) == data

    def test_tojson_escapes_script_close_case_insensitive(self, env):
        """tojson escapes all </ sequences, not just </script>."""
        data = {"x": "</Script>", "y": "</style>"}
        tmpl = env.from_string("{{ data|tojson }}")
        result = tmpl.render(data=data)
        assert "</" not in result
        assert json.loads(result) == data

    def test_tojson_attr_deeply_nested_round_trip(self, env):
        """Round-trip with deeply nested structure."""
        data = {"a": {"b": {"c": {"d": [1, "two", None, True, {"e": "f&g"}]}}}}
        tmpl = env.from_string("{{ data|tojson(attr=true) }}")
        result = tmpl.render(data=data)
        assert json.loads(html.unescape(result)) == data

    def test_tojson_pipeline_operator(self, env):
        """tojson works with the |> pipeline operator."""
        tmpl = env.from_string("{{ data |> tojson }}")
        result = tmpl.render(data={"a": 1})
        assert '"a"' in result

    def test_tojson_pipeline_operator_attr(self, env):
        """tojson(attr=true) works with the |> pipeline operator."""
        tmpl = env.from_string("{{ data |> tojson(attr=true) }}")
        result = tmpl.render(data={"a": 1})
        assert "&quot;" in result
        assert json.loads(html.unescape(result)) == {"a": 1}


class TestFilterChaining:
    """Test chaining multiple filters."""

    def test_chain_basic(self, env):
        """Basic filter chain."""
        tmpl = env.from_string('{{ "  HELLO  "|trim|lower }}')
        assert tmpl.render() == "hello"

    def test_chain_multiple(self, env):
        """Multiple filter chain."""
        tmpl = env.from_string('{{ "  hello world  "|trim|title|replace(" ", "-") }}')
        assert tmpl.render() == "Hello-World"

    def test_chain_with_args(self, env):
        """Filter chain with arguments."""
        tmpl = env.from_string('{{ items|sort|join(", ") }}')
        assert tmpl.render(items=[3, 1, 2]) == "1, 2, 3"


class TestCustomFilters:
    """Test custom filter registration."""

    def test_custom_filter(self, env):
        """Register and use custom filter."""

        def double(value):
            return value * 2

        env.add_filter("double", double)
        tmpl = env.from_string("{{ 5|double }}")
        assert tmpl.render() == "10"

    def test_custom_filter_with_args(self, env):
        """Custom filter with arguments."""

        def multiply(value, factor):
            return value * factor

        env.add_filter("multiply", multiply)
        tmpl = env.from_string("{{ 5|multiply(3) }}")
        assert tmpl.render() == "15"

    def test_custom_filter_override(self, env):
        """Override built-in filter works with custom filter registry."""
        env_custom = Environment()

        def custom_upper(value):
            return value.upper() + "!"

        env_custom.add_filter("upper", custom_upper)
        tmpl = env_custom.from_string('{{ "hello"|upper }}')
        assert tmpl.render() == "HELLO!"
