"""Tests for kida.sandbox module."""

import pytest

from kida.sandbox import (
    DEFAULT_POLICY,
    SandboxedEnvironment,
    SandboxPolicy,
    SecurityError,
    _is_attr_blocked,
    _is_type_blocked,
    _make_sandboxed_range,
)

# ---------------------------------------------------------------------------
# SandboxedEnvironment: rendering safe templates
# ---------------------------------------------------------------------------


class TestSandboxedEnvironmentSafeTemplates:
    def setup_method(self):
        self.env = SandboxedEnvironment()

    def test_render_dict_attribute(self):
        result = self.env.from_string("{{ user.name }}").render(user={"name": "Alice"})
        assert result == "Alice"

    def test_render_nested_dict(self):
        data = {"user": {"address": {"city": "Portland"}}}
        result = self.env.from_string("{{ user.address.city }}").render(**data)
        assert result == "Portland"

    def test_render_string_method(self):
        result = self.env.from_string("{{ name.upper() }}").render(name="alice")
        assert result == "ALICE"

    def test_render_list_access(self):
        result = self.env.from_string("{{ items[0] }}").render(items=["a", "b", "c"])
        assert result == "a"

    def test_render_plain_string(self):
        result = self.env.from_string("hello world").render()
        assert result == "hello world"

    def test_render_variable_substitution(self):
        result = self.env.from_string("Hello, {{ name }}!").render(name="Bob")
        assert result == "Hello, Bob!"


# ---------------------------------------------------------------------------
# SecurityError on blocked dunder attributes
# ---------------------------------------------------------------------------


class TestBlockedDunderAttributes:
    def setup_method(self):
        self.env = SandboxedEnvironment()

    def test_class_blocked(self):
        with pytest.raises(SecurityError, match="__class__"):
            self.env.from_string("{{ x.__class__ }}").render(x="hello")

    def test_globals_blocked(self):
        with pytest.raises(SecurityError, match="__globals__"):
            self.env.from_string("{{ x.__globals__ }}").render(x=lambda: None)

    def test_subclasses_blocked(self):
        with pytest.raises(SecurityError, match="__subclasses__"):
            self.env.from_string("{{ x.__subclasses__ }}").render(x="hello")

    def test_mro_blocked(self):
        with pytest.raises(SecurityError, match="__mro__"):
            self.env.from_string("{{ x.__mro__ }}").render(x="hello")

    def test_dict_blocked(self):
        with pytest.raises(SecurityError, match="__dict__"):
            self.env.from_string("{{ x.__dict__ }}").render(x="hello")

    def test_init_blocked(self):
        with pytest.raises(SecurityError, match="__init__"):
            self.env.from_string("{{ x.__init__ }}").render(x="hello")


# ---------------------------------------------------------------------------
# SecurityError on blocked types (function, type objects)
# ---------------------------------------------------------------------------


class TestBlockedTypes:
    def setup_method(self):
        self.env = SandboxedEnvironment()

    def test_function_type_blocked(self):
        fn = lambda: None  # noqa: E731
        with pytest.raises(SecurityError, match="function"):
            self.env.from_string("{{ fn.safe_attr }}").render(fn=fn)

    def test_type_object_blocked(self):
        with pytest.raises(SecurityError, match="type"):
            self.env.from_string("{{ t.mro }}").render(t=int)


# ---------------------------------------------------------------------------
# SandboxPolicy configuration
# ---------------------------------------------------------------------------


class TestSandboxPolicy:
    def test_default_policy_values(self):
        policy = SandboxPolicy()
        assert policy.allowed_attributes is None
        assert policy.blocked_attributes == frozenset()
        assert policy.blocked_types == frozenset()
        assert policy.allow_import is False
        assert policy.max_output_size is None
        assert policy.max_range == 10000

    def test_custom_allowed_attributes(self):
        policy = SandboxPolicy(allowed_attributes=frozenset({"name", "title"}))
        assert policy.allowed_attributes == frozenset({"name", "title"})

    def test_custom_blocked_attributes(self):
        policy = SandboxPolicy(blocked_attributes=frozenset({"secret"}))
        assert "secret" in policy.blocked_attributes

    def test_policy_is_frozen(self):
        policy = SandboxPolicy()
        with pytest.raises(AttributeError):
            policy.max_range = 5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _is_attr_blocked()
# ---------------------------------------------------------------------------


