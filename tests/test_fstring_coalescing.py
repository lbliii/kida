"""Tests for f-string coalescing optimization (RFC: fstring-code-generation).

Tests verify:
    1. Coalesceable node detection
    2. F-string AST generation correctness
    3. Output equivalence (coalesced vs non-coalesced)
    4. Edge cases (braces, backslashes, etc.)
    5. Configuration options
"""

import pytest

from kida import Environment
from kida.compiler import Compiler
from kida.compiler.coalescing import (
    _BUILTIN_PURE_FILTERS,
    COALESCE_MIN_NODES,
)
from kida.nodes import (
    BinOp,
    CondExpr,
    Const,
    Data,
    Filter,
    FuncCall,
    Getattr,
    Getitem,
    InlinedFilter,
    Name,
    Output,
    Pipeline,
)


class TestCoalesceableDetection:
    """Test _is_coalesceable() and _is_simple_expr() methods."""

    @pytest.fixture
    def env(self) -> Environment:
        """Create environment with default settings."""
        return Environment()

    @pytest.fixture
    def compiler(self, env: Environment):
        """Create compiler instance for testing."""
        from kida.compiler import Compiler

        return Compiler(env)

    def test_data_node_coalesceable(self, compiler):
        """Data nodes are always coalesceable."""
        node = Data(lineno=1, col_offset=0, value="Hello")
        assert compiler._is_coalesceable(node) is True

    def test_empty_data_coalesceable(self, compiler):
        """Empty Data nodes are coalesceable (filtered during generation)."""
        node = Data(lineno=1, col_offset=0, value="")
        assert compiler._is_coalesceable(node) is True

    def test_simple_name_coalesceable(self, compiler):
        """Simple variable output is coalesceable."""
        expr = Name(lineno=1, col_offset=0, name="user")
        node = Output(lineno=1, col_offset=0, expr=expr)
        assert compiler._is_coalesceable(node) is True

    def test_const_coalesceable(self, compiler):
        """Constant expression is coalesceable."""
        expr = Const(lineno=1, col_offset=0, value="hello")
        node = Output(lineno=1, col_offset=0, expr=expr)
        assert compiler._is_coalesceable(node) is True

    def test_getattr_coalesceable(self, compiler):
        """Attribute access is coalesceable."""
        # user.name
        expr = Getattr(
            lineno=1,
            col_offset=0,
            obj=Name(lineno=1, col_offset=0, name="user"),
            attr="name",
        )
        node = Output(lineno=1, col_offset=0, expr=expr)
        assert compiler._is_coalesceable(node) is True

    def test_nested_getattr_coalesceable(self, compiler):
        """Nested attribute access is coalesceable."""
        # user.profile.name
        inner = Getattr(
            lineno=1,
            col_offset=0,
            obj=Name(lineno=1, col_offset=0, name="user"),
            attr="profile",
        )
        expr = Getattr(lineno=1, col_offset=0, obj=inner, attr="name")
        node = Output(lineno=1, col_offset=0, expr=expr)
        assert compiler._is_coalesceable(node) is True

    def test_getitem_coalesceable(self, compiler):
        """Item access is coalesceable."""
        # items[0]
        expr = Getitem(
            lineno=1,
            col_offset=0,
            obj=Name(lineno=1, col_offset=0, name="items"),
            key=Const(lineno=1, col_offset=0, value=0),
        )
        node = Output(lineno=1, col_offset=0, expr=expr)
        assert compiler._is_coalesceable(node) is True

    def test_getitem_string_key_coalesceable(self, compiler):
        """Item access with string key is coalesceable."""
        # data["key"]
        expr = Getitem(
            lineno=1,
            col_offset=0,
            obj=Name(lineno=1, col_offset=0, name="data"),
            key=Const(lineno=1, col_offset=0, value="key"),
        )
        node = Output(lineno=1, col_offset=0, expr=expr)
        assert compiler._is_coalesceable(node) is True

    def test_pure_filter_coalesceable(self, compiler):
        """Output with pure filter is coalesceable."""
        # name | upper
        expr = Filter(
            lineno=1,
            col_offset=0,
            value=Name(lineno=1, col_offset=0, name="name"),
            name="upper",
        )
        node = Output(lineno=1, col_offset=0, expr=expr)
        assert compiler._is_coalesceable(node) is True

    def test_pure_filter_with_simple_args_coalesceable(self, compiler):
        """Pure filter with simple arguments is coalesceable."""
        # name | default("N/A")
        expr = Filter(
            lineno=1,
            col_offset=0,
            value=Name(lineno=1, col_offset=0, name="name"),
            name="default",
            args=(Const(lineno=1, col_offset=0, value="N/A"),),
        )
        node = Output(lineno=1, col_offset=0, expr=expr)
        assert compiler._is_coalesceable(node) is True

    def test_pure_filter_with_kwargs_coalesceable(self, compiler):
        """Pure filter with keyword arguments is coalesceable."""
        # name | truncate(length=10)
        expr = Filter(
            lineno=1,
            col_offset=0,
            value=Name(lineno=1, col_offset=0, name="name"),
            name="truncate",
            kwargs={"length": Const(lineno=1, col_offset=0, value=10)},
        )
        node = Output(lineno=1, col_offset=0, expr=expr)
        assert compiler._is_coalesceable(node) is True

    def test_impure_filter_not_coalesceable(self, compiler):
        """Output with impure/unknown filter is not coalesceable."""
        # name | custom_filter
        expr = Filter(
            lineno=1,
            col_offset=0,
            value=Name(lineno=1, col_offset=0, name="name"),
            name="custom_filter",
        )
        node = Output(lineno=1, col_offset=0, expr=expr)
        assert compiler._is_coalesceable(node) is False

    def test_pipeline_all_pure_coalesceable(self, compiler):
        """Pipeline with all pure steps is coalesceable."""
        # name |> upper |> trim
        expr = Pipeline(
            lineno=1,
            col_offset=0,
            value=Name(lineno=1, col_offset=0, name="name"),
            steps=(
                ("upper", (), {}),
                ("trim", (), {}),
            ),
        )
        node = Output(lineno=1, col_offset=0, expr=expr)
        assert compiler._is_coalesceable(node) is True

    def test_pipeline_impure_step_not_coalesceable(self, compiler):
        """Pipeline with impure step is not coalesceable."""
        # name |> upper |> custom
        expr = Pipeline(
            lineno=1,
            col_offset=0,
            value=Name(lineno=1, col_offset=0, name="name"),
            steps=(
                ("upper", (), {}),
                ("custom", (), {}),
            ),
        )
        node = Output(lineno=1, col_offset=0, expr=expr)
        assert compiler._is_coalesceable(node) is False

    def test_funccall_not_coalesceable(self, compiler):
        """Function calls are not coalesceable."""
        # myfunc(x)
        expr = FuncCall(
            lineno=1,
            col_offset=0,
            func=Name(lineno=1, col_offset=0, name="myfunc"),
            args=(Name(lineno=1, col_offset=0, name="x"),),
        )
        node = Output(lineno=1, col_offset=0, expr=expr)
        assert compiler._is_coalesceable(node) is False

    def test_condexpr_not_coalesceable(self, compiler):
        """Conditional expressions are not coalesceable."""
        # a if cond else b
        expr = CondExpr(
            lineno=1,
            col_offset=0,
            test=Name(lineno=1, col_offset=0, name="cond"),
            if_true=Name(lineno=1, col_offset=0, name="a"),
            if_false=Name(lineno=1, col_offset=0, name="b"),
        )
        node = Output(lineno=1, col_offset=0, expr=expr)
        assert compiler._is_coalesceable(node) is False

    def test_binop_not_coalesceable(self, compiler):
        """Binary operations are not coalesceable."""
        # a + b
        expr = BinOp(
            lineno=1,
            col_offset=0,
            op="+",
            left=Name(lineno=1, col_offset=0, name="a"),
            right=Name(lineno=1, col_offset=0, name="b"),
        )
        node = Output(lineno=1, col_offset=0, expr=expr)
        assert compiler._is_coalesceable(node) is False

    def test_custom_pure_filter_coalesceable(self):
        """User-registered pure filter is coalesceable."""
        env = Environment()
        env.pure_filters.add("my_pure")

        from kida.compiler import Compiler

        compiler = Compiler(env)

        expr = Filter(
            lineno=1,
            col_offset=0,
            value=Name(lineno=1, col_offset=0, name="x"),
            name="my_pure",
        )
        node = Output(lineno=1, col_offset=0, expr=expr)
        assert compiler._is_coalesceable(node) is True

    def test_inlined_filter_coalesceable(self, compiler):
        """InlinedFilter expressions are coalesceable."""
        # name.upper() equivalent
        expr = InlinedFilter(
            lineno=1,
            col_offset=0,
            value=Name(lineno=1, col_offset=0, name="name"),
            method="upper",
        )
        node = Output(lineno=1, col_offset=0, expr=expr)
        assert compiler._is_coalesceable(node) is True


