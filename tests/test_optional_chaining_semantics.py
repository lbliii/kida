"""v0.8.0 semantics for `?.` and `?[...]` — Mapping-soft, object-strict.

`?.` and `?[...]` short-circuit missing keys to ``None`` on Mapping receivers
(mirroring Python's ``dict.get(key)`` idiom). Object attribute misses and
Sequence out-of-range accesses still raise ``UndefinedError`` under strict mode.
"""

from __future__ import annotations

from collections import ChainMap
from types import MappingProxyType, SimpleNamespace

import pytest

from kida import Environment
from kida.exceptions import UndefinedError


@pytest.fixture
def strict_env():
    return Environment(strict_undefined=True)


@pytest.fixture
def lenient_env():
    return Environment(strict_undefined=False)


# --- Mapping short-circuit: `?.` ---


def test_optional_dot_plain_dict_missing_key_returns_none(strict_env):
    t = strict_env.from_string("{{ user?.nickname }}")
    assert t.render(user={}) == ""


def test_optional_dot_mapping_proxy_missing_key_returns_none(strict_env):
    t = strict_env.from_string("{{ cfg?.theme }}")
    assert t.render(cfg=MappingProxyType({})) == ""


def test_optional_dot_chain_map_missing_key_returns_none(strict_env):
    t = strict_env.from_string("{{ cfg?.theme }}")
    assert t.render(cfg=ChainMap({}, {})) == ""


def test_optional_dot_dict_subclass_missing_key_returns_none(strict_env):
    class MyDict(dict):
        pass

    t = strict_env.from_string("{{ user?.nickname }}")
    assert t.render(user=MyDict()) == ""


def test_optional_dot_dict_subclass_with_missing_hook_is_honored(strict_env):
    """Dict subclasses with __missing__ get their hook respected (no bypass)."""

    class Defaulting(dict):
        def __missing__(self, key):
            return f"[{key}]"

    t = strict_env.from_string("{{ user?.nickname }}")
    # type(obj) is dict fast path doesn't match; Mapping slow path calls obj[name]
    # which triggers __missing__ → returns "[nickname]", not None.
    assert t.render(user=Defaulting()) == "[nickname]"


def test_optional_dot_mapping_present_key_returns_value(strict_env):
    t = strict_env.from_string("{{ user?.name }}")
    assert t.render(user={"name": "Ada"}) == "Ada"


# --- Mapping short-circuit: `?[...]` ---


def test_optional_subscript_dict_missing_key_returns_none(strict_env):
    t = strict_env.from_string("{{ cfg?['theme'] }}")
    assert t.render(cfg={}) == ""


def test_optional_subscript_mapping_proxy_missing_key_returns_none(strict_env):
    t = strict_env.from_string("{{ cfg?['theme'] }}")
    assert t.render(cfg=MappingProxyType({})) == ""


def test_optional_subscript_dict_present_key_returns_value(strict_env):
    t = strict_env.from_string("{{ cfg?['theme'] }}")
    assert t.render(cfg={"theme": "dark"}) == "dark"


# --- Object attr strictness preserved ---


def test_optional_dot_on_object_missing_attr_raises(strict_env):
    t = strict_env.from_string("{{ user?.nickname }}")
    with pytest.raises(UndefinedError):
        t.render(user=SimpleNamespace())


def test_optional_dot_on_object_present_attr_returns_value(strict_env):
    t = strict_env.from_string("{{ user?.name }}")
    assert t.render(user=SimpleNamespace(name="Ada")) == "Ada"


# --- Sequence out-of-range still strict ---


def test_optional_subscript_list_out_of_range_raises(strict_env):
    t = strict_env.from_string("{{ items?[5] }}")
    with pytest.raises(UndefinedError):
        t.render(items=[1, 2, 3])


def test_optional_subscript_list_in_range_returns_value(strict_env):
    t = strict_env.from_string("{{ items?[1] }}")
    assert t.render(items=["a", "b", "c"]) == "b"


# --- None receiver short-circuit (unchanged) ---


def test_optional_dot_none_receiver_returns_none(strict_env):
    t = strict_env.from_string("{{ user?.name }}")
    assert t.render(user=None) == ""


def test_optional_subscript_none_receiver_returns_none(strict_env):
    t = strict_env.from_string("{{ items?[0] }}")
    assert t.render(items=None) == ""


# --- Nested chains: every link may short-circuit ---


def test_nested_optional_dot_all_mappings_missing_returns_none(strict_env):
    t = strict_env.from_string("{{ config?.theme?.primary }}")
    assert t.render(config={}) == ""
    assert t.render(config={"theme": {}}) == ""
    assert t.render(config={"theme": {"primary": "#000"}}) == "#000"


def test_nested_optional_mixed_dot_and_bracket(strict_env):
    t = strict_env.from_string("{{ config?['theme']?.primary }}")
    assert t.render(config={}) == ""
    assert t.render(config={"theme": {"primary": "blue"}}) == "blue"


# --- Lenient mode (strict_undefined=False) ---


def test_lenient_optional_dot_mapping_miss_returns_none(lenient_env):
    t = lenient_env.from_string("{{ user?.nickname }}")
    assert t.render(user={}) == ""


def test_lenient_optional_subscript_list_out_of_range_returns_none(lenient_env):
    """Lenient mode is soft on Sequence out-of-range too."""
    t = lenient_env.from_string("{{ items?[5] }}")
    assert t.render(items=[1, 2, 3]) == ""


# --- Interaction with ?? (null coalesce) ---


def test_optional_dot_coalesce_on_mapping_miss(strict_env):
    t = strict_env.from_string('{{ user?.nickname ?? "fb" }}')
    assert t.render(user={}) == "fb"
    assert t.render(user=None) == "fb"
    assert t.render(user={"nickname": "Ada"}) == "Ada"


def test_optional_dot_coalesce_on_object_miss(strict_env):
    """?? catches the UndefinedError raised for object-attr misses."""
    t = strict_env.from_string('{{ user?.nickname ?? "fb" }}')
    assert t.render(user=SimpleNamespace()) == "fb"
    assert t.render(user=SimpleNamespace(nickname="Ada")) == "Ada"
