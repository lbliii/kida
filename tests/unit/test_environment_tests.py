import pytest

from kida.environment import tests as builtin_tests


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
