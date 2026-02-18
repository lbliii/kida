"""Test advanced Kida template features.

Tests for Kida-native features:
- {% def %} - functions with lexical scoping
- {% call %} / {% slot %} - component patterns
- {% capture %} - capture block content to variable
- {% cache %} - fragment caching
- {% filter %} - apply filter to block content
"""

import pytest

from kida import DictLoader, Environment


@pytest.fixture
def env():
    """Create a Kida environment for testing."""
    return Environment()


@pytest.fixture
def env_no_autoescape():
    """Create a Kida environment without autoescaping."""
    return Environment(autoescape=False)


# =============================================================================
# {% def %} - Kida functions with lexical scoping
# =============================================================================


class TestDefBasics:
    """Basic {% def %} functionality."""

    def test_simple_def(self, env):
        """Simple function definition and call."""
        tmpl = env.from_string(
            "{% def greet(name) %}Hello {{ name }}!{% enddef %}{{ greet('World') }}"
        )
        assert tmpl.render() == "Hello World!"

    def test_def_with_end(self, env):
        """Function using unified {% end %} closing."""
        tmpl = env.from_string(
            "{% def greet(name) %}Hello {{ name }}!{% end %}{{ greet('World') }}"
        )
        assert tmpl.render() == "Hello World!"

    def test_def_no_args(self, env):
        """Function with no arguments."""
        tmpl = env.from_string("{% def hello() %}Hello!{% enddef %}{{ hello() }}")
        assert tmpl.render() == "Hello!"

    def test_def_multiple_args(self, env):
        """Function with multiple arguments."""
        tmpl = env.from_string(
            "{% def greet(first, last) %}Hello {{ first }} {{ last }}!{% enddef %}"
            "{{ greet('John', 'Doe') }}"
        )
        assert tmpl.render() == "Hello John Doe!"

    def test_def_with_defaults(self, env):
        """Function with default argument values."""
        tmpl = env.from_string(
            "{% def greet(name='World') %}Hello {{ name }}!{% enddef %}{{ greet() }}"
        )
        assert tmpl.render() == "Hello World!"

    def test_def_override_defaults(self, env):
        """Override function default arguments."""
        tmpl = env.from_string(
            "{% def greet(name='World') %}Hello {{ name }}!{% enddef %}{{ greet('User') }}"
        )
        assert tmpl.render() == "Hello User!"


class TestDefScoping:
    """{% def %} lexical scoping - functions can access outer scope."""

    def test_access_outer_scope(self, env):
        """Function can access outer scope variables."""
        tmpl = env.from_string(
            "{% set title = 'Welcome' %}"
            "{% def card(content) %}"
            "<div>{{ title }}: {{ content }}</div>"
            "{% enddef %}"
            "{{ card('Hello') }}"
        )
        assert tmpl.render() == "<div>Welcome: Hello</div>"

    def test_access_context_vars(self, env):
        """Function can access template context variables."""
        tmpl = env.from_string("{% def show() %}Site: {{ site_name }}{% enddef %}{{ show() }}")
        assert tmpl.render(site_name="Bengal") == "Site: Bengal"

    def test_arg_shadows_outer(self, env):
        """Function argument shadows outer variable."""
        tmpl = env.from_string(
            "{% set name = 'outer' %}"
            "{% def greet(name) %}{{ name }}{% enddef %}"
            "{{ greet('inner') }}"
        )
        assert tmpl.render() == "inner"


class TestDefNested:
    """Nested function definitions."""

    def test_nested_def(self, env):
        """Function defined inside another function."""
        tmpl = env.from_string(
            "{% def outer(text) %}"
            "{% def inner(x) %}[{{ x }}]{% enddef %}"
            "{{ inner(text) }}"
            "{% enddef %}"
            "{{ outer('test') }}"
        )
        assert "[test]" in tmpl.render()

    def test_recursive_def(self, env):
        """Recursive function call."""
        tmpl = env.from_string(
            "{% def countdown(n) %}"
            "{{ n }}"
            "{% if n > 0 %}{{ countdown(n - 1) }}{% endif %}"
            "{% enddef %}"
            "{{ countdown(3) }}"
        )
        result = tmpl.render()
        assert "3" in result and "2" in result and "1" in result and "0" in result