class TestBackslashDetection:
    """Test backslash detection in expressions."""

    @pytest.fixture
    def compiler(self) -> Compiler:
        return Compiler(Environment())

    def test_backslash_in_const_detected(self, compiler):
        """Backslash in string constant is detected."""
        expr = Const(lineno=1, col_offset=0, value="path\\to\\file")
        node = Output(lineno=1, col_offset=0, expr=expr)
        assert compiler._is_coalesceable(node) is False

    def test_no_backslash_in_const(self, compiler):
        """String without backslash is coalesceable."""
        expr = Const(lineno=1, col_offset=0, value="path/to/file")
        node = Output(lineno=1, col_offset=0, expr=expr)
        assert compiler._is_coalesceable(node) is True

    def test_backslash_in_filter_arg_detected(self, compiler):
        """Backslash in filter argument is detected."""
        expr = Filter(
            lineno=1,
            col_offset=0,
            value=Name(lineno=1, col_offset=0, name="x"),
            name="default",
            args=(Const(lineno=1, col_offset=0, value="C:\\path"),),
        )
        node = Output(lineno=1, col_offset=0, expr=expr)
        assert compiler._is_coalesceable(node) is False


class TestFStringGeneration:
    """Test _compile_coalesced_output() method."""

    @pytest.fixture
    def env(self) -> Environment:
        return Environment()

    def test_simple_coalesce_two_data(self, env):
        """Two Data nodes coalesce into single f-string."""
        template = env.from_string("Hello World")
        result = template.render()
        assert result == "Hello World"

    def test_coalesce_data_and_output(self, env):
        """Data + Output coalesces correctly."""
        template = env.from_string("Hello, {{ name }}!")
        result = template.render(name="World")
        assert result == "Hello, World!"

    def test_coalesce_multiple_outputs(self, env):
        """Multiple outputs coalesce with interpolation."""
        template = env.from_string("{{ a }}{{ b }}{{ c }}")
        result = template.render(a="1", b="2", c="3")
        assert result == "123"

    def test_escape_function_called(self, env):
        """Escaped outputs use _e() function."""
        template = env.from_string("{{ html }}")
        result = template.render(html="<b>bold</b>")
        assert result == "&lt;b&gt;bold&lt;/b&gt;"

    def test_safe_output_uses_str(self, env):
        """Non-escaped outputs use _s() function."""
        from kida.utils.html import Markup

        template = env.from_string("{{ html | safe }}")
        result = template.render(html=Markup("<b>bold</b>"))
        assert result == "<b>bold</b>"


