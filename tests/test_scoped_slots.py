"""Tests for scoped slots — let: bindings on {% slot %} tags."""

from kida import DictLoader, Environment


class TestBasicScopedSlots:
    """Basic scoped slot functionality."""

    def test_single_binding(self, env: Environment) -> None:
        """Slot exposes a single variable to the caller."""
        tmpl = env.from_string(
            "{% def items(data) %}"
            "{% for item in data %}"
            "{% slot row let:item=item %}{{ item }}{% end %}"
            "{% end %}"
            "{% end %}"
            "{% call items(['a', 'b', 'c']) %}"
            "{% slot row let:item %}[{{ item }}]{% end %}"
            "{% end %}"
        )
        assert tmpl.render() == "[a][b][c]"

    def test_multiple_bindings(self, env: Environment) -> None:
        """Slot exposes multiple variables."""
        tmpl = env.from_string(
            "{% def items(data) %}"
            "{% for item in data %}"
            "{% slot row let:item=item, let:idx=loop.index %}{{ item }}{% end %}"
            "{% end %}"
            "{% end %}"
            "{% call items(['x', 'y']) %}"
            "{% slot row let:item, let:idx %}{{ idx }}:{{ item }}{% end %}"
            "{% end %}"
        )
        assert tmpl.render() == "1:x2:y"

    def test_default_content_with_bindings(self, env: Environment) -> None:
        """Default slot content uses the bindings when no call-site override."""
        tmpl = env.from_string(
            "{% def items(data) %}"
            "{% for item in data %}"
            "{% slot row let:item=item %}({{ item }}){% end %}"
            "{% end %}"
            "{% end %}"
            "{{ items(['a', 'b']) }}"
        )
        assert tmpl.render() == "(a)(b)"

    def test_no_bindings_still_works(self, env: Environment) -> None:
        """Slots without let: bindings work exactly as before."""
        tmpl = env.from_string(
            "{% def box() %}<div>{% slot %}</div>{% end %}{% call box() %}content{% end %}"
        )
        assert tmpl.render() == "<div>content</div>"

    def test_binding_expression(self, env: Environment) -> None:
        """Binding values can be arbitrary expressions."""
        tmpl = env.from_string(
            "{% def items(data) %}"
            "{% for item in data %}"
            "{% slot row let:upper=item|upper %}{{ item }}{% end %}"
            "{% end %}"
            "{% end %}"
            "{% call items(['hello']) %}"
            "{% slot row let:upper %}{{ upper }}{% end %}"
            "{% end %}"
        )
        assert tmpl.render() == "HELLO"


class TestNamedScopedSlots:
    """Scoped slots with named slots."""

    def test_different_slots_different_bindings(self, env: Environment) -> None:
        """Different named slots can expose different data."""
        tmpl = env.from_string(
            "{% def table(rows) %}"
            "<table>"
            "{% slot header %}"
            "{% for row in rows %}"
            "<tr>{% slot cell let:row=row %}{{ row }}{% end %}</tr>"
            "{% end %}"
            "</table>"
            "{% end %}"
            "{% call table(['a', 'b']) %}"
            "{% slot header %}<th>Header</th>{% end %}"
            "{% slot cell let:row %}<td>[{{ row }}]</td>{% end %}"
            "{% end %}"
        )
        assert (
            tmpl.render()
            == "<table><th>Header</th><tr><td>[a]</td></tr><tr><td>[b]</td></tr></table>"
        )


