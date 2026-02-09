"""Tests for Kida strict mode.

RFC: rfc-kida-python-compatibility.md (Phase 2)

Strict mode (default) raises UndefinedError for undefined variables instead
of silently returning None. This catches typos and missing variables early.

Key behaviors:
1. Undefined variables raise UndefinedError
2. Defined variables work normally
3. Undefined variables always raise UndefinedError
4. default filter works with undefined variables
5. is defined/is undefined tests work correctly
6. Error messages include variable name and location
"""

from __future__ import annotations

import pytest

from kida.environment import Environment, UndefinedError


class TestUndefinedError:
    """Test UndefinedError behavior in strict mode."""

    @pytest.fixture
    def env(self) -> Environment:
        """Create a strict mode environment (default)."""
        return Environment()

    def test_undefined_raises_error(self, env: Environment) -> None:
        """Accessing undefined variable raises UndefinedError."""
        with pytest.raises(UndefinedError) as exc_info:
            env.from_string("{{ undefined_var }}").render()
        assert "undefined_var" in str(exc_info.value)

    def test_error_includes_variable_name(self, env: Environment) -> None:
        """Error includes the undefined variable name."""
        try:
            env.from_string("{{ my_missing_var }}").render()
            pytest.fail("Expected UndefinedError")
        except UndefinedError as e:
            assert e.name == "my_missing_var"

    def test_error_includes_template_name(self, env: Environment) -> None:
        """Error includes template name when available."""
        try:
            env.from_string("{{ missing }}", name="test.html").render()
            pytest.fail("Expected UndefinedError")
        except UndefinedError as e:
            assert "test.html" in str(e)

    def test_defined_variables_work(self, env: Environment) -> None:
        """Defined variables work normally in strict mode."""
        result = env.from_string("{{ name }}").render(name="World")
        assert result == "World"

    def test_globals_work(self, env: Environment) -> None:
        """Global functions work in strict mode."""
        result = env.from_string("{{ len([1, 2, 3]) }}").render()
        assert result == "3"


class TestDefaultFilter:
    """Test default filter works with strict mode."""

    @pytest.fixture
    def env(self) -> Environment:
        """Create a strict mode environment (default)."""
        return Environment()

    def test_default_with_undefined(self, env: Environment) -> None:
        """Default filter provides fallback for undefined variables."""
        result = env.from_string('{{ missing | default("fallback") }}').render()
        assert result == "fallback"

    def test_default_d_alias(self, env: Environment) -> None:
        """The 'd' alias for default filter works."""
        result = env.from_string('{{ missing | d("fallback") }}').render()
        assert result == "fallback"

    def test_default_with_defined(self, env: Environment) -> None:
        """Default filter returns value when defined."""
        result = env.from_string('{{ name | default("fallback") }}').render(name="Alice")
        assert result == "Alice"

    def test_default_with_none(self, env: Environment) -> None:
        """Default filter handles None values."""
        result = env.from_string('{{ value | default("fallback") }}').render(value=None)
        assert result == "fallback"

    def test_default_boolean_true(self, env: Environment) -> None:
        """Default filter with boolean=True checks truthiness."""
        result = env.from_string('{{ value | default("fallback", true) }}').render(value="")
        assert result == "fallback"

    def test_default_boolean_false(self, env: Environment) -> None:
        """Default filter with boolean=False only checks None."""
        result = env.from_string('{{ value | default("fallback", false) }}').render(value="")
        assert result == ""


class TestIsDefinedTest:
    """Test 'is defined' and 'is undefined' tests work with strict mode."""

    @pytest.fixture
    def env(self) -> Environment:
        """Create a strict mode environment (default)."""
        return Environment()

    def test_is_defined_true(self, env: Environment) -> None:
        """'is defined' returns True for defined variables."""
        result = env.from_string("{% if x is defined %}yes{% endif %}").render(x=42)
        assert result == "yes"

    def test_is_defined_false(self, env: Environment) -> None:
        """'is defined' returns False for undefined variables."""
        result = env.from_string("{% if x is defined %}yes{% else %}no{% endif %}").render()
        assert result == "no"

    def test_is_undefined_true(self, env: Environment) -> None:
        """'is undefined' returns True for undefined variables."""
        result = env.from_string("{% if x is undefined %}yes{% endif %}").render()
        assert result == "yes"

    def test_is_undefined_false(self, env: Environment) -> None:
        """'is undefined' returns False for defined variables."""
        result = env.from_string("{% if x is undefined %}yes{% else %}no{% endif %}").render(x=42)
        assert result == "no"

    def test_is_not_defined(self, env: Environment) -> None:
        """'is not defined' works correctly."""
        result = env.from_string("{% if x is not defined %}yes{% endif %}").render()
        assert result == "yes"

    def test_none_is_undefined(self, env: Environment) -> None:
        """None value is considered undefined (consistent with Jinja2)."""
        result = env.from_string("{% if x is defined %}yes{% else %}no{% endif %}").render(x=None)
        assert result == "no"


