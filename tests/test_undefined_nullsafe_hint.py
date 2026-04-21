"""Tests for the null-safe hint on `UndefinedError` (Sprint 3.1).

Attribute/key UndefinedErrors include a secondary hint pointing at `?.`, `?[`,
`??`, and `| get(...)` so users stop reaching for `.get("k", "")` chains.
Variable-kind UndefinedErrors keep their existing hint unchanged.
"""

import pytest

from kida import Environment
from kida.exceptions import UndefinedError


def test_attribute_error_includes_nullsafe_hint():
    env = Environment(strict_undefined=True)
    t = env.from_string("{{ user.nickname }}")
    with pytest.raises(UndefinedError) as excinfo:
        t.render(user={})
    msg = str(excinfo.value)
    assert "x?.y" in msg
    assert "| get(" in msg


def test_variable_error_does_not_include_nullsafe_hint():
    env = Environment(strict_undefined=True)
    t = env.from_string("{{ something }}")
    with pytest.raises(UndefinedError) as excinfo:
        t.render()
    msg = str(excinfo.value)
    assert "x?.y" not in msg


def test_nullsafe_hint_is_in_addition_not_replacement():
    """The null-safe hint should appear alongside the primary hint."""
    env = Environment(strict_undefined=True)
    t = env.from_string("{{ user.nickname }}")
    with pytest.raises(UndefinedError) as excinfo:
        t.render(user={})
    msg = str(excinfo.value)
    # Primary hint (about | default) still present for attribute errors
    assert "default" in msg
    # Null-safe hint also present
    assert "x?.y" in msg


def test_format_compact_includes_nullsafe_hint():
    """Structured terminal output also carries the null-safe hint."""
    err = UndefinedError("dict.nickname", kind="attribute/key")
    compact = err.format_compact()
    assert "x?.y" in compact


def test_format_compact_variable_kind_no_nullsafe_hint():
    err = UndefinedError("something", kind="variable")
    compact = err.format_compact()
    assert "x?.y" not in compact


# --- Semantic pins for ?. operator (v0.8.0 split) ---
# `?.` and `?[...]` short-circuit missing keys to None on Mapping receivers.
# Object attribute misses still raise under strict mode. These tests pin that
# split so docs and implementation cannot drift apart silently.


def test_optional_dot_short_circuits_on_none_receiver():
    env = Environment(strict_undefined=True)
    t = env.from_string("{{ user?.nickname }}")
    assert t.render(user=None) == ""


def test_optional_dot_returns_none_on_missing_mapping_key():
    """v0.8.0: `?.` on a Mapping returns None for missing keys (dict.get idiom)."""
    env = Environment(strict_undefined=True)
    t = env.from_string("{{ user?.nickname }}")
    assert t.render(user={}) == ""


def test_optional_dot_still_raises_on_missing_object_attr():
    """v0.8.0: object attribute misses still raise in strict mode."""

    class User:
        pass

    env = Environment(strict_undefined=True)
    t = env.from_string("{{ user?.nickname }}")
    with pytest.raises(UndefinedError):
        t.render(user=User())


def test_optional_dot_with_coalesce_handles_both():
    env = Environment(strict_undefined=True)
    t = env.from_string('{{ user?.nickname ?? "fb" }}')
    assert t.render(user=None) == "fb"
    assert t.render(user={}) == "fb"
    assert t.render(user={"nickname": "Ada"}) == "Ada"
