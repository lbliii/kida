"""Tests for kida.environment.filters._misc.

Covers _filter_get (dict/object/None access, method-name shadowing),
_filter_date (None, datetime, epoch, invalid epoch — see TestFilterDateBugs),
_filter_random and _filter_shuffle (empty, single, determinism via seed),
_filter_classes (None, falsy values, nested lists, non-iterable).
"""

from __future__ import annotations

import random as random_module
from datetime import date, datetime

import pytest

from kida.environment.filters._misc import (
    _filter_classes,
    _filter_date,
    _filter_get,
    _filter_random,
    _filter_shuffle,
    _filter_urlencode,
)


class _Obj:
    def __init__(self, name: str = "x") -> None:
        self.name = name


class TestFilterGet:
    def test_dict_existing_key(self):
        assert _filter_get({"a": 1, "b": 2}, "a") == 1

    def test_dict_missing_key_default_none(self):
        assert _filter_get({"a": 1}, "missing") is None

    def test_dict_missing_key_custom_default(self):
        assert _filter_get({"a": 1}, "missing", "fallback") == "fallback"

    def test_dict_method_name_shadow(self):
        # Motivating case: dict 'items'/'keys'/'values'/'get' would normally
        # return the bound method via dotted access. _filter_get reaches the value.
        assert _filter_get({"items": "real-value"}, "items") == "real-value"
        assert _filter_get({"keys": [1, 2]}, "keys") == [1, 2]

    def test_none_value_returns_default(self):
        assert _filter_get(None, "any") is None
        assert _filter_get(None, "any", "fallback") == "fallback"

    def test_object_attr_access(self):
        assert _filter_get(_Obj(name="alice"), "name") == "alice"

    def test_object_missing_attr_returns_default(self):
        assert _filter_get(_Obj(), "nope", "fb") == "fb"


class TestFilterDate:
    def test_none_returns_empty(self):
        assert _filter_date(None) == ""

    def test_datetime_default_format(self):
        dt = datetime(2026, 4, 20, 12, 0, 0)
        assert _filter_date(dt) == "2026-04-20"

    def test_datetime_custom_format(self):
        dt = datetime(2026, 4, 20)
        assert _filter_date(dt, "%b %d, %Y") == "Apr 20, 2026"

    def test_date_object(self):
        assert _filter_date(date(2026, 4, 20)) == "2026-04-20"

    def test_epoch_int(self):
        # Epoch 0 is platform-local; just check format is a date
        result = _filter_date(0)
        assert len(result) == 10
        assert result.count("-") == 2

    def test_epoch_float(self):
        result = _filter_date(0.5)
        assert len(result) == 10

    def test_unsupported_type_returns_empty(self):
        # Strings, lists etc. fall through to the empty branch
        assert _filter_date("2026-04-20") == ""
        assert _filter_date([1, 2, 3]) == ""


class TestFilterDateGracefulDegradation:
    """_filter_date returns '' with a CoercionWarning rather than crashing on
    out-of-range or NaN epochs. Previously raised OverflowError/ValueError.
    """

    def test_huge_epoch_returns_empty_with_warning(self):
        from kida.exceptions import CoercionWarning

        with pytest.warns(CoercionWarning, match="could not convert epoch"):
            assert _filter_date(10**20) == ""

    def test_negative_huge_epoch_returns_empty_with_warning(self):
        from kida.exceptions import CoercionWarning

        with pytest.warns(CoercionWarning):
            assert _filter_date(-(10**20)) == ""

    def test_nan_returns_empty_with_warning(self):
        from kida.exceptions import CoercionWarning

        with pytest.warns(CoercionWarning):
            assert _filter_date(float("nan")) == ""


class TestFilterRandom:
    def test_empty_returns_none(self):
        assert _filter_random([]) is None
        assert _filter_random("") is None
        assert _filter_random(()) is None

    def test_single_element(self):
        assert _filter_random([42]) == 42

    def test_picks_from_sequence(self, monkeypatch):
        monkeypatch.setattr(random_module, "choice", lambda seq: seq[0])
        assert _filter_random([1, 2, 3]) == 1

    def test_works_on_iterators(self):
        # _filter_random calls list(value), so iterators are fine
        result = _filter_random(iter([99]))
        assert result == 99


class TestFilterShuffle:
    def test_empty(self):
        assert _filter_shuffle([]) == []

    def test_single_element(self):
        assert _filter_shuffle([7]) == [7]

    def test_returns_new_list_not_input(self):
        original = [1, 2, 3]
        result = _filter_shuffle(original)
        assert result is not original
        assert sorted(result) == [1, 2, 3]

    def test_works_on_tuple(self):
        result = _filter_shuffle((1, 2, 3))
        assert isinstance(result, list)
        assert sorted(result) == [1, 2, 3]

    def test_deterministic_with_seed(self):
        random_module.seed(42)
        a = _filter_shuffle([1, 2, 3, 4, 5])
        random_module.seed(42)
        b = _filter_shuffle([1, 2, 3, 4, 5])
        assert a == b


class TestFilterClasses:
    def test_none_returns_empty(self):
        assert _filter_classes(None) == ""

    def test_simple_list(self):
        assert _filter_classes(["card", "active"]) == "card active"

    def test_drops_falsy(self):
        # None, "", False, 0 all dropped
        assert _filter_classes(["card", None, "", False, 0, "done"]) == "card done"

    def test_drops_conditional_when_false(self):
        # Common pattern: ['card', 'active' if False, 'done' if True]
        # The parser produces None for false conditionals; classes drops it.
        assert _filter_classes(["card", None, "done"]) == "card done"

    def test_nested_list_flattened_one_level(self):
        assert _filter_classes(["a", ["b", "c"], "d"]) == "a b c d"

    def test_nested_tuple_flattened(self):
        assert _filter_classes(["a", ("b", "c")]) == "a b c"

    def test_nested_list_drops_falsy(self):
        assert _filter_classes(["a", ["b", None, "", "c"]]) == "a b c"

    def test_empty_list(self):
        assert _filter_classes([]) == ""

    def test_non_iterable_falls_back_to_str(self):
        assert _filter_classes(42) == "42"

    def test_string_input_iterated_as_chars(self):
        # str is iterable, so each char is treated as a class — surprising but
        # documented; users should pass a list.
        assert _filter_classes("abc") == "a b c"

    def test_int_in_list_stringified(self):
        assert _filter_classes([1, 2, 3]) == "1 2 3"


class TestFilterUrlencode:
    def test_basic(self):
        assert _filter_urlencode("hello world") == "hello%20world"

    def test_special_chars(self):
        assert _filter_urlencode("a/b?c=d") == "a%2Fb%3Fc%3Dd"

    def test_non_string_coerced(self):
        assert _filter_urlencode(42) == "42"
