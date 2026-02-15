import pytest

from kida.environment import tests as builtin_tests
from kida.template.helpers import UNDEFINED, _Undefined


@pytest.mark.parametrize(
    ("value", "test_name", "args", "expected"),
    [
        (None, "defined", (), False),
        ("x", "defined", (), True),
        (None, "undefined", (), True),
        (2, "odd", (), False),
        (3, "odd", (), True),
        (4, "even", (), True),
        (6, "divisibleby", (3,), True),
        ("abc", "iterable", (), True),
        ({}, "mapping", (), True),
        ([1, 2], "sequence", (), True),
        ("hello", "string", (), True),
        (True, "true", (), True),
        (False, "false", (), True),
        ("foo", "match", (r"f.*",), True),
        ("abc", "eq", ("abc",), True),
        ("abc", "sameas", ("abc",), True),
        # _Undefined sentinel is treated as "not defined"
        (UNDEFINED, "defined", (), False),
        (UNDEFINED, "undefined", (), True),
    ],
)
def test_apply_test_branches(value, test_name, args, expected):
    assert builtin_tests._apply_test(value, test_name, *args) is expected


def test_default_tests_mapping_covers_aliases() -> None:
    funcs = builtin_tests.DEFAULT_TESTS
    # Aliases share the same callable object
    assert funcs["eq"] is funcs["equalto"]
    assert funcs["gt"] is funcs["greaterthan"]
    assert funcs["lt"] is funcs["lessthan"]
    # Callable and string helpers
    assert funcs["callable"](lambda: None) is True
    assert funcs["upper"]("ABC") is True
    assert funcs["lower"]("abc") is True


def test_match_returns_false_on_none() -> None:
    assert builtin_tests._test_match(None, r".*") is False


# ── _Undefined sentinel unit tests ──────────────────────────────────────


class TestUndefinedSentinel:
    """Unit tests for the _Undefined sentinel returned by _safe_getattr."""

    def test_str_returns_empty(self) -> None:
        assert str(UNDEFINED) == ""

    def test_repr(self) -> None:
        assert repr(UNDEFINED) == "Undefined"

    def test_falsy(self) -> None:
        assert not UNDEFINED
        assert bool(UNDEFINED) is False

    def test_len_is_zero(self) -> None:
        assert len(UNDEFINED) == 0

    def test_iterable_empty(self) -> None:
        assert list(UNDEFINED) == []

    def test_equality_with_another_undefined(self) -> None:
        other = _Undefined()
        assert other == UNDEFINED

    def test_not_equal_to_empty_string(self) -> None:
        assert UNDEFINED != ""

    def test_not_equal_to_none(self) -> None:
        assert UNDEFINED != None  # noqa: E711

    def test_hashable(self) -> None:
        s = {UNDEFINED}
        assert len(s) == 1

    def test_defined_test_returns_false(self) -> None:
        assert builtin_tests._test_defined(UNDEFINED) is False

    def test_apply_test_defined_returns_false(self) -> None:
        assert builtin_tests._apply_test(UNDEFINED, "defined") is False

    def test_apply_test_undefined_returns_true(self) -> None:
        assert builtin_tests._apply_test(UNDEFINED, "undefined") is True