# =============================================================================
# {% call %} / {% slot %} - Component patterns
# =============================================================================


class TestCallSlot:
    """{% call %} and {% slot %} for component patterns."""

    def test_simple_call_slot(self, env):
        """Basic call/slot pattern for components."""
        tmpl = env.from_string(
            "{% def wrapper() %}"
            "<div class='wrapper'>{% slot %}</div>"
            "{% enddef %}"
            "{% call wrapper() %}Content here{% endcall %}"
        )
        result = tmpl.render()
        assert result == "<div class='wrapper'>Content here</div>"

    def test_call_slot_with_end(self, env):
        """Call block using unified {% end %} closing."""
        tmpl = env.from_string(
            "{% def box() %}<box>{% slot %}</box>{% end %}{% call box() %}Inside{% end %}"
        )
        assert tmpl.render() == "<box>Inside</box>"

    def test_call_with_args(self, env):
        """Call passing arguments to function."""
        tmpl = env.from_string(
            "{% def card(title) %}"
            "<div class='card'><h2>{{ title }}</h2>{% slot %}</div>"
            "{% enddef %}"
            "{% call card('My Card') %}<p>Card content</p>{% endcall %}"
        )
        result = tmpl.render()
        assert "<h2>My Card</h2>" in result
        assert "<p>Card content</p>" in result

    def test_nested_calls(self, env):
        """Nested call blocks."""
        tmpl = env.from_string(
            "{% def outer() %}<outer>{% slot %}</outer>{% enddef %}"
            "{% def inner() %}<inner>{% slot %}</inner>{% enddef %}"
            "{% call outer() %}{% call inner() %}Content{% endcall %}{% endcall %}"
        )
        result = tmpl.render()
        assert result == "<outer><inner>Content</inner></outer>"

    def test_slot_not_rendered_without_call(self, env):
        """Slot is empty when function called directly (not via call block)."""
        tmpl = env.from_string("{% def box() %}[{% slot %}]{% enddef %}{{ box() }}")
        assert tmpl.render() == "[]"


class TestNamedSlots:
    """Named slots in {% call %} blocks."""

    def test_named_slot_in_call(self, env):
        """Slot blocks assign content to named slots; other content goes to default."""
        tmpl = env.from_string(
            "{% def card() %}"
            "[header:{% slot header %}][body:{% slot %}]"
            "{% end %}"
            "{% call card() %}"
            "{% slot header %}X{% end %}Y"
            "{% end %}"
        )
        assert tmpl.render() == "[header:X][body:Y]"

    def test_slot_placeholder_by_name(self, env):
        """Def with {% slot header %} and {% slot %}; call with named slots."""
        tmpl = env.from_string(
            "{% def card(title) %}"
            "<article><h2>{{ title }}</h2>"
            "<div class='actions'>{% slot header_actions %}</div>"
            "<div class='body'>{% slot %}</div></article>"
            "{% end %}"
            "{% call card('Settings') %}"
            "{% slot header_actions %}<button>⋯</button>{% end %}"
            "<p>Body content.</p>"
            "{% end %}"
        )
        result = tmpl.render()
        assert "<h2>Settings</h2>" in result
        assert "<button>⋯</button>" in result
        assert "<p>Body content.</p>" in result

    def test_backward_compat_single_body(self, env):
        """Existing {% call x() %}body{% end %} still works (no slot blocks)."""
        tmpl = env.from_string(
            "{% def box() %}<div>{% slot %}</div>{% end %}{% call box() %}Content{% end %}"
        )
        assert tmpl.render() == "<div>Content</div>"

    def test_caller_with_named_slot(self, env):
        """caller('slot_name') returns named slot content when invoked from def body."""
        tmpl = env.from_string(
            "{% def card() %}"
            "<div class='header'>{{ caller('header') }}</div>"
            "<div class='body'>{{ caller() }}</div>"
            "{% end %}"
            "{% call card() %}"
            "{% slot header %}Title{% end %}"
            "Body content"
            "{% end %}"
        )
        result = tmpl.render()
        assert "Title" in result
        assert "Body content" in result
        assert "<div class='header'>" in result
        assert "<div class='body'>" in result