class TestIsDefinedAttributeChains:
    """Test that 'is defined' works correctly for attribute chains.

    Regression tests for the bug where ``pokemon.name is defined``
    returned True when ``pokemon`` was a list (no ``.name`` attribute).
    """

    @pytest.fixture
    def env(self) -> Environment:
        return Environment()

    def test_missing_attr_on_list_is_not_defined(self, env: Environment) -> None:
        t = env.from_string("{% if items.name is defined %}yes{% else %}no{% end %}")
        assert t.render(items=[1, 2, 3]) == "no"

    def test_missing_attr_on_int_is_not_defined(self, env: Environment) -> None:
        t = env.from_string("{% if x.foo is defined %}yes{% else %}no{% end %}")
        assert t.render(x=42) == "no"

    def test_existing_attr_on_dict_is_defined(self, env: Environment) -> None:
        t = env.from_string("{% if obj.name is defined %}yes{% else %}no{% end %}")
        assert t.render(obj={"name": "hello"}) == "yes"

    def test_missing_key_on_dict_is_not_defined(self, env: Environment) -> None:
        t = env.from_string("{% if obj.missing is defined %}yes{% else %}no{% end %}")
        assert t.render(obj={"name": "hello"}) == "no"

    def test_attr_on_none_is_not_defined(self, env: Environment) -> None:
        t = env.from_string("{% if obj.name is defined %}yes{% else %}no{% end %}")
        assert t.render(obj=None) == "no"

    def test_existing_attr_on_object_is_defined(self, env: Environment) -> None:
        class Obj:
            name = "test"

        t = env.from_string("{% if obj.name is defined %}yes{% else %}no{% end %}")
        assert t.render(obj=Obj()) == "yes"

    def test_is_undefined_for_missing_attr(self, env: Environment) -> None:
        t = env.from_string("{% if items.name is undefined %}yes{% else %}no{% end %}")
        assert t.render(items=[1, 2]) == "yes"

    def test_is_not_defined_for_missing_attr(self, env: Environment) -> None:
        t = env.from_string("{% if items.name is not defined %}yes{% else %}no{% end %}")
        assert t.render(items=[1, 2]) == "yes"

    def test_undefined_attr_renders_empty(self, env: Environment) -> None:
        """Missing attributes still render as empty string in output."""
        t = env.from_string("{{ items.name }}")
        assert t.render(items=[1, 2]) == ""

    def test_undefined_attr_is_falsy_in_if(self, env: Environment) -> None:
        """Missing attributes are falsy in plain {% if %} guards."""
        t = env.from_string("{% if items.name %}yes{% else %}no{% end %}")
        assert t.render(items=[1, 2]) == "no"


class TestStrictModeEdgeCases:
    """Test edge cases and complex scenarios with strict mode."""

    @pytest.fixture
    def env(self) -> Environment:
        """Create a strict mode environment (default)."""
        return Environment()

    def test_nested_attribute_on_undefined(self, env: Environment) -> None:
        """Nested attribute access on undefined raises error."""
        with pytest.raises(UndefinedError):
            env.from_string("{{ missing.attr }}").render()

    def test_attribute_access_on_defined(self, env: Environment) -> None:
        """Attribute access on defined object works."""
        result = env.from_string("{{ obj.name }}").render(obj={"name": "test"})
        assert result == "test"

    def test_loop_variable_defined(self, env: Environment) -> None:
        """Loop variables are considered defined."""
        result = env.from_string("{% for i in items %}{{ i }}{% endfor %}").render(items=[1, 2, 3])
        assert result == "123"

    def test_set_makes_variable_defined(self, env: Environment) -> None:
        """Variables set with {% set %} are considered defined."""
        result = env.from_string("{% set x = 42 %}{{ x }}").render()
        assert result == "42"

    def test_filter_on_defined_none(self, env: Environment) -> None:
        """Filters work on defined None values."""
        result = env.from_string('{{ value | default("none") }}').render(value=None)
        assert result == "none"

    def test_complex_expression_with_undefined(self, env: Environment) -> None:
        """Complex expressions with undefined parts raise error."""
        with pytest.raises(UndefinedError):
            env.from_string("{{ a + b }}").render(a=1)

    def test_conditional_short_circuit(self, env: Environment) -> None:
        """Conditionals short-circuit to avoid evaluating undefined."""
        # If 'x' is truthy, 'y' is never evaluated
        result = env.from_string("{% if x or y %}yes{% endif %}").render(x=True)
        assert result == "yes"


class TestStrictModePerformance:
    """Verify strict mode doesn't add significant overhead."""

    def test_strict_mode_fast_path(self) -> None:
        """Defined variables use fast lookup path."""
        env = Environment()
        tmpl = env.from_string("{{ name }}")
        # Should be fast - no exception handling in hot path
        for _ in range(100):
            assert tmpl.render(name="test") == "test"
