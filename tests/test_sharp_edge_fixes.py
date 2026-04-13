"""Tests for sharp edge fixes: strict undefined, render_with_blocks validation, etc."""

import pytest

from kida import Environment
from kida.exceptions import TemplateRuntimeError, UndefinedError

# =============================================================================
# Sprint 2: Strict Undefined Mode
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
