"""Test environment configuration and features in Kida template engine.

Tests autoescape, whitespace control, loaders, caching, and configuration.
"""

import sys

import pytest

from kida import (
    DictLoader,
    Environment,
    FileSystemLoader,
    FunctionLoader,
    Markup,
    PackageLoader,
    TemplateNotFoundError,
)


class TestAutoescape:
    """Autoescape functionality tests."""

    def test_autoescape_on(self):
        """Autoescape escapes HTML."""
        env = Environment(autoescape=True)
        tmpl = env.from_string("{{ text }}")
        assert tmpl.render(text="<script>") == "&lt;script&gt;"

    def test_autoescape_off(self):
        """Autoescape off doesn't escape."""
        env = Environment(autoescape=False)
        tmpl = env.from_string("{{ text }}")
        assert tmpl.render(text="<script>") == "<script>"

    def test_safe_filter(self):
        """safe filter prevents escaping."""
        env = Environment(autoescape=True)
        tmpl = env.from_string("{{ text|safe }}")
        assert tmpl.render(text="<b>bold</b>") == "<b>bold</b>"

    def test_markup_not_escaped(self):
        """Markup instances not double-escaped."""
        env = Environment(autoescape=True)
        tmpl = env.from_string("{{ html }}")
        result = tmpl.render(html=Markup("<b>safe</b>"))
        assert result == "<b>safe</b>"
        assert "&lt;" not in result

    def test_escape_filter(self):
        """escape filter forces escaping."""
        env = Environment(autoescape=False)
        tmpl = env.from_string("{{ text|escape }}")
        assert tmpl.render(text="<b>") == "&lt;b&gt;"

    def test_e_filter(self):
        """e filter (alias for escape)."""
        env = Environment(autoescape=False)
        tmpl = env.from_string("{{ text|e }}")
        assert tmpl.render(text="<b>") == "&lt;b&gt;"

    def test_special_chars(self):
        """All special HTML chars escaped."""
        env = Environment(autoescape=True)
        tmpl = env.from_string("{{ text }}")
        result = tmpl.render(text="<>&\"'")
        assert "&lt;" in result
        assert "&gt;" in result
        assert "&amp;" in result


class TestWhitespaceControl:
    """Whitespace control tests."""

    def test_trim_blocks(self):
        """trim_blocks removes newline after block."""
        env = Environment(trim_blocks=True)
        tmpl = env.from_string("{% if true %}\nHello{% endif %}")
        result = tmpl.render()
        assert not result.startswith("\n")

    def test_lstrip_blocks(self):
        """lstrip_blocks removes leading whitespace."""
        env = Environment(lstrip_blocks=True)
        tmpl = env.from_string("    {% if true %}Hello{% endif %}")
        result = tmpl.render()
        assert not result.startswith("    ")

    def test_minus_tag_left(self):
        """{%- removes preceding whitespace."""
        env = Environment()
        tmpl = env.from_string("Hello   {%- if true %} World{% endif %}")
        assert tmpl.render() == "Hello World"

    def test_minus_tag_right(self):
        """-%} removes following whitespace."""
        env = Environment()
        tmpl = env.from_string("{% if true -%}   World{% endif %}")
        assert tmpl.render() == "World"

    def test_minus_both(self):
        """Both sides stripped."""
        env = Environment()
        tmpl = env.from_string("Hello   {%- if true -%}   World{% endif %}")
        assert tmpl.render() == "HelloWorld"

    def test_minus_output(self):
        """Whitespace control in output tags."""
        env = Environment()
        tmpl = env.from_string("Hello   {{- ' World' }}")
        assert tmpl.render() == "Hello World"

    def test_minus_output_right(self):
        """Whitespace control right side of output."""
        env = Environment()
        tmpl = env.from_string("{{ 'Hello' -}}   World")
        assert tmpl.render() == "HelloWorld"


class TestDictLoader:
    """DictLoader tests."""

    def test_basic_load(self):
        """Basic template loading."""
        loader = DictLoader({"test.html": "Hello World"})
        env = Environment(loader=loader)
        tmpl = env.get_template("test.html")
        assert tmpl.render() == "Hello World"

    def test_multiple_templates(self):
        """Load multiple templates."""
        loader = DictLoader(
            {
                "a.html": "A",
                "b.html": "B",
                "c.html": "C",
            }
        )
        env = Environment(loader=loader)
        assert env.get_template("a.html").render() == "A"
        assert env.get_template("b.html").render() == "B"
        assert env.get_template("c.html").render() == "C"

    def test_template_not_found(self):
        """Template not found raises error."""
        from kida import TemplateNotFoundError

        loader = DictLoader({})
        env = Environment(loader=loader)
        with pytest.raises(TemplateNotFoundError):
            env.get_template("missing.html")