# =============================================================================
# {% capture %} - Capture block to variable
# =============================================================================


class TestCapture:
    """{% capture %} to capture block content to a variable."""

    def test_simple_capture(self, env):
        """Basic capture block."""
        tmpl = env.from_string("{% capture content %}Hello World{% endcapture %}{{ content }}")
        assert tmpl.render() == "Hello World"

    def test_capture_with_end(self, env):
        """Capture using unified {% end %} closing."""
        tmpl = env.from_string("{% capture msg %}Captured{% end %}{{ msg }}")
        assert tmpl.render() == "Captured"

    def test_capture_with_expressions(self, env):
        """Capture block with expressions."""
        tmpl = env.from_string(
            "{% capture greeting %}Hello {{ name }}!{% endcapture %}{{ greeting }}"
        )
        assert tmpl.render(name="World") == "Hello World!"

    def test_capture_with_loop(self, env):
        """Capture block containing a loop."""
        tmpl = env.from_string(
            "{% capture items %}{% for i in [1,2,3] %}{{ i }}{% endfor %}{% endcapture %}"
            "{{ items }}"
        )
        assert tmpl.render() == "123"

    def test_multiple_captures(self, env):
        """Multiple capture blocks."""
        tmpl = env.from_string(
            "{% capture a %}A{% endcapture %}{% capture b %}B{% endcapture %}{{ b }}{{ a }}"
        )
        assert tmpl.render() == "BA"

    def test_capture_reuse(self, env):
        """Capture and reuse multiple times."""
        tmpl = env.from_string("{% capture x %}X{% endcapture %}{{ x }}{{ x }}{{ x }}")
        assert tmpl.render() == "XXX"


# =============================================================================
# {% cache %} - Fragment caching
# =============================================================================


class TestCache:
    """{% cache %} for fragment caching."""

    def test_simple_cache(self, env):
        """Basic cache block."""
        tmpl = env.from_string("{% cache 'test-key' %}Cached content{% endcache %}")
        assert tmpl.render() == "Cached content"

    def test_cache_with_end(self, env):
        """Cache using unified {% end %} closing."""
        tmpl = env.from_string("{% cache 'key' %}Content{% end %}")
        assert tmpl.render() == "Content"

    def test_cache_with_expression_key(self, env):
        """Cache with expression as key."""
        tmpl = env.from_string("{% cache 'item-' ~ id %}Item {{ id }}{% endcache %}")
        assert tmpl.render(id=42) == "Item 42"

    def test_cache_hit(self, env):
        """Cache returns cached value on second render."""
        tmpl = env.from_string("{% cache 'counter' %}{{ counter }}{% endcache %}")
        # First render
        result1 = tmpl.render(counter=1)
        # Second render with different counter - should still get cached value
        result2 = tmpl.render(counter=2)
        assert result1 == "1"
        assert result2 == "1"  # Cached

    def test_cache_different_keys(self, env):
        """Different cache keys store different values."""
        tmpl1 = env.from_string("{% cache 'a' %}A{% endcache %}")
        tmpl2 = env.from_string("{% cache 'b' %}B{% endcache %}")
        assert tmpl1.render() == "A"
        assert tmpl2.render() == "B"

    def test_cache_with_ttl(self, env):
        """Cache with TTL parameter (not enforced, just parsed)."""
        tmpl = env.from_string('{% cache "key", ttl="5m" %}Expires{% endcache %}')
        assert tmpl.render() == "Expires"


# =============================================================================
# {% filter %} - Apply filter to block content
# =============================================================================


