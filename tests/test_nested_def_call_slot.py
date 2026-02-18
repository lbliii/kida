"""Regression test for nested def→call→slot (wrapper macro pattern)."""

from kida import Environment


class TestNestedDefCallSlot:
    """Def wrapping call with slot block - used by chirp-ui state primitives."""

    def test_nested_def_call_slot_three_end(self, env: Environment) -> None:
        """Wrapper macro: def contains call contains slot block. Needs 3 {% end %}."""
        tmpl = env.from_string(
            "{% def inner() %}<div>{% slot %}</div>{% end %}"
            "{% def wrapper() %}"
            "{% call inner() %}"
            "{% slot %}{{ caller() }}{% end %}"
            "{% end %}"
            "{% end %}"
            "{% call wrapper() %}Content{% end %}"
        )
        result = tmpl.render()
        assert result == "<div>Content</div>"
