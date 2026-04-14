"""Tests for sharp edge fixes: strict undefined, render_with_blocks validation, etc."""

import warnings

import pytest

from kida import Environment
from kida.exceptions import CoercionWarning, TemplateRuntimeError, UndefinedError

# =============================================================================
# Sprint 1 (v0.6.x): Broken except X, Y: syntax — verify second type is caught
# =============================================================================


class TestExceptSyntaxFixes:
    """Verify the second exception type in except clauses is now caught."""

    def test_safe_getattr_catches_typeerror_on_subscript(self) -> None:
        """safe_getattr on non-subscriptable object returns '' not TypeError."""
        env = Environment()
        # An object that has no __getitem__ — subscript access raises TypeError.
        # Before the fix, only KeyError was caught; TypeError would propagate.

        class NoSubscript:
            pass

        tmpl = env.from_string("{{ obj.missing }}")
        result = tmpl.render(obj=NoSubscript())
        assert result == ""

    def test_collection_filter_first_catches_typeerror(self) -> None:
        """| first on a non-iterable returns None, not an unhandled error."""
        env = Environment()
        tmpl = env.from_string("{{ val | first }}")
        result = tmpl.render(val=42)
        assert result == "None"

    def test_collection_filter_length_catches_valueerror(self) -> None:
        """| length on a non-iterable returns 0."""
        env = Environment()
        tmpl = env.from_string("{{ val | length }}")
        result = tmpl.render(val=42)
        assert result == "0"

    def test_collection_filter_last_catches_typeerror(self) -> None:
        """| last on a non-iterable returns None, not an unhandled error."""
        env = Environment()
        tmpl = env.from_string("{{ val | last }}")
        result = tmpl.render(val=42)
        assert result == "None"

    def test_include_ignore_missing_catches_template_errors(self) -> None:
        """include with ignore_missing catches TemplateNotFoundError."""
        from kida import DictLoader

        env = Environment(loader=DictLoader({}))
        tmpl = env.from_string("{% include 'missing.html' ignore missing %}")
        result = tmpl.render()
        assert result == ""


# =============================================================================
# Sprint 2 (v0.6.x): CoercionWarning on collection filters
# =============================================================================


class TestCollectionFilterCoercionWarnings:
    """Collection filters emit CoercionWarning on non-iterable input."""

    def test_first_non_iterable_warns(self) -> None:
        from kida.environment.filters._collections import _filter_first

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _filter_first(42)
        coercion = [x for x in w if issubclass(x.category, CoercionWarning)]
        assert result is None
        assert len(coercion) == 1
        assert "first" in str(coercion[0].message)

    def test_last_non_iterable_warns(self) -> None:
        from kida.environment.filters._collections import _filter_last

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _filter_last(42)
        coercion = [x for x in w if issubclass(x.category, CoercionWarning)]
        assert result is None
        assert len(coercion) == 1
        assert "last" in str(coercion[0].message)

    def test_length_non_sized_warns(self) -> None:
        from kida.environment.filters._collections import _filter_length

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _filter_length(42)
        coercion = [x for x in w if issubclass(x.category, CoercionWarning)]
        assert result == 0
        assert len(coercion) == 1
        assert "length" in str(coercion[0].message)

    def test_take_non_iterable_warns(self) -> None:
        from kida.environment.filters._collections import _filter_take

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _filter_take(42, 3)
        coercion = [x for x in w if issubclass(x.category, CoercionWarning)]
        assert result == []
        assert len(coercion) == 1
        assert "take" in str(coercion[0].message)

    def test_skip_non_iterable_warns(self) -> None:
        from kida.environment.filters._collections import _filter_skip

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _filter_skip(42, 3)
        coercion = [x for x in w if issubclass(x.category, CoercionWarning)]
        assert result == []
        assert len(coercion) == 1
        assert "skip" in str(coercion[0].message)

    def test_compact_non_iterable_warns(self) -> None:
        from kida.environment.filters._collections import _filter_compact

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _filter_compact(42)
        coercion = [x for x in w if issubclass(x.category, CoercionWarning)]
        assert result == []
        assert len(coercion) == 1
        assert "compact" in str(coercion[0].message)

    def test_map_non_iterable_warns(self) -> None:
        from kida.environment.filters._collections import _filter_map

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _filter_map(42)
        coercion = [x for x in w if issubclass(x.category, CoercionWarning)]
        assert result == []
        assert len(coercion) == 1
        assert "map" in str(coercion[0].message)

    def test_valid_input_no_warning(self) -> None:
        """Filters on valid iterables should NOT emit warnings."""
        from kida.environment.filters._collections import (
            _filter_first,
            _filter_last,
            _filter_length,
        )

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _filter_first([1, 2, 3])
            _filter_last([1, 2, 3])
            _filter_length([1, 2, 3])
        coercion = [x for x in w if issubclass(x.category, CoercionWarning)]
        assert len(coercion) == 0