class TestFilterBlock:
    """{% filter %} to apply filter to entire block."""

    def test_simple_filter_block(self, env_no_autoescape):
        """Basic filter block."""
        tmpl = env_no_autoescape.from_string("{% filter upper %}hello world{% endfilter %}")
        assert tmpl.render() == "HELLO WORLD"

    def test_filter_block_with_end(self, env_no_autoescape):
        """Filter block using unified {% end %} closing."""
        tmpl = env_no_autoescape.from_string("{% filter lower %}HELLO{% end %}")
        assert tmpl.render() == "hello"

    def test_filter_block_with_expressions(self, env_no_autoescape):
        """Filter block containing expressions."""
        tmpl = env_no_autoescape.from_string("{% filter upper %}hello {{ name }}{% endfilter %}")
        assert tmpl.render(name="world") == "HELLO WORLD"

    def test_filter_block_with_loop(self, env_no_autoescape):
        """Filter block containing a loop."""
        tmpl = env_no_autoescape.from_string(
            "{% filter upper %}{% for x in ['a', 'b', 'c'] %}{{ x }}{% endfor %}{% endfilter %}"
        )
        assert tmpl.render() == "ABC"

    def test_nested_filter_blocks(self, env_no_autoescape):
        """Nested filter blocks."""
        tmpl = env_no_autoescape.from_string(
            "{% filter upper %}{% filter trim %}  hello  {% endfilter %}{% endfilter %}"
        )
        assert tmpl.render() == "HELLO"

    def test_filter_with_args(self, env_no_autoescape):
        """Filter block with filter arguments."""
        tmpl = env_no_autoescape.from_string("{% filter truncate(5) %}hello world{% endfilter %}")
        result = tmpl.render()
        assert len(result) <= 8  # truncate adds "..."


# =============================================================================
# Integration tests
# =============================================================================


class TestIntegration:
    """Integration tests combining multiple features."""

    def test_def_with_capture(self, env):
        """Use def with capture inside."""
        tmpl = env.from_string(
            "{% def make_list(items) %}"
            "{% capture result %}"
            "{% for item in items %}{{ item }},{% endfor %}"
            "{% endcapture %}"
            "{{ result }}"
            "{% enddef %}"
            "{{ make_list([1,2,3]) }}"
        )
        assert tmpl.render() == "1,2,3,"

    def test_call_with_conditional(self, env):
        """Call block with conditional slot content."""
        tmpl = env.from_string(
            "{% def box() %}<box>{% slot %}</box>{% enddef %}"
            "{% call box() %}"
            "{% if show %}Visible{% endif %}"
            "{% endcall %}"
        )
        assert tmpl.render(show=True) == "<box>Visible</box>"
        assert tmpl.render(show=False) == "<box></box>"

    def test_def_import_pattern(self):
        """Import def from another template."""
        loader = DictLoader(
            {
                "components.html": (
                    "{% def button(text) %}<button>{{ text }}</button>{% enddef %}"
                ),
                "main.html": (
                    "{% from \"components.html\" import button %}{{ button('Click me') }}"
                ),
            }
        )
        env = Environment(loader=loader)
        tmpl = env.get_template("main.html")
        assert tmpl.render() == "<button>Click me</button>"

    def test_def_with_inheritance(self):
        """Def in template with inheritance."""
        loader = DictLoader(
            {
                "base.html": ("<html>{% block content %}{% endblock %}</html>"),
                "child.html": (
                    '{% extends "base.html" %}'
                    "{% def greet(n) %}Hi {{ n }}{% enddef %}"
                    "{% block content %}{{ greet('World') }}{% endblock %}"
                ),
            }
        )
        env = Environment(loader=loader)
        tmpl = env.get_template("child.html")
        result = tmpl.render()
        assert "Hi World" in result
        assert "<html>" in result


# ── has_slot() introspection ─────────────────────────────────────────────


