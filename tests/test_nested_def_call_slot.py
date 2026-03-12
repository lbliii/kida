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

    def test_nested_empty_slot_passthrough_to_outer_caller(self) -> None:
        """Empty slot in block passed to inner macro delegates to outer caller (resource_index pattern).

        Page → resource_index → filter_bar. Block has {% slot filter_controls %}{% end %}
        (empty). When filter_bar renders {% slot filter_controls %}, it should get the
        page's slot content, not the block's empty default.
        """
        loader = DictLoader(
            {
                "filter_bar.html": (
                    "{% def filter_bar(action) %}"
                    '<form class="filter-bar" action="{{ action }}">'
                    '<div class="controls">{% slot filter_controls %}</div>'
                    '<div class="actions">{% slot filter_actions %}</div>'
                    "</form>"
                    "{% end %}"
                ),
                "resource_index.html": (
                    "{% from 'filter_bar.html' import filter_bar %}"
                    "{% def resource_index(title, filter_action) %}"
                    '<div class="resource-index">'
                    "<h1>{{ title }}</h1>"
                    "{% if filter_action %}"
                    "{% call filter_bar(filter_action) %}"
                    "{% slot filter_controls %}{% end %}"
                    "{% slot filter_actions %}{% end %}"
                    "{% end %}"
                    "{% endif %}"
                    '<div class="results">{% slot %}</div>'
                    "</div>"
                    "{% end %}"
                ),
                "page.html": (
                    '{% from "resource_index.html" import resource_index %}'
                    "{% call resource_index('Skills', '/skills') %}"
                    "{% slot filter_controls %}<button>Filters</button>{% end %}"
                    '{% slot filter_actions %}<a href="#">Clear</a>{% end %}'
                    "<article>Skill A</article>"
                    "{% end %}"
                ),
            }
        )
        env = Environment(loader=loader)
        page = env.get_template("page.html")
        html = page.render()
        assert "filter-bar" in html
        assert "<button>Filters</button>" in html
        assert 'href="#"' in html
        assert "Clear" in html
        assert "Skill A" in html