# =============================================================================
# Sprint 3 (v0.6.x): Harden number filters
# =============================================================================


class TestNumberFilterCoercionWarnings:
    """Number filters emit CoercionWarning on non-numeric input."""

    def test_round_non_numeric_warns(self) -> None:
        from kida.environment.filters._numbers import _filter_round

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _filter_round("abc")
        coercion = [x for x in w if issubclass(x.category, CoercionWarning)]
        assert result == 0.0
        assert len(coercion) == 1
        assert "round" in str(coercion[0].message)

    def test_round_strict_raises(self) -> None:
        from kida.environment.filters._numbers import _filter_round

        with pytest.raises(TemplateRuntimeError):
            _filter_round("abc", strict=True)

    def test_round_valid_no_warning(self) -> None:
        from kida.environment.filters._numbers import _filter_round

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _filter_round(3.14159, 2)
        coercion = [x for x in w if issubclass(x.category, CoercionWarning)]
        assert result == 3.14
        assert len(coercion) == 0

    def test_filesizeformat_non_numeric_warns(self) -> None:
        from kida.environment.filters._numbers import _filter_filesizeformat

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _filter_filesizeformat("not_a_number")
        coercion = [x for x in w if issubclass(x.category, CoercionWarning)]
        assert result == "0 Bytes"
        assert len(coercion) == 1
        assert "filesizeformat" in str(coercion[0].message)

    def test_min_none_attribute_warns(self) -> None:
        from kida.environment.filters._numbers import _filter_min

        class Item:
            def __init__(self, weight: int | None) -> None:
                self.weight = weight

        items = [Item(10), Item(None), Item(5)]
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _filter_min(items, attribute="weight")
        coercion = [x for x in w if issubclass(x.category, CoercionWarning)]
        assert len(coercion) == 1
        assert "1 item(s)" in str(coercion[0].message)
        assert result.weight is None  # None → 0, which is the min

    def test_max_none_attribute_warns(self) -> None:
        from kida.environment.filters._numbers import _filter_max

        class Item:
            def __init__(self, weight: int | None) -> None:
                self.weight = weight

        items = [Item(10), Item(None), Item(5)]
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _filter_max(items, attribute="weight")
        coercion = [x for x in w if issubclass(x.category, CoercionWarning)]
        assert len(coercion) == 1
        assert result.weight == 10

    def test_min_no_none_no_warning(self) -> None:
        from kida.environment.filters._numbers import _filter_min

        class Item:
            def __init__(self, weight: int) -> None:
                self.weight = weight

        items = [Item(10), Item(3), Item(5)]
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _filter_min(items, attribute="weight")
        coercion = [x for x in w if issubclass(x.category, CoercionWarning)]
        assert len(coercion) == 0


# =============================================================================
# Previous: Strict Undefined Mode
# =============================================================================