class TestHasSlot:
    """Test has_slot() inside {% def %} bodies."""

    @pytest.fixture
    def env(self):
        return Environment()

    def test_has_slot_true_with_call(self, env):
        """has_slot() returns True when def is invoked via {% call %}."""
        tmpl = env.from_string(
            "{% def box() %}"
            "{% if has_slot() %}HAS{% else %}NO{% end %}"
            "{% end %}"
            "{% call box() %}body{% end %}"
        )
        assert "HAS" in tmpl.render()

    def test_has_slot_false_direct_call(self, env):
        """has_slot() returns False when def is called directly."""
        tmpl = env.from_string(
            "{% def box() %}{% if has_slot() %}HAS{% else %}NO{% end %}{% end %}{{ box() }}"
        )
        assert "NO" in tmpl.render()

    def test_has_slot_conditional_slot_rendering(self, env):
        """has_slot() enables conditional slot wrapper elements."""
        tmpl = env.from_string(
            "{% def card(title) %}"
            "<h3>{{ title }}</h3>"
            "{% if has_slot() %}<div>{% slot %}</div>{% end %}"
            "{% end %}"
            "{% call card('A') %}content{% end %}"
            "|"
            "{{ card('B') }}"
        )
        result = tmpl.render()
        assert "<div>content</div>" in result
        assert "B</h3>" in result
        # The no-slot call should NOT have the wrapper div
        parts = result.split("|")
        assert "<div>" in parts[0]
        assert "<div>" not in parts[1]

    def test_has_slot_with_args(self, env):
        """has_slot() works correctly when def has arguments."""
        tmpl = env.from_string(
            "{% def item(label, count) %}"
            "{{ label }}({{ count }})"
            "{% if has_slot() %}+{% slot %}{% end %}"
            "{% end %}"
            "{% call item('A', 1) %}extra{% end %}"
            "|"
            "{{ item('B', 2) }}"
        )
        result = tmpl.render()
        assert "A(1)+extra" in result
        assert "B(2)" in result
        assert "B(2)+" not in result


# =============================================================================
# Typed {% def %} parameters (RFC: typed-def-parameters)
# =============================================================================


class TestTypedDefParser:
    """Parser: type annotation syntax in {% def %} parameters."""

    def test_simple_type(self, env):
        """Simple type annotation: name: str"""
        tmpl = env.from_string(
            "{% def greet(name: str) %}Hello {{ name }}!{% end %}{{ greet('World') }}"
        )
        assert tmpl.render() == "Hello World!"

    def test_union_type(self, env):
        """Union type annotation: name: str | None"""
        tmpl = env.from_string(
            "{% def show(val: str | None = none) %}"
            "{% if val %}{{ val }}{% else %}empty{% end %}"
            "{% end %}{{ show() }}"
        )
        assert tmpl.render() == "empty"

    def test_mixed_typed_untyped(self, env):
        """Mix of typed and untyped parameters."""
        tmpl = env.from_string(
            "{% def card(title: str, items, count: int = 0) %}"
            "{{ title }}:{{ count }}"
            "{% end %}{{ card('A', []) }}"
        )
        assert tmpl.render() == "A:0"

    def test_generic_type(self, env):
        """Generic type annotation: items: list"""
        tmpl = env.from_string(
            "{% def show(items: list) %}"
            "{% for i in items %}{{ i }}{% end %}"
            "{% end %}{{ show([1, 2, 3]) }}"
        )
        assert tmpl.render() == "123"

    def test_generic_with_params(self, env):
        """Generic with type parameters: mapping: dict[str, int]"""
        tmpl = env.from_string(
            "{% def show(data: dict[str, int]) %}"
            "{% for k, v in data.items() %}{{ k }}={{ v }}{% end %}"
            "{% end %}{{ show({'a': 1}) }}"
        )
        assert tmpl.render() == "a=1"

    def test_multiple_typed_with_defaults(self, env):
        """Multiple typed params with defaults."""
        tmpl = env.from_string(
            "{% def greet(name: str, greeting: str = 'Hello') %}"
            "{{ greeting }}, {{ name }}!"
            "{% end %}{{ greet('World') }}"
        )
        assert tmpl.render() == "Hello, World!"

    def test_typed_override_default(self, env):
        """Override default on typed parameter."""
        tmpl = env.from_string(
            "{% def greet(name: str, greeting: str = 'Hello') %}"
            "{{ greeting }}, {{ name }}!"
            "{% end %}{{ greet('World', 'Hi') }}"
        )
        assert tmpl.render() == "Hi, World!"

    def test_untyped_still_works(self, env):
        """Untyped parameters remain fully supported."""
        tmpl = env.from_string(
            "{% def greet(name) %}Hello {{ name }}!{% end %}{{ greet('World') }}"
        )
        assert tmpl.render() == "Hello World!"

    def test_vararg_untyped(self, env):
        """*args and **kwargs remain untyped."""
        tmpl = env.from_string(
            "{% def join_all(*args) %}{{ args | join(', ') }}{% end %}{{ join_all('a', 'b', 'c') }}"
        )
        assert tmpl.render() == "a, b, c"

    def test_typed_with_vararg(self, env):
        """Typed params alongside *args."""
        tmpl = env.from_string(
            "{% def label(prefix: str, *items) %}"
            "{{ prefix }}: {{ items | join(', ') }}"
            "{% end %}{{ label('Tags', 'a', 'b') }}"
        )
        assert tmpl.render() == "Tags: a, b"

    def test_typed_with_call_slot(self, env):
        """Typed params work with {% call %} and {% slot %}."""
        tmpl = env.from_string(
            "{% def card(title: str) %}"
            "<h3>{{ title }}</h3>"
            "<div>{% slot %}</div>"
            "{% end %}"
            "{% call card('My Card') %}content{% end %}"
        )
        assert "My Card" in tmpl.render()
        assert "content" in tmpl.render()

    def test_nested_generic_type(self, env):
        """Nested generic: dict[str, list[int]]"""
        tmpl = env.from_string(
            "{% def show(data: dict[str, list[int]]) %}"
            "{% for k, v in data.items() %}{{ k }}={{ v | join(',') }}{% end %}"
            "{% end %}{{ show({'nums': [1, 2]}) }}"
        )
        assert tmpl.render() == "nums=1,2"

    def test_custom_model_type(self, env):
        """Custom model type name: data: MyModel"""
        tmpl = env.from_string(
            "{% def show(data: MyModel) %}{{ data.name }}{% end %}{{ show({'name': 'test'}) }}"
        )
        assert tmpl.render() == "test"