class TestIsAttrBlocked:
    def test_builtin_blocked_dunder(self):
        assert _is_attr_blocked("__class__", DEFAULT_POLICY) is True

    def test_builtin_blocked_globals(self):
        assert _is_attr_blocked("__globals__", DEFAULT_POLICY) is True

    def test_builtin_blocked_code(self):
        assert _is_attr_blocked("__code__", DEFAULT_POLICY) is True

    def test_frame_attr_blocked(self):
        assert _is_attr_blocked("gi_frame", DEFAULT_POLICY) is True

    def test_f_globals_blocked(self):
        assert _is_attr_blocked("f_globals", DEFAULT_POLICY) is True

    def test_safe_name_allowed(self):
        assert _is_attr_blocked("name", DEFAULT_POLICY) is False

    def test_safe_name_title(self):
        assert _is_attr_blocked("title", DEFAULT_POLICY) is False

    def test_regular_attribute_allowed(self):
        assert _is_attr_blocked("foo", DEFAULT_POLICY) is False

    def test_unknown_dunder_blocked(self):
        # Unknown dunders should be blocked (not in the safe set)
        assert _is_attr_blocked("__whatever__", DEFAULT_POLICY) is True

    def test_allowed_dunder_len(self):
        assert _is_attr_blocked("__len__", DEFAULT_POLICY) is False

    def test_allowed_dunder_iter(self):
        assert _is_attr_blocked("__iter__", DEFAULT_POLICY) is False

    def test_allowed_dunder_contains(self):
        assert _is_attr_blocked("__contains__", DEFAULT_POLICY) is False

    def test_allowed_dunder_getitem(self):
        assert _is_attr_blocked("__getitem__", DEFAULT_POLICY) is False

    def test_allowed_dunder_str(self):
        assert _is_attr_blocked("__str__", DEFAULT_POLICY) is False

    def test_allowed_dunder_repr(self):
        assert _is_attr_blocked("__repr__", DEFAULT_POLICY) is False

    def test_custom_blocked_attribute(self):
        policy = SandboxPolicy(blocked_attributes=frozenset({"secret"}))
        assert _is_attr_blocked("secret", policy) is True

    def test_custom_blocked_does_not_affect_others(self):
        policy = SandboxPolicy(blocked_attributes=frozenset({"secret"}))
        assert _is_attr_blocked("name", policy) is False

    def test_allowed_attributes_whitelist(self):
        policy = SandboxPolicy(allowed_attributes=frozenset({"name", "age"}))
        assert _is_attr_blocked("name", policy) is False
        assert _is_attr_blocked("age", policy) is False

    def test_allowed_attributes_blocks_unlisted(self):
        policy = SandboxPolicy(allowed_attributes=frozenset({"name"}))
        assert _is_attr_blocked("email", policy) is True

    def test_safe_collection_methods_pass_with_whitelist(self):
        # Safe collection methods are allowed even with an allowed_attributes whitelist
        policy = SandboxPolicy(allowed_attributes=frozenset({"name"}))
        assert _is_attr_blocked("items", policy) is False
        assert _is_attr_blocked("keys", policy) is False
        assert _is_attr_blocked("upper", policy) is False


# ---------------------------------------------------------------------------
# _is_type_blocked()
# ---------------------------------------------------------------------------


class TestIsTypeBlocked:
    def test_function_blocked(self):
        assert _is_type_blocked(lambda: None, DEFAULT_POLICY) is True

    def test_type_object_blocked(self):
        assert _is_type_blocked(int, DEFAULT_POLICY) is True

    def test_string_safe(self):
        assert _is_type_blocked("hello", DEFAULT_POLICY) is False

    def test_int_safe(self):
        assert _is_type_blocked(42, DEFAULT_POLICY) is False

    def test_dict_safe(self):
        assert _is_type_blocked({"a": 1}, DEFAULT_POLICY) is False

    def test_list_safe(self):
        assert _is_type_blocked([1, 2, 3], DEFAULT_POLICY) is False

    def test_none_safe(self):
        assert _is_type_blocked(None, DEFAULT_POLICY) is False

    def test_custom_blocked_type(self):

        class Evil:
            pass

        policy = SandboxPolicy(blocked_types=frozenset({Evil}))
        assert _is_type_blocked(Evil(), policy) is True

    def test_custom_blocked_does_not_affect_builtins(self):

        class Evil:
            pass

        policy = SandboxPolicy(blocked_types=frozenset({Evil}))
        assert _is_type_blocked("safe", policy) is False


# ---------------------------------------------------------------------------
# Sandboxed range()
# ---------------------------------------------------------------------------


class TestSandboxedRange:
    def test_range_within_limit(self):
        sandboxed_range = _make_sandboxed_range(DEFAULT_POLICY)
        result = sandboxed_range(10)
        assert list(result) == list(range(10))

    def test_range_at_limit(self):
        policy = SandboxPolicy(max_range=5)
        sandboxed_range = _make_sandboxed_range(policy)
        result = sandboxed_range(5)
        assert list(result) == [0, 1, 2, 3, 4]

    def test_range_exceeds_limit(self):
        policy = SandboxPolicy(max_range=5)
        sandboxed_range = _make_sandboxed_range(policy)
        with pytest.raises(SecurityError, match="exceeds sandbox limit"):
            sandboxed_range(6)

    def test_range_with_start_stop(self):
        sandboxed_range = _make_sandboxed_range(DEFAULT_POLICY)
        result = sandboxed_range(2, 5)
        assert list(result) == [2, 3, 4]

    def test_range_with_step(self):
        sandboxed_range = _make_sandboxed_range(DEFAULT_POLICY)
        result = sandboxed_range(0, 10, 2)
        assert list(result) == [0, 2, 4, 6, 8]

    def test_range_zero_size_ok(self):
        policy = SandboxPolicy(max_range=0)
        sandboxed_range = _make_sandboxed_range(policy)
        result = sandboxed_range(0)
        assert list(result) == []

    def test_range_via_template(self):
        env = SandboxedEnvironment()
        result = env.from_string("{% for i in range(3) %}{{ i }}{% endfor %}").render()
        assert result == "012"


# ---------------------------------------------------------------------------
# DEFAULT_POLICY
# ---------------------------------------------------------------------------


class TestDefaultPolicy:
    def test_default_policy_is_sandbox_policy(self):
        assert isinstance(DEFAULT_POLICY, SandboxPolicy)

    def test_default_policy_no_allowed_attributes(self):
        assert DEFAULT_POLICY.allowed_attributes is None

    def test_default_policy_no_extra_blocked(self):
        assert DEFAULT_POLICY.blocked_attributes == frozenset()

    def test_default_policy_no_import(self):
        assert DEFAULT_POLICY.allow_import is False

    def test_default_policy_max_range(self):
        assert DEFAULT_POLICY.max_range == 10000