class TestStrictUndefined:
    """Environment(strict_undefined=True) raises on missing attribute access."""

    @pytest.fixture()
    def strict_env(self) -> Environment:
        return Environment(strict_undefined=True)

    @pytest.fixture()
    def lenient_env(self) -> Environment:
        return Environment(strict_undefined=False)

    def test_missing_attribute_raises(self, strict_env: Environment) -> None:
        """{{ obj.missing }} raises UndefinedError in strict mode."""
        tmpl = strict_env.from_string("{{ obj.typo }}")
        with pytest.raises(UndefinedError):
            tmpl.render(obj={"name": "Alice"})

    def test_existing_attribute_works(self, strict_env: Environment) -> None:
        """{{ obj.name }} works fine when attribute exists."""
        tmpl = strict_env.from_string("{{ obj.name }}")
        assert tmpl.render(obj={"name": "Alice"}) == "Alice"

    def test_none_attribute_renders_empty(self, strict_env: Environment) -> None:
        """{{ obj.name }} renders as '' when value is None (not missing)."""
        tmpl = strict_env.from_string("{{ obj.name }}")
        assert tmpl.render(obj={"name": None}) == ""

    def test_missing_nested_attribute_raises(self, strict_env: Environment) -> None:
        """{{ obj.a.b }} raises on the missing part."""
        tmpl = strict_env.from_string("{{ obj.missing.nested }}")
        with pytest.raises(UndefinedError):
            tmpl.render(obj={"name": "Alice"})

    def test_for_over_missing_raises(self, strict_env: Environment) -> None:
        """{% for x in obj.missing %} raises in strict mode."""
        tmpl = strict_env.from_string("{% for x in obj.typo %}{{ x }}{% end %}")
        with pytest.raises(UndefinedError):
            tmpl.render(obj={"items": [1, 2, 3]})

    def test_if_missing_raises(self, strict_env: Environment) -> None:
        """{% if obj.missing %} raises in strict mode."""
        tmpl = strict_env.from_string("{% if obj.typo %}yes{% end %}")
        with pytest.raises(UndefinedError):
            tmpl.render(obj={"flag": True})

    def test_default_filter_still_works(self, strict_env: Environment) -> None:
        """{{ obj.missing | default('fb') }} works even in strict mode."""
        tmpl = strict_env.from_string("{{ obj.missing | default('fallback') }}")
        # default filter catches UndefinedError internally
        result = tmpl.render(obj={})
        assert result == "fallback"

    def test_is_defined_still_works(self, strict_env: Environment) -> None:
        """{{ obj.missing is defined }} returns False in strict mode."""
        tmpl = strict_env.from_string("{{ obj.missing is defined }}")
        result = tmpl.render(obj={})
        assert result.strip().lower() == "false"

    def test_lenient_mode_unchanged(self, lenient_env: Environment) -> None:
        """Default mode still silently returns '' for missing attributes."""
        tmpl = lenient_env.from_string("{{ obj.typo }}")
        assert tmpl.render(obj={"name": "Alice"}) == ""

    def test_dict_method_access_works(self, strict_env: Environment) -> None:
        """Dict methods like .keys() still work in strict mode."""
        tmpl = strict_env.from_string("{{ obj.keys() | list }}")
        result = tmpl.render(obj={"a": 1})
        assert "a" in result


# =============================================================================
# Sprint 3: render_with_blocks Validation
# =============================================================================


class TestRenderWithBlocksValidation:
    """render_with_blocks raises on unknown block names."""

    def test_valid_block_name(self) -> None:
        env = Environment()
        tmpl = env.from_string("{% block content %}default{% end %}")
        result = tmpl.render_with_blocks({"content": "<p>Override</p>"})
        assert "<p>Override</p>" in result

    def test_unknown_block_name_raises(self) -> None:
        env = Environment()
        tmpl = env.from_string("{% block content %}default{% end %}")
        with pytest.raises(TemplateRuntimeError, match="unknown block"):
            tmpl.render_with_blocks({"contentt": "<p>Typo</p>"})

    def test_unknown_block_suggests_similar(self) -> None:
        env = Environment()
        tmpl = env.from_string("{% block content %}default{% end %}")
        with pytest.raises(TemplateRuntimeError, match="did you mean 'content'"):
            tmpl.render_with_blocks({"contentt": "<p>Typo</p>"})

    def test_empty_overrides_ok(self) -> None:
        env = Environment()
        tmpl = env.from_string("{% block content %}default{% end %}")
        result = tmpl.render_with_blocks({})
        assert "default" in result


# =============================================================================
# Sprint 4: _Undefined.get() Behavior
# =============================================================================


class TestUndefinedGet:
    """_Undefined.get() returns UNDEFINED (renders as '') when no default given."""

    def test_get_no_default_renders_empty(self) -> None:
        """UNDEFINED.get('key') renders as '' in template output."""
        env = Environment()
        tmpl = env.from_string("{{ obj.missing.get('key') }}")
        result = tmpl.render(obj={})
        assert result == ""

    def test_get_explicit_none_returns_none(self) -> None:
        """UNDEFINED.get('key', None) returns None (distinguishable from no-default)."""
        from kida.template.helpers import UNDEFINED

        result = UNDEFINED.get("key", None)
        assert result is None

    def test_get_with_fallback(self) -> None:
        """UNDEFINED.get('key', 'fallback') returns 'fallback'."""
        from kida.template.helpers import UNDEFINED

        assert UNDEFINED.get("key", "fallback") == "fallback"