class TestBraceHandling:
    """Test brace handling in f-strings."""

    @pytest.fixture
    def env(self) -> Environment:
        return Environment()

    def test_brace_in_literal_preserved(self, env):
        """Braces in literal text are output correctly."""
        template = env.from_string("body { color: red }")
        result = template.render()
        assert result == "body { color: red }"

    def test_css_braces_preserved(self, env):
        """CSS with braces renders correctly."""
        css = "<style>body { margin: 0 } .box { padding: 10px }</style>"
        template = env.from_string(css)
        result = template.render()
        assert result == css

    def test_json_braces_preserved(self, env):
        """JSON with braces renders correctly."""
        json_str = '{"name": "test", "value": 42}'
        template = env.from_string(json_str)
        result = template.render()
        assert result == json_str

    def test_mixed_braces_and_variables(self, env):
        """Braces in literal text with variables work correctly."""
        template = env.from_string("<style>.{{ cls }} { color: {{ color }} }</style>")
        result = template.render(cls="box", color="red")
        assert result == "<style>.box { color: red }</style>"

    def test_multiple_braces_in_literal(self, env):
        """Multiple braces in literal text work correctly."""
        # Test brace patterns that might trip up f-string generation
        template = env.from_string("function() { if (x) { return y; } }")
        result = template.render()
        assert result == "function() { if (x) { return y; } }"