class TestTypedDefCompiler:
    """Compiler: annotations propagate into generated Python AST."""

    def _compile_to_pyast(self, env, source):
        """Parse and compile source to Python AST module."""
        import ast as pyast

        from kida.compiler import Compiler
        from kida.lexer import Lexer
        from kida.parser import Parser

        lexer = Lexer(source)
        tokens = list(lexer.tokenize())
        parser = Parser(tokens, None, None, source)
        tree = parser.parse()

        compiler = Compiler(env)
        # Use internal _compile_template to get the AST before code gen
        compiler._name = None
        compiler._filename = None
        compiler._locals = set()
        compiler._block_counter = 0
        compiler._has_async = False
        module = compiler._compile_template(tree)
        pyast.fix_missing_locations(module)
        return module

    def test_annotation_in_compiled_ast(self, env):
        """Compiled function carries annotation on ast.arg nodes."""
        import ast as pyast

        source = "{% def greet(name: str, count: int = 0) %}{{ name }}{% end %}"
        module = self._compile_to_pyast(env, source)

        # Find the FunctionDef for _def_greet (compiler may emit multiple
        # copies for different render modes — check the first one)
        func_defs = [
            n
            for n in pyast.walk(module)
            if isinstance(n, pyast.FunctionDef) and n.name == "_def_greet"
        ]
        assert len(func_defs) >= 1
        func = func_defs[0]

        # Check annotations on the first two args (name: str, count: int)
        assert func.args.args[0].arg == "name"
        assert isinstance(func.args.args[0].annotation, pyast.Name)
        assert func.args.args[0].annotation.id == "str"

        assert func.args.args[1].arg == "count"
        assert isinstance(func.args.args[1].annotation, pyast.Name)
        assert func.args.args[1].annotation.id == "int"

    def test_union_annotation_in_compiled_ast(self, env):
        """Union annotation produces BinOp in compiled AST."""
        import ast as pyast

        source = "{% def show(val: str | None = none) %}{{ val }}{% end %}"
        module = self._compile_to_pyast(env, source)

        func_defs = [
            n
            for n in pyast.walk(module)
            if isinstance(n, pyast.FunctionDef) and n.name == "_def_show"
        ]
        assert len(func_defs) >= 1
        ann = func_defs[0].args.args[0].annotation
        # str | None compiles to BinOp(Name('str'), BitOr, Constant(None))
        assert ann is not None
        assert isinstance(ann, pyast.BinOp)

    def test_unannotated_param_has_no_annotation(self, env):
        """Unannotated params produce ast.arg with annotation=None."""
        import ast as pyast

        source = "{% def greet(name) %}{{ name }}{% end %}"
        module = self._compile_to_pyast(env, source)

        func_defs = [
            n
            for n in pyast.walk(module)
            if isinstance(n, pyast.FunctionDef) and n.name == "_def_greet"
        ]
        assert len(func_defs) >= 1
        assert func_defs[0].args.args[0].annotation is None

    def test_malformed_annotation_falls_back(self, env):
        """Malformed annotation string falls back to None gracefully."""
        from kida.compiler.statements.functions import FunctionCompilationMixin

        result = FunctionCompilationMixin._parse_annotation("not a[valid type")
        assert result is None