class TestScopedSlotEdgeCases:
    """Edge cases and interaction with other features."""

    def test_nested_scoped_slots(self) -> None:
        """Inner and outer components both expose scoped bindings."""
        loader = DictLoader(
            {
                "outer.html": (
                    "{% def outer(items) %}"
                    "{% for item in items %}"
                    "{% slot row let:item=item %}{{ item }}{% end %}"
                    "{% end %}"
                    "{% end %}"
                ),
                "page.html": (
                    "{% from 'outer.html' import outer %}"
                    "{% call outer(['a', 'b']) %}"
                    "{% slot row let:item %}({{ item }}){% end %}"
                    "{% end %}"
                ),
            }
        )
        env = Environment(loader=loader)
        assert env.get_template("page.html").render() == "(a)(b)"

    def test_scoped_slot_with_provide_consume(self, env: Environment) -> None:
        """Scoped slots and provide/consume coexist."""
        tmpl = env.from_string(
            "{% def items(data) %}"
            "{% provide theme='dark' %}"
            "{% for item in data %}"
            "{% slot row let:item=item %}{{ item }}{% end %}"
            "{% end %}"
            "{% end %}"
            "{% end %}"
            "{% call items(['x']) %}"
            "{% slot row let:item %}{{ item }}-{{ consume('theme') }}{% end %}"
            "{% end %}"
        )
        assert tmpl.render() == "x-dark"

    def test_scoped_slot_no_params_ignores_kwargs(self, env: Environment) -> None:
        """Slot body without let: params still works when def passes bindings."""
        tmpl = env.from_string(
            "{% def items(data) %}"
            "{% for item in data %}"
            "{% slot row let:item=item %}{{ item }}{% end %}"
            "{% end %}"
            "{% end %}"
            "{% call items(['a', 'b']) %}"
            "{% slot row %}fixed{% end %}"
            "{% end %}"
        )
        # The slot body ignores the bindings — just renders "fixed" for each row
        assert tmpl.render() == "fixedfixed"

    def test_scoped_slot_default_slot(self, env: Environment) -> None:
        """Default (unnamed) slot with scoped bindings."""
        tmpl = env.from_string(
            "{% def items(data) %}"
            "{% for item in data %}"
            "{% slot let:item=item %}{{ item }}{% end %}"
            "{% end %}"
            "{% end %}"
            "{% call items(['a', 'b']) %}"
            "[{{ item }}]"
            "{% end %}"
        )
        # Default slot content receives scoped bindings
        assert tmpl.render() == "[a][b]"

    def test_multiple_binding_refs_not_cached(self, env: Environment) -> None:
        """Regression: CSE must not cache let: binding vars across slot boundary.

        When a scoped binding variable is referenced more than once in the
        slot body, the CSE optimisation previously hoisted the lookup to
        function entry — before _slot_kwargs were pushed onto the scope
        stack — causing UndefinedError.  (GitHub #70)
        """
        tmpl = env.from_string(
            "{% def datatable(items) %}"
            "{% for item in items %}"
            "{% slot row let:row=item %}{{ row.name }}{% end %}"
            "{% end %}"
            "{% end %}"
            "{% call datatable(items=[{'name': 'Alice', 'age': 30},"
            " {'name': 'Bob', 'age': 25}]) %}"
            "{% slot row let:row %}{{ row.name }} ({{ row.age }}){% end %}"
            "{% end %}"
        )
        assert tmpl.render() == "Alice (30)Bob (25)"

    def test_multiple_binding_refs_cross_template(self) -> None:
        """Regression: scoped slot bindings work across template imports.

        Same CSE issue as test_multiple_binding_refs_not_cached, but with
        the def imported from a separate template.  (GitHub #70)
        """
        loader = DictLoader(
            {
                "components.html": (
                    "{% def datatable(items) %}"
                    "{% for item in items %}"
                    "{% slot row let:row=item %}{{ row.name }}{% end %}"
                    "{% end %}"
                    "{% end %}"
                ),
                "page.html": (
                    "{% from 'components.html' import datatable %}"
                    "{% call datatable(items=users) %}"
                    "{% slot row let:row %}{{ row.name }} ({{ row.age }}){% end %}"
                    "{% end %}"
                ),
            }
        )
        env = Environment(loader=loader)
        result = env.get_template("page.html").render(
            users=[{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
        )
        assert result == "Alice (30)Bob (25)"

    def test_binding_name_shadows_outer_cached_var(self, env: Environment) -> None:
        """Regression: slot binding must override an outer variable of the same name.

        If a variable is referenced unconditionally outside the call block
        (making it CSE-cacheable) AND used as a let: binding name inside a
        slot body, the slot body must resolve via _lookup_scope (seeing the
        scoped value), not via the cached _cv_<name> closure.  (GitHub #70)
        """
        tmpl = env.from_string(
            "{% def wrapper(items) %}"
            "{% for item in items %}"
            "{% slot row let:row=item %}{{ row }}{% end %}"
            "{% end %}"
            "{% end %}"
            "{{ row }}|{{ row }}|"
            "{% call wrapper(items=['X', 'Y']) %}"
            "{% slot row let:row %}[{{ row }}]{% end %}"
            "{% end %}"
        )
        # 'row' is referenced 2x unconditionally (cached), but inside
        # the slot body it must resolve to the let: binding, not the cache.
        result = tmpl.render(row="OUTER")
        assert result == "OUTER|OUTER|[X][Y]"

    def test_loop_index_binding(self, env: Environment) -> None:
        """Common pattern: expose loop.index alongside item."""
        tmpl = env.from_string(
            "{% def numbered_list(items) %}"
            "<ol>"
            "{% for item in items %}"
            "{% slot row let:item=item, let:index=loop.index, let:first=loop.first %}"
            "<li>{{ item }}</li>"
            "{% end %}"
            "{% end %}"
            "</ol>"
            "{% end %}"
            "{% call numbered_list(['a', 'b', 'c']) %}"
            "{% slot row let:item, let:index, let:first %}"
            "<li class=\"{{ 'first' if first }}\">{{ index }}. {{ item }}</li>"
            "{% end %}"
            "{% end %}"
        )
        result = tmpl.render()
        assert '<li class="first">1. a</li>' in result
        assert '<li class="">2. b</li>' in result