class TestFileSystemLoader:
    """FileSystemLoader tests."""

    def test_basic_load(self, tmp_path):
        """Basic template loading from filesystem."""
        template_file = tmp_path / "test.html"
        template_file.write_text("Hello {{ name }}")

        loader = FileSystemLoader(str(tmp_path))
        env = Environment(loader=loader)
        tmpl = env.get_template("test.html")
        assert tmpl.render(name="World") == "Hello World"

    def test_subdirectory(self, tmp_path):
        """Load template from subdirectory."""
        subdir = tmp_path / "templates"
        subdir.mkdir()
        template_file = subdir / "test.html"
        template_file.write_text("Subdir template")

        loader = FileSystemLoader(str(tmp_path))
        env = Environment(loader=loader)
        tmpl = env.get_template("templates/test.html")
        assert tmpl.render() == "Subdir template"


class TestTemplateCaching:
    """Template caching tests."""

    def test_template_cached(self):
        """Templates are cached."""
        loader = DictLoader({"test.html": "Hello"})
        env = Environment(loader=loader)

        tmpl1 = env.get_template("test.html")
        tmpl2 = env.get_template("test.html")

        # Should be same object (cached)
        assert tmpl1 is tmpl2

    def test_from_string_caching(self):
        """from_string may not be cached (by default)."""
        env = Environment()
        tmpl1 = env.from_string("Hello")
        tmpl2 = env.from_string("Hello")

        # from_string typically creates new template each time
        # This is expected behavior - templates are different objects
        assert tmpl1 is not tmpl2


class TestEnvironmentFilters:
    """Environment filter registration tests."""

    def test_add_filter(self):
        """Add custom filter."""
        env = Environment()

        def reverse_string(s):
            return s[::-1]

        env.add_filter("reverse_str", reverse_string)
        tmpl = env.from_string("{{ text|reverse_str }}")
        assert tmpl.render(text="hello") == "olleh"

    def test_update_filters(self):
        """Update multiple filters at once."""
        env = Environment()

        def double(x):
            return x * 2

        def triple(x):
            return x * 3

        env.update_filters({"double": double, "triple": triple})
        tmpl = env.from_string("{{ 5|double }}-{{ 5|triple }}")
        assert tmpl.render() == "10-15"

    def test_override_builtin_filter(self):
        """Override builtin filter works with custom filter registry."""
        env = Environment()

        def custom_upper(s):
            return s.upper() + "!"

        env.add_filter("upper", custom_upper)
        tmpl = env.from_string("{{ 'hello'|upper }}")
        assert tmpl.render() == "HELLO!"


class TestEnvironmentTests:
    """Environment test registration tests."""

    def test_add_test(self):
        """Add custom test."""
        env = Environment()

        def is_even(n):
            return n % 2 == 0

        env.add_test("even", is_even)
        tmpl = env.from_string("{% if x is even %}yes{% endif %}")
        assert tmpl.render(x=4) == "yes"
        assert tmpl.render(x=3) == ""

    def test_update_tests(self):
        """Update multiple tests at once."""
        env = Environment()

        def is_positive(n):
            return n > 0

        def is_negative(n):
            return n < 0

        env.update_tests({"positive": is_positive, "negative": is_negative})
        tmpl = env.from_string("{% if x is positive %}+{% elif x is negative %}-{% endif %}")
        assert tmpl.render(x=5) == "+"
        assert tmpl.render(x=-5) == "-"


class TestEnvironmentGlobals:
    """Environment globals tests."""

    def test_add_global(self):
        """Add global variable."""
        env = Environment()
        env.add_global("site_name", "My Site")
        tmpl = env.from_string("{{ site_name }}")
        assert tmpl.render() == "My Site"

    def test_global_function(self):
        """Add global function."""
        env = Environment()

        def greet(name):
            return f"Hello {name}"

        env.add_global("greet", greet)
        tmpl = env.from_string("{{ greet('World') }}")
        assert tmpl.render() == "Hello World"


