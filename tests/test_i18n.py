"""Tests for i18n — {% trans %}...{% endtrans %} blocks and gettext integration."""

import pytest

from kida import Environment
from kida.utils.html import Markup


class TestTransBasic:
    """{% trans %} block rendering."""

    def test_simple_trans(self, env: Environment) -> None:
        """{% trans %}Hello{% endtrans %} renders the translated string."""
        tmpl = env.from_string("{% trans %}Hello{% endtrans %}")
        assert tmpl.render() == "Hello"

    def test_simple_trans_with_mock_gettext(self) -> None:
        """Mock gettext translates the message."""
        env = Environment()
        env.install_gettext_callables(
            gettext=lambda s: "Bonjour" if s == "Hello" else s,
            ngettext=lambda s, p, n: s if n == 1 else p,
        )
        tmpl = env.from_string("{% trans %}Hello{% endtrans %}")
        assert tmpl.render() == "Bonjour"

    def test_trans_with_variables(self) -> None:
        """Variable bindings are interpolated into translated string."""
        env = Environment()
        env.install_gettext_callables(
            gettext=lambda s: "Bonjour, %(name)s!" if "%(name)s" in s else s,
            ngettext=lambda s, p, n: s if n == 1 else p,
        )
        tmpl = env.from_string("{% trans name=user_name %}Hello, {{ name }}!{% endtrans %}")
        result = tmpl.render(user_name="Alice")
        assert result == "Bonjour, Alice!"

    def test_trans_multiple_variables(self) -> None:
        """Multiple variable bindings work."""
        env = Environment()
        tmpl = env.from_string(
            "{% trans greeting=g, name=n %}{{ greeting }}, {{ name }}!{% endtrans %}"
        )
        result = tmpl.render(g="Hi", n="Bob")
        assert result == "Hi, Bob!"

    def test_trans_whitespace_normalized(self, env: Environment) -> None:
        """Whitespace in message ID is normalized."""
        tmpl = env.from_string("{% trans %}\n  Hello,\n  world!\n{% endtrans %}")
        # Identity gettext returns normalized message
        result = tmpl.render()
        assert result == "Hello, world!"


class TestTransPlural:
    """Pluralization with {% plural %}."""

    def test_plural_singular(self, env: Environment) -> None:
        """count=1 uses singular form."""
        tmpl = env.from_string(
            "{% trans count=n %}One item.{% plural %}{{ count }} items.{% endtrans %}"
        )
        assert tmpl.render(n=1) == "One item."

    def test_plural_plural(self, env: Environment) -> None:
        """count>1 uses plural form."""
        tmpl = env.from_string(
            "{% trans count=n %}One item.{% plural %}{{ count }} items.{% endtrans %}"
        )
        assert tmpl.render(n=5) == "5 items."

    def test_plural_with_mock_ngettext(self) -> None:
        """Mock ngettext translates plural forms."""
        env = Environment()
        env.install_gettext_callables(
            gettext=lambda s: s,
            ngettext=lambda s, p, n: "Un élément." if n == 1 else "%(count)s éléments.",
        )
        tmpl = env.from_string(
            "{% trans count=n %}One item.{% plural %}{{ count }} items.{% endtrans %}"
        )
        assert tmpl.render(n=3) == "3 éléments."
        assert tmpl.render(n=1) == "Un élément."


class TestTransEscaping:
    """HTML escaping interaction with translated strings."""

    def test_variable_values_escaped(self) -> None:
        """Variable values are HTML-escaped in translated string."""
        env = Environment(autoescape=True)
        tmpl = env.from_string("{% trans name=user_input %}Hello, {{ name }}!{% endtrans %}")
        result = tmpl.render(user_input="<script>alert(1)</script>")
        assert "&lt;script&gt;" in result
        assert "<script>" not in result

    def test_markup_passthrough(self) -> None:
        """Markup variable values are not double-escaped."""
        env = Environment(autoescape=True)
        tmpl = env.from_string("{% trans name=safe_html %}Hello, {{ name }}!{% endtrans %}")
        result = tmpl.render(safe_html=Markup("<b>bold</b>"))
        assert "<b>bold</b>" in result

    def test_no_variables_escaped(self) -> None:
        """Simple trans without variables escapes the translated string."""
        env = Environment(autoescape=True)
        env.install_gettext_callables(
            gettext=lambda s: "Hello & goodbye",
            ngettext=lambda s, p, n: s if n == 1 else p,
        )
        tmpl = env.from_string("{% trans %}Hello{% endtrans %}")
        result = tmpl.render()
        assert "&amp;" in result