class TestEdgeCases:
    """Test edge cases for f-string coalescing."""

    @pytest.fixture
    def env(self) -> Environment:
        return Environment()

    def test_single_node_not_coalesced(self, env):
        """Single coalesceable node uses normal compilation."""
        # Single node shouldn't trigger coalescing (threshold is 2)
        template = env.from_string("{{ x }}")
        result = template.render(x="hello")
        assert result == "hello"

    def test_empty_data_skipped(self, env):
        """Empty Data nodes don't create empty constants."""
        template = env.from_string("{{ a }}{{ b }}")
        result = template.render(a="1", b="2")
        assert result == "12"

    def test_disabled_optimization(self):
        """fstring_coalescing=False disables coalescing."""
        env = Environment(fstring_coalescing=False)
        template = env.from_string("{{ a }}{{ b }}")
        result = template.render(a="1", b="2")
        assert result == "12"  # Output should still be correct

    def test_attribute_access(self, env):
        """Attribute access in coalesced output."""
        template = env.from_string("Name: {{ user.name }}")
        result = template.render(user={"name": "Alice"})
        assert result == "Name: Alice"

    def test_item_access(self, env):
        """Item access in coalesced output."""
        template = env.from_string("First: {{ items[0] }}")
        result = template.render(items=["a", "b", "c"])
        assert result == "First: a"

    def test_filter_in_coalesced(self, env):
        """Pure filter in coalesced output."""
        template = env.from_string("Name: {{ name | upper }}")
        result = template.render(name="alice")
        assert result == "Name: ALICE"