class TestEnvironmentConfiguration:
    """Environment configuration tests."""

    def test_default_config(self):
        """Default configuration."""
        env = Environment()
        # Should be able to render basic template
        tmpl = env.from_string("{{ x }}")
        assert tmpl.render(x=42) == "42"

    def test_block_start_string(self):
        """Custom block start string (if supported)."""
        # Some implementations allow customizing delimiters
        try:
            env = Environment(block_start_string="<%")
            tmpl = env.from_string("<% if true %>yes<% endif %>")
            assert tmpl.render() == "yes"
        except (TypeError, AttributeError):
            pytest.skip("Custom delimiters not supported")

    def test_variable_start_string(self):
        """Custom variable start string (if supported)."""
        try:
            env = Environment(variable_start_string="<<")
            tmpl = env.from_string("<< x >>")
            assert tmpl.render(x=42) == "42"
        except (TypeError, AttributeError):
            pytest.skip("Custom delimiters not supported")


class TestMarkupClass:
    """Markup class tests."""

    def test_markup_creation(self):
        """Create Markup instance."""
        m = Markup("<b>safe</b>")
        assert str(m) == "<b>safe</b>"

    def test_markup_escape(self):
        """Markup.escape class method."""
        m = Markup.escape("<script>")
        assert str(m) == "&lt;script&gt;"

    def test_markup_concatenation(self):
        """Markup concatenation."""
        m = Markup("<b>") + "text" + Markup("</b>")
        # Result should be Markup
        assert isinstance(m, Markup)

    def test_markup_format(self):
        """Markup format method escapes arguments."""
        m = Markup("<p>{}</p>").format("<script>")
        assert "&lt;script&gt;" in str(m)

    def test_markup_join(self):
        """Markup join method."""
        m = Markup(", ").join(["a", "b", "c"])
        assert str(m) == "a, b, c"

    def test_markup_striptags(self):
        """Markup striptags method."""
        m = Markup("<p>Hello <b>World</b></p>")
        assert m.striptags() == "Hello World"

    def test_markup_unescape(self):
        """Markup unescape method."""
        m = Markup("&lt;script&gt;")
        assert m.unescape() == "<script>"


class TestFunctionLoader:
    """FunctionLoader tests."""

    def test_string_return(self):
        """Function returning a string works."""

        def load(name):
            if name == "hello.html":
                return "Hello, {{ name }}!"
            return None

        env = Environment(loader=FunctionLoader(load))
        tmpl = env.get_template("hello.html")
        assert tmpl.render(name="World") == "Hello, World!"

    def test_tuple_return(self):
        """Function returning (source, filename) tuple works."""

        def load(name):
            if name == "page.html":
                return "<h1>Page</h1>", "custom://page.html"
            return None

        env = Environment(loader=FunctionLoader(load))
        tmpl = env.get_template("page.html")
        assert tmpl.render() == "<h1>Page</h1>"

    def test_none_return_raises(self):
        """Function returning None raises TemplateNotFoundError."""

        def load(name):
            return None

        env = Environment(loader=FunctionLoader(load))
        with pytest.raises(TemplateNotFoundError):
            env.get_template("missing.html")

    def test_lambda_loader(self):
        """Lambda as load function works."""
        templates = {"index.html": "<p>Index</p>"}
        env = Environment(loader=FunctionLoader(lambda name: templates.get(name)))
        assert env.get_template("index.html").render() == "<p>Index</p>"

    def test_list_templates_empty(self):
        """FunctionLoader.list_templates returns empty list."""
        loader = FunctionLoader(lambda name: None)
        assert loader.list_templates() == []

    def test_with_variables(self):
        """FunctionLoader templates can use full kida syntax."""

        def load(name):
            if name == "loop.html":
                return "{% for x in items %}{{ x }}{% end %}"
            return None

        env = Environment(loader=FunctionLoader(load))
        tmpl = env.get_template("loop.html")
        assert tmpl.render(items=["a", "b", "c"]) == "abc"

    def test_with_inheritance(self):
        """FunctionLoader supports template inheritance."""

        def load(name):
            templates = {
                "base.html": "<html>{% block content %}{% end %}</html>",
                "page.html": "{% extends 'base.html' %}{% block content %}Hi{% end %}",
            }
            return templates.get(name)

        env = Environment(loader=FunctionLoader(load))
        tmpl = env.get_template("page.html")
        assert tmpl.render() == "<html>Hi</html>"

    def test_with_includes(self):
        """FunctionLoader supports includes."""

        def load(name):
            templates = {
                "main.html": "Before {% include 'partial.html' %} After",
                "partial.html": "PARTIAL",
            }
            return templates.get(name)

        env = Environment(loader=FunctionLoader(load))
        tmpl = env.get_template("main.html")
        assert tmpl.render() == "Before PARTIAL After"