class TestTransNoTranslations:
    """Behavior when no translations are installed (identity defaults)."""

    def test_identity_gettext(self, env: Environment) -> None:
        """Without translations, {% trans %} passes through."""
        tmpl = env.from_string("{% trans %}Hello{% endtrans %}")
        assert tmpl.render() == "Hello"

    def test_identity_ngettext_singular(self, env: Environment) -> None:
        """Without translations, singular form for count=1."""
        tmpl = env.from_string(
            "{% trans count=n %}One item.{% plural %}{{ count }} items.{% endtrans %}"
        )
        assert tmpl.render(n=1) == "One item."

    def test_identity_ngettext_plural(self, env: Environment) -> None:
        """Without translations, plural form for count!=1."""
        tmpl = env.from_string(
            "{% trans count=n %}One item.{% plural %}{{ count }} items.{% endtrans %}"
        )
        assert tmpl.render(n=5) == "5 items."

    def test_shorthand_gettext(self, env: Environment) -> None:
        """{{ _("Hello") }} uses the global _ function."""
        tmpl = env.from_string('{{ _("Hello") }}')
        assert tmpl.render() == "Hello"

    def test_shorthand_ngettext(self, env: Environment) -> None:
        """{{ _n("item", "items", count) }} uses the global _n function."""
        tmpl = env.from_string('{{ _n("item", "items", n) }}')
        assert tmpl.render(n=1) == "item"
        assert tmpl.render(n=5) == "items"


class TestTransErrors:
    """Parse-time error handling."""

    def test_undeclared_variable_raises(self, env: Environment) -> None:
        """{{ unknown }} inside {% trans %} without declaration raises error."""
        with pytest.raises(Exception, match="Undeclared variable"):
            env.from_string("{% trans %}Hello, {{ name }}!{% endtrans %}")

    def test_complex_expression_raises(self, env: Environment) -> None:
        """{{ user.name }} inside trans body raises error (undeclared)."""
        with pytest.raises(Exception, match="Undeclared variable"):
            env.from_string("{% trans %}Hello, {{ user.name }}!{% endtrans %}")

    def test_plural_without_count_raises(self, env: Environment) -> None:
        """{% plural %} without count variable raises error."""
        with pytest.raises(Exception, match="count"):
            env.from_string("{% trans name=n %}One.{% plural %}Many.{% endtrans %}")

    def test_unexpected_block_inside_trans(self, env: Environment) -> None:
        """Non-plural/endtrans block tags inside trans raise error."""
        with pytest.raises(Exception, match="Unexpected block tag"):
            env.from_string("{% trans %}{% if true %}x{% end %}{% endtrans %}")


class TestTransIntegration:
    """Integration tests for trans in various template contexts."""

    def test_trans_inside_for_loop(self, env: Environment) -> None:
        """{% trans %} works inside {% for %}."""
        tmpl = env.from_string(
            "{% for item in items %}{% trans name=item %}Hello, {{ name }}! {% endtrans %}{% end %}"
        )
        result = tmpl.render(items=["Alice", "Bob"])
        assert "Hello, Alice!" in result
        assert "Hello, Bob!" in result

    def test_trans_with_endtrans(self, env: Environment) -> None:
        """{% endtrans %} works as closing tag."""
        tmpl = env.from_string("{% trans %}Hello{% endtrans %}")
        assert tmpl.render() == "Hello"

    def test_trans_with_end(self, env: Environment) -> None:
        """{% end %} also works as closing tag."""
        tmpl = env.from_string("{% trans %}Hello{% end %}")
        assert tmpl.render() == "Hello"

    def test_trans_with_filter_expression(self) -> None:
        """Variable binding can use filter expressions."""
        env = Environment()
        tmpl = env.from_string('{% trans name="alice" | upper %}Hello, {{ name }}!{% endtrans %}')
        assert tmpl.render() == "Hello, ALICE!"

    def test_install_translations_object(self) -> None:
        """install_translations() works with gettext-like objects."""

        class MockTranslations:
            def gettext(self, message: str) -> str:
                return {"Hello": "Hola"}.get(message, message)

            def ngettext(self, singular: str, plural: str, n: int) -> str:
                return singular if n == 1 else plural

        env = Environment()
        env.install_translations(MockTranslations())
        tmpl = env.from_string("{% trans %}Hello{% endtrans %}")
        assert tmpl.render() == "Hola"
