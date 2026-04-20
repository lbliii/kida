"""Tests for kida.environment.filters._debug.

Covers _filter_debug (None, str, list, tuple, dict, custom obj with title/weight,
nested objects, max_items truncation) and _filter_pprint (None, dict, list).

_filter_debug returns its input unchanged but writes a formatted summary to
stderr, so tests assert both the return value identity AND the stderr output.
"""

from __future__ import annotations

from kida.environment.filters._debug import _debug_repr, _filter_debug, _filter_pprint


class _Page:
    """Object with title/weight attributes — exercises the special-case branch."""

    def __init__(self, title: str | None = None, weight: int | None = None) -> None:
        self.title = title
        self.weight = weight


class _PageWithMetadata:
    """Object whose weight lives under .metadata['weight']."""

    def __init__(self, title: str, metadata: dict[str, object]) -> None:
        self.title = title
        self.metadata = metadata


class _Plain:
    """Object with __dict__ but no title attr — exercises the generic obj branch.

    Uses int values (not str) so attribute reprs avoid the .title-method
    surprise documented in TestDebugRepr.test_str_triggers_title_branch.
    """

    def __init__(self) -> None:
        self.foo = 42
        self.empty = None
        self._private = "hidden"


class TestDebugRepr:
    def test_none(self):
        assert _debug_repr(None) == "None"

    def test_object_with_title_only(self):
        page = _Page(title="Intro")
        assert _debug_repr(page) == "_Page(title='Intro')"

    def test_object_with_title_and_weight(self):
        page = _Page(title="Intro", weight=10)
        assert _debug_repr(page) == "_Page(title='Intro', weight=10)"

    def test_object_with_metadata_weight(self):
        page = _PageWithMetadata(title="Intro", metadata={"weight": 5})
        assert _debug_repr(page) == "_PageWithMetadata(title='Intro', weight=5)"

    def test_long_repr_truncated(self):
        # Use list (no .title attr) so the truncation branch is reached
        long_list = list(range(100))
        result = _debug_repr(long_list, max_len=20)
        assert len(result) == 20
        assert result.endswith("...")

    def test_short_repr_not_truncated(self):
        assert _debug_repr(42) == "42"

    def test_str_does_not_trigger_title_branch(self):
        # Regression guard: str.title is a bound method, not a string.
        # _debug_repr must not mistake it for a Page-like .title attribute.
        assert _debug_repr("bar") == "'bar'"

    def test_bytes_does_not_trigger_title_branch(self):
        assert _debug_repr(b"bar") == "b'bar'"

    def test_object_with_callable_title_skipped(self):
        class Methody:
            def title(self):
                return "should not appear"

        result = _debug_repr(Methody())
        # Falls through to repr — no title= prefix
        assert "title=" not in result


class TestFilterDebug:
    def test_returns_value_unchanged_none(self, capsys):
        result = _filter_debug(None)
        assert result is None
        err = capsys.readouterr().err
        assert "DEBUG" in err
        assert "None" in err

    def test_returns_value_unchanged_str(self, capsys):
        result = _filter_debug("hello")
        assert result == "hello"
        err = capsys.readouterr().err
        assert "DEBUG" in err
        assert "str" in err

    def test_label_appears_in_output(self, capsys):
        _filter_debug([1, 2, 3], label="my list")
        err = capsys.readouterr().err
        assert "[my list]" in err

    def test_list_shows_length_and_items(self, capsys):
        _filter_debug([1, 2, 3])
        err = capsys.readouterr().err
        assert "list[3]" in err
        assert "[0] 1" in err
        assert "[2] 3" in err

    def test_tuple_handled_like_list(self, capsys):
        _filter_debug((10, 20))
        err = capsys.readouterr().err
        assert "tuple[2]" in err
        assert "[0] 10" in err

    def test_list_truncated_by_max_items(self, capsys):
        _filter_debug([1, 2, 3, 4, 5, 6, 7], max_items=3)
        err = capsys.readouterr().err
        assert "list[7]" in err
        assert "[0] 1" in err
        assert "[2] 3" in err
        assert "[3]" not in err
        assert "4 more items" in err

    def test_list_of_objects_flags_none_attrs(self, capsys):
        items = [_Page(title="A", weight=1), _Page(title="B", weight=None)]
        _filter_debug(items)
        err = capsys.readouterr().err
        assert "_Page(title='A', weight=1)" in err
        assert "<-- None: weight" in err

    def test_dict_shows_key_count_and_pairs(self, capsys):
        _filter_debug({"a": 1, "b": 2})
        err = capsys.readouterr().err
        assert "dict[2 keys]" in err
        assert "'a'" in err
        assert "'b'" in err

    def test_dict_flags_none_value(self, capsys):
        _filter_debug({"name": "x", "weight": None})
        err = capsys.readouterr().err
        assert "<-- None!" in err

    def test_dict_truncated_by_max_items(self, capsys):
        _filter_debug({f"k{i}": i for i in range(10)}, max_items=2)
        err = capsys.readouterr().err
        assert "dict[10 keys]" in err
        assert "8 more keys" in err

    def test_object_with_dict(self, capsys):
        _filter_debug(_Plain())
        err = capsys.readouterr().err
        assert "<_Plain>" in err
        assert ".foo = 42" in err
        assert ".empty = None <-- None!" in err
        # Private attributes excluded
        assert "_private" not in err

    def test_object_attrs_truncated_by_max_items(self, capsys):
        class Many:
            def __init__(self) -> None:
                for i in range(8):
                    setattr(self, f"attr{i}", i)

        _filter_debug(Many(), max_items=3)
        err = capsys.readouterr().err
        assert "5 more attributes" in err

    def test_scalar_falls_through_to_default_branch(self, capsys):
        _filter_debug(42)
        err = capsys.readouterr().err
        assert "42 (int)" in err

    def test_no_label_omits_brackets(self, capsys):
        _filter_debug("x")
        err = capsys.readouterr().err
        # Format is "DEBUG : ..." when no label (label_str is empty)
        assert "DEBUG :" in err
        assert "[" not in err.split(":", 1)[0]


class TestFilterPprint:
    def test_pprint_none(self):
        assert _filter_pprint(None) == "None"

    def test_pprint_dict(self):
        result = _filter_pprint({"a": 1, "b": 2})
        assert "'a': 1" in result
        assert "'b': 2" in result

    def test_pprint_list(self):
        result = _filter_pprint([1, 2, 3])
        assert result == "[1, 2, 3]"

    def test_pprint_nested(self):
        result = _filter_pprint({"outer": {"inner": [1, 2]}})
        assert "'outer'" in result
        assert "'inner'" in result
