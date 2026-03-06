"""Regression test for nested def→call→slot (wrapper macro pattern)."""

from kida import DictLoader, Environment


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

    def test_nested_def_call_cross_template(self) -> None:
        """Wrapper imports inner from another template - like wizard_form→safe_region."""
        loader = DictLoader(
            {
                "inner.html": "{% def inner() %}<div>{% slot %}</div>{% end %}",
                "wrapper.html": (
                    "{% from 'inner.html' import inner %}"
                    "{% def wrapper() %}"
                    "{% call inner() %}"
                    "{% slot %}{{ caller() }}{% end %}"
                    "{% end %}"
                    "{% end %}"
                    "{% call wrapper() %}Content{% end %}"
                ),
            }
        )
        env = Environment(loader=loader)
        tmpl = env.get_template("wrapper.html")
        result = tmpl.render()
        assert result == "<div>Content</div>"

    def test_nested_def_call_default_slot_no_block(self) -> None:
        """Call with caller() in default slot (no {% slot %} block) - like wizard_form."""
        loader = DictLoader(
            {
                "inner.html": "{% def inner() %}<div>{% slot %}</div>{% end %}",
                "wrapper.html": (
                    "{% from 'inner.html' import inner %}"
                    "{% def wrapper() %}"
                    "{% call inner() %}"
                    "<p>prefix</p><div>{{ caller() }}</div>"
                    "{% end %}"
                    "{% end %}"
                    "{% call wrapper() %}Content{% end %}"
                ),
            }
        )
        env = Environment(loader=loader)
        tmpl = env.get_template("wrapper.html")
        result = tmpl.render()
        assert "<p>prefix</p>" in result
        assert "<div>Content</div>" in result