class TestPackageLoader:
    """PackageLoader tests."""

    @pytest.fixture()
    def mock_package(self, tmp_path):
        """Create a mock Python package with templates."""
        pkg_dir = tmp_path / "test_pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        tmpl_dir = pkg_dir / "templates"
        tmpl_dir.mkdir()
        (tmpl_dir / "index.html").write_text("Hello, {{ name }}!")
        (tmpl_dir / "base.html").write_text("<html>{% block content %}{% end %}</html>")

        sub_dir = tmpl_dir / "pages"
        sub_dir.mkdir()
        (sub_dir / "about.html").write_text("<h1>About</h1>")

        # Add to sys.path so importlib can find it
        sys.path.insert(0, str(tmp_path))
        yield "test_pkg"
        sys.path.remove(str(tmp_path))
        # Clean up module from cache
        sys.modules.pop("test_pkg", None)

    def test_basic_load(self, mock_package):
        """Load a template from a package."""
        loader = PackageLoader(mock_package, "templates")
        env = Environment(loader=loader)
        tmpl = env.get_template("index.html")
        assert tmpl.render(name="World") == "Hello, World!"

    def test_subdirectory_load(self, mock_package):
        """Load a template from a subdirectory within the package."""
        loader = PackageLoader(mock_package, "templates")
        env = Environment(loader=loader)
        tmpl = env.get_template("pages/about.html")
        assert tmpl.render() == "<h1>About</h1>"

    def test_template_not_found(self, mock_package):
        """Missing template raises TemplateNotFoundError."""
        loader = PackageLoader(mock_package, "templates")
        env = Environment(loader=loader)
        with pytest.raises(TemplateNotFoundError):
            env.get_template("nonexistent.html")

    def test_list_templates(self, mock_package):
        """list_templates returns all templates in package."""
        loader = PackageLoader(mock_package, "templates")
        templates = loader.list_templates()
        assert "index.html" in templates
        assert "base.html" in templates
        assert "pages/about.html" in templates

    def test_filename_in_source(self, mock_package):
        """get_source returns meaningful filename."""
        loader = PackageLoader(mock_package, "templates")
        _source, filename = loader.get_source("index.html")
        assert filename is not None
        assert "test_pkg" in filename
        assert "index.html" in filename

    def test_with_rendering(self, mock_package):
        """Full render cycle through PackageLoader."""
        loader = PackageLoader(mock_package, "templates")
        env = Environment(loader=loader)
        tmpl = env.get_template("index.html")
        result = tmpl.render(name="Kida")
        assert result == "Hello, Kida!"

    def test_invalid_package_raises(self):
        """Non-existent package raises ModuleNotFoundError."""
        loader = PackageLoader("nonexistent_package_xyz_123", "templates")
        with pytest.raises(ModuleNotFoundError):
            loader.get_source("test.html")

    def test_with_choice_loader(self, mock_package):
        """PackageLoader works inside ChoiceLoader."""
        from kida import ChoiceLoader

        override = DictLoader({"index.html": "Override!"})
        pkg_loader = PackageLoader(mock_package, "templates")
        loader = ChoiceLoader([override, pkg_loader])

        env = Environment(loader=loader)
        # Override wins for index.html
        assert env.get_template("index.html").render() == "Override!"
        # Package provides pages/about.html
        assert env.get_template("pages/about.html").render() == "<h1>About</h1>"

    def test_default_package_path(self, tmp_path):
        """Default package_path is 'templates'."""
        pkg_dir = tmp_path / "default_pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")
        tmpl_dir = pkg_dir / "templates"
        tmpl_dir.mkdir()
        (tmpl_dir / "test.html").write_text("Default path works")

        sys.path.insert(0, str(tmp_path))
        try:
            loader = PackageLoader("default_pkg")
            env = Environment(loader=loader)
            assert env.get_template("test.html").render() == "Default path works"
        finally:
            sys.path.remove(str(tmp_path))
            sys.modules.pop("default_pkg", None)