class TestTypedDefBackwardCompat:
    """Backward compatibility: Def.args property still works."""

    def test_args_property_returns_names(self, env):
        """Def.args backward-compat property returns param names."""
        from kida.nodes import Def, DefParam

        node = Def(
            lineno=1,
            col_offset=0,
            name="test",
            params=(
                DefParam(lineno=1, col_offset=0, name="x", annotation="str"),
                DefParam(lineno=1, col_offset=0, name="y"),
            ),
            body=(),
        )
        assert node.args == ("x", "y")

    def test_params_has_annotations(self, env):
        """Def.params carries annotation data."""
        from kida.nodes import Def, DefParam

        node = Def(
            lineno=1,
            col_offset=0,
            name="test",
            params=(
                DefParam(lineno=1, col_offset=0, name="x", annotation="str"),
                DefParam(lineno=1, col_offset=0, name="y"),
            ),
            body=(),
        )
        assert node.params[0].annotation == "str"
        assert node.params[1].annotation is None


class TestCallSiteValidation:
    """Analysis: call-site validation against {% def %} signatures."""

    def _validate(self, source):
        """Parse source and return call validation issues."""
        from kida.analysis.analyzer import BlockAnalyzer
        from kida.lexer import Lexer
        from kida.parser import Parser

        lexer = Lexer(source)
        tokens = list(lexer.tokenize())
        parser = Parser(tokens, None, None, source)
        ast = parser.parse()
        analyzer = BlockAnalyzer()
        return analyzer.validate_calls(ast)

    def test_correct_call_no_issues(self):
        """Correct call produces no validation issues."""
        issues = self._validate(
            "{% def card(title, items) %}"
            "{{ title }}{% for i in items %}{{ i }}{% end %}"
            "{% end %}"
            "{{ card('hi', [1, 2]) }}"
        )
        assert issues == []

    def test_unknown_param(self):
        """Unknown keyword argument is detected."""
        issues = self._validate("{% def card(title) %}{{ title }}{% end %}{{ card(titl='oops') }}")
        assert len(issues) == 1
        assert "titl" in issues[0].unknown_params

    def test_missing_required_param(self):
        """Missing required parameter is detected."""
        issues = self._validate(
            "{% def card(title, items) %}{{ title }}{% end %}{{ card(items=[1, 2]) }}"
        )
        assert len(issues) == 1
        assert "title" in issues[0].missing_required

    def test_duplicate_param_last_wins(self):
        """Duplicate kwargs are deduplicated by the parser (last-wins).

        The AST stores kwargs in a dict, so duplicates can't be detected
        at the analysis level. The call is valid since 'title' is provided.
        """
        issues = self._validate(
            "{% def card(title) %}{{ title }}{% end %}{{ card(title='a', title='b') }}"
        )
        # No issues — the dict already deduplicated the kwargs
        assert issues == []

    def test_vararg_relaxes_positional(self):
        """*args in def relaxes positional validation."""
        issues = self._validate(
            "{% def join_all(*args) %}{{ args | join }}{% end %}{{ join_all('a', 'b', 'c') }}"
        )
        assert issues == []

    def test_kwarg_relaxes_keyword(self):
        """**kwargs in def relaxes keyword validation."""
        issues = self._validate(
            "{% def tag(name, **attrs) %}"
            "<{{ name }}>{% end %}"
            "{{ tag('div', id='main', class='big') }}"
        )
        assert issues == []

    def test_default_params_not_required(self):
        """Parameters with defaults are not required."""
        issues = self._validate(
            "{% def greet(name: str = 'World') %}Hello {{ name }}{% end %}{{ greet() }}"
        )
        assert issues == []

    def test_environment_validate_calls_flag(self):
        """Environment.validate_calls emits warnings on bad calls."""
        import warnings

        env = Environment(validate_calls=True)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            env.from_string("{% def card(title) %}{{ title }}{% end %}{{ card(titl='oops') }}")
        assert len(w) == 1
        assert "titl" in str(w[0].message)

    def test_environment_validate_calls_disabled_by_default(self):
        """By default, no validation warnings are emitted."""
        import warnings

        env = Environment()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            env.from_string("{% def card(title) %}{{ title }}{% end %}{{ card(titl='oops') }}")
        # No validation warnings (there may be other warnings, so filter)
        call_warnings = [x for x in w if "titl" in str(x.message)]
        assert call_warnings == []

    def test_call_block_validated(self):
        """{% call %} blocks are also validated."""
        issues = self._validate(
            "{% def card(title) %}<h3>{{ title }}</h3>{% slot %}{% end %}"
            "{% call card(titl='oops') %}body{% end %}"
        )
        assert len(issues) == 1
        assert "titl" in issues[0].unknown_params

    def test_is_valid_property(self):
        """CallValidation.is_valid returns False when issues exist."""
        issues = self._validate("{% def card(title) %}{{ title }}{% end %}{{ card(titl='oops') }}")
        assert len(issues) == 1
        assert not issues[0].is_valid

    def test_valid_call_returns_empty(self):
        """Valid calls return empty issues list."""
        issues = self._validate(
            "{% def greet(name: str) %}Hello {{ name }}{% end %}{{ greet('World') }}"
        )
        assert issues == []

    def test_positional_args_fill_required(self):
        """Positional args satisfy required params left-to-right."""
        issues = self._validate(
            "{% def card(title, items) %}{{ title }}{% end %}{{ card('hello', [1, 2]) }}"
        )
        assert issues == []

    def test_unknown_function_no_false_positive(self):
        """Calls to functions not from {% def %} are silently skipped."""
        issues = self._validate("{% def card(title) %}{{ title }}{% end %}{{ other_func('test') }}")
        assert issues == []

    def test_multiple_defs_validated_independently(self):
        """Multiple defs each have their own signature for validation."""
        issues = self._validate(
            "{% def greet(name) %}{{ name }}{% end %}"
            "{% def card(title, items) %}{{ title }}{% end %}"
            "{{ greet('hi') }}"
            "{{ card(titl='oops') }}"
        )
        # greet call is fine; card call has unknown 'titl' and missing 'title', 'items'
        assert len(issues) == 1
        assert issues[0].def_name == "card"
        assert "titl" in issues[0].unknown_params

    def test_nested_def_validated(self):
        """Calls to nested defs are validated."""
        issues = self._validate(
            "{% def outer() %}"
            "{% def inner(x) %}{{ x }}{% end %}"
            "{{ inner(y='bad') }}"
            "{% end %}"
            "{{ outer() }}"
        )
        assert len(issues) == 1
        assert issues[0].def_name == "inner"
        assert "y" in issues[0].unknown_params