class TestIntegration:
    """Integration tests for coalesced vs non-coalesced output."""

    @pytest.fixture
    def env_coalesced(self) -> Environment:
        return Environment(fstring_coalescing=True)

    @pytest.fixture
    def env_non_coalesced(self) -> Environment:
        return Environment(fstring_coalescing=False)

    def test_output_matches_non_coalesced(self, env_coalesced, env_non_coalesced):
        """Coalesced template produces identical output."""
        source = '<div id="{{ item.id }}">{{ item.name }}</div>'
        ctx = {"item": {"id": "123", "name": "Test"}}

        result_coalesced = env_coalesced.from_string(source).render(**ctx)
        result_non_coalesced = env_non_coalesced.from_string(source).render(**ctx)

        assert result_coalesced == result_non_coalesced
        assert result_coalesced == '<div id="123">Test</div>'

    def test_loop_body_coalesced(self, env_coalesced):
        """Loop body with consecutive outputs is coalesced."""
        source = "{% for item in items %}<li>{{ item.id }}: {{ item.name }}</li>{% end %}"
        ctx = {"items": [{"id": "1", "name": "A"}, {"id": "2", "name": "B"}]}
        result = env_coalesced.from_string(source).render(**ctx)
        assert result == "<li>1: A</li><li>2: B</li>"

    def test_control_flow_breaks_coalescing(self, env_coalesced):
        """Control flow creates separate coalescing groups."""
        source = (
            "<span>{{ a }}</span>{% if show %}<span>{{ b }}</span>{% end %}<span>{{ c }}</span>"
        )
        ctx = {"a": "1", "b": "2", "c": "3", "show": True}
        result = env_coalesced.from_string(source).render(**ctx)
        assert result == "<span>1</span><span>2</span><span>3</span>"

    def test_control_flow_breaks_coalescing_false(self, env_coalesced):
        """Control flow with false condition."""
        source = (
            "<span>{{ a }}</span>{% if show %}<span>{{ b }}</span>{% end %}<span>{{ c }}</span>"
        )
        ctx = {"a": "1", "b": "2", "c": "3", "show": False}
        result = env_coalesced.from_string(source).render(**ctx)
        assert result == "<span>1</span><span>3</span>"

    def test_nested_loops(self, env_coalesced):
        """Nested loops with outputs work correctly."""
        source = (
            """{% for row in rows %}{% for col in cols %}[{{ row }},{{ col }}]{% end %}{% end %}"""
        )
        ctx = {"rows": [1, 2], "cols": ["a", "b"]}
        result = env_coalesced.from_string(source).render(**ctx)
        assert result == "[1,a][1,b][2,a][2,b]"

    def test_block_inheritance(self):
        """Block inheritance with coalescing."""
        from kida.environment.loaders import DictLoader

        env = Environment(
            fstring_coalescing=True,
            loader=DictLoader(
                {
                    "base.html": "<html>{% block content %}{% end %}</html>",
                    "child.html": '{% extends "base.html" %}{% block content %}<div>{{ title }}</div>{% end %}',
                }
            ),
        )

        result = env.get_template("child.html").render(title="Hello")
        assert result == "<html><div>Hello</div></html>"

    def test_html_escaping_preserved(self, env_coalesced):
        """HTML escaping is preserved in coalesced output."""
        source = "<div>{{ content }}</div>"
        ctx = {"content": "<script>alert('xss')</script>"}
        result = env_coalesced.from_string(source).render(**ctx)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_complex_template(self, env_coalesced, env_non_coalesced):
        """Complex template with mixed content produces identical output."""
        source = """
<div class="card">
    <h1>{{ title | upper }}</h1>
    {% for item in items %}
    <div class="item" id="item-{{ item.id }}">
        <span>{{ item.name }}</span>
        {% if item.active %}
        <span class="badge">Active</span>
        {% end %}
    </div>
    {% end %}
</div>
"""
        ctx = {
            "title": "Products",
            "items": [
                {"id": 1, "name": "Widget", "active": True},
                {"id": 2, "name": "Gadget", "active": False},
            ],
        }

        result_coalesced = env_coalesced.from_string(source).render(**ctx)
        result_non_coalesced = env_non_coalesced.from_string(source).render(**ctx)

        assert result_coalesced == result_non_coalesced


class TestBuiltinPureFilters:
    """Test that built-in pure filters are correctly defined."""

    def test_pure_filters_exist(self):
        """Verify _BUILTIN_PURE_FILTERS contains expected filters."""
        expected = {
            "upper",
            "lower",
            "title",
            "capitalize",
            "trim",
            "strip",
            "escape",
            "e",
            "default",
            "d",
            "length",
            "first",
            "last",
        }
        for f in expected:
            assert f in _BUILTIN_PURE_FILTERS, f"{f} should be in pure filters"

    def test_coalesce_min_nodes_threshold(self):
        """Verify COALESCE_MIN_NODES is set correctly."""
        assert COALESCE_MIN_NODES == 2


class TestPipelineCoalescing:
    """Test pipeline expression coalescing."""

    @pytest.fixture
    def env(self) -> Environment:
        return Environment()

    def test_pipeline_pure_filters(self, env):
        """Pipeline with pure filters is coalesced."""
        template = env.from_string("{{ name |> upper |> trim }}")
        result = template.render(name="  hello  ")
        assert result == "HELLO"

    def test_pipeline_in_html(self, env):
        """Pipeline in HTML context."""
        template = env.from_string("<span>{{ name |> upper }}</span>")
        result = template.render(name="alice")
        assert result == "<span>ALICE</span>"
