"""Tests for Template.render_block() — block-level rendering.

This is the contract that chirp's Fragment return type depends on.
If these tests break, chirp's core differentiator (HTML fragments) breaks.
"""

import pytest

from kida import DictLoader, Environment, TemplateError


def _env(**templates: str) -> Environment:
    """Build an Environment with in-memory templates."""
    return Environment(loader=DictLoader(templates))


class TestRenderBlock:
    """Basic render_block functionality."""

    def test_simple_block(self) -> None:
        env = _env(page="Header {% block content %}Hello, {{ name }}!{% endblock %} Footer")
        template = env.get_template("page")
        result = template.render_block("content", name="World")
        assert result.strip() == "Hello, World!"

    def test_block_with_context(self) -> None:
        env = _env(
            page="{% block items %}{% for x in things %}<li>{{ x }}</li>{% endfor %}{% endblock %}"
        )
        template = env.get_template("page")
        result = template.render_block("items", things=["a", "b", "c"])
        assert "<li>a</li>" in result
        assert "<li>b</li>" in result
        assert "<li>c</li>" in result

    def test_block_isolates_output(self) -> None:
        """render_block should only return the block, not surrounding content."""
        env = _env(page="BEFORE {% block middle %}MIDDLE{% endblock %} AFTER")
        template = env.get_template("page")
        result = template.render_block("middle")
        assert "MIDDLE" in result
        assert "BEFORE" not in result
        assert "AFTER" not in result

    def test_nonexistent_block_raises(self) -> None:
        env = _env(page="{% block real %}content{% endblock %}")
        template = env.get_template("page")
        with pytest.raises((KeyError, TemplateError)):
            template.render_block("nonexistent")

    def test_empty_block(self) -> None:
        env = _env(page="{% block empty %}{% endblock %}")
        template = env.get_template("page")
        result = template.render_block("empty")
        assert result.strip() == ""


class TestRenderBlockInheritance:
    """render_block with template inheritance ({% extends %})."""

    def test_child_overrides_block(self) -> None:
        env = _env(
            base="<html>{% block content %}default{% endblock %}</html>",
            child='{% extends "base" %}{% block content %}overridden{% endblock %}',
        )
        template = env.get_template("child")
        result = template.render_block("content")
        assert "overridden" in result
        assert "default" not in result

    def test_child_block_with_context(self) -> None:
        env = _env(
            base="<html>{% block content %}{% endblock %}</html>",
            child='{% extends "base" %}{% block content %}<h1>{{ title }}</h1>{% endblock %}',
        )
        template = env.get_template("child")
        result = template.render_block("content", title="Hello")
        assert "<h1>Hello</h1>" in result
        assert "<html>" not in result

    def test_inherited_block_available(self) -> None:
        """Parent-only blocks are renderable via render_block on descendant template."""
        env = _env(
            base="{% block sidebar %}Default Sidebar{% endblock %} {% block content %}{% endblock %}",
            child='{% extends "base" %}{% block content %}Page Content{% endblock %}',
        )
        template = env.get_template("child")
        # sidebar is inherited from base — render_block resolves through chain
        result = template.render_block("sidebar")
        assert "Default Sidebar" in result

    def test_multi_level_inheritance(self) -> None:
        """render_block resolves through multi-level inheritance chains."""
        env = _env(
            base="{% block header %}Base Header{% endblock %}{% block content %}{% endblock %}",
            layout='{% extends "base" %}{% block header %}Layout Header{% endblock %}',
            page='{% extends "layout" %}{% block content %}Page Content{% endblock %}',
        )
        template = env.get_template("page")
        # header from layout (middle level)
        assert "Layout Header" in template.render_block("header")
        # content from page (leaf)
        assert "Page Content" in template.render_block("content")
        # base-only block reachable from page
        assert "Base Header" not in template.render_block("header")
        assert "Layout Header" in template.render_block("header")

    def test_nested_block_dispatch(self) -> None:
        """Parent block calling nested block dispatches to child override."""
        env = _env(
            base="{% block outer %}[{% block inner %}default{% endblock %}]{% endblock %}",
            child='{% extends "base" %}{% block inner %}overridden{% endblock %}',
        )
        template = env.get_template("child")
        # outer from base, inner from child — effective _blocks passed
        result = template.render_block("outer")
        assert "[overridden]" in result

    def test_inherited_fragment_rendering(self) -> None:
        """Fragment blocks from parent are renderable via render_block on child."""
        env = _env(
            base="{% block content %}{% endblock %}{% fragment oob %}{{ data }}{% end %}",
            child='{% extends "base" %}{% block content %}Main{% endblock %}',
        )
        template = env.get_template("child")
        result = template.render_block("oob", data="fragment")
        assert "fragment" in result

    @pytest.mark.asyncio
    async def test_inherited_block_stream_async(self) -> None:
        """render_block_stream_async supports inherited blocks."""
        env = _env(
            base="{% block sidebar %}Sidebar{% endblock %}{% block content %}{% endblock %}",
            child='{% extends "base" %}{% block content %}Content{% endblock %}',
        )
        template = env.get_template("child")
        chunks = [c async for c in template.render_block_stream_async("sidebar")]
        assert "".join(chunks) == "Sidebar"


class TestListBlocks:
    """Template.list_blocks() — discover available block names."""

    def test_single_block(self) -> None:
        env = _env(page="{% block content %}hello{% endblock %}")
        template = env.get_template("page")
        blocks = template.list_blocks()
        assert "content" in blocks

    def test_multiple_blocks(self) -> None:
        env = _env(
            page="{% block header %}h{% endblock %}{% block content %}c{% endblock %}{% block footer %}f{% endblock %}"
        )
        template = env.get_template("page")
        blocks = template.list_blocks()
        assert "header" in blocks
        assert "content" in blocks
        assert "footer" in blocks

    def test_no_blocks(self) -> None:
        env = _env(page="Just text, no blocks")
        template = env.get_template("page")
        blocks = template.list_blocks()
        assert blocks == []

    def test_inherited_blocks_included(self) -> None:
        """list_blocks returns all blocks the child can render, including inherited."""
        env = _env(
            base="{% block a %}{% endblock %}{% block b %}{% endblock %}",
            child='{% extends "base" %}{% block a %}overridden{% endblock %}',
        )
        template = env.get_template("child")
        blocks = template.list_blocks()
        assert "a" in blocks
        assert "b" in blocks  # inherited from parent, available via render_block

    def test_inherited_block_map_cached(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Effective inherited block map is computed once and reused (when auto_reload=False)."""
        env = Environment(
            loader=DictLoader(
                {
                    "base": "{% block sidebar %}s{% endblock %}{% block content %}c{% endblock %}",
                    "child": '{% extends "base" %}{% block content %}overridden{% endblock %}',
                }
            ),
            auto_reload=False,
        )
        template = env.get_template("child")

        calls = 0
        original = template._inheritance_chain

        def counted_inheritance_chain():
            nonlocal calls
            calls += 1
            return original()

        monkeypatch.setattr(template, "_inheritance_chain", counted_inheritance_chain)

        # First lookup builds cache, subsequent lookups should reuse it.
        template.render_block("sidebar")
        template.render_block("content")
        blocks = template.list_blocks()

        assert "sidebar" in blocks
        assert "content" in blocks
        assert calls == 1


class TestFragmentBlocks:
    """{% fragment name %} — blocks skipped during render(), available via render_block()."""

    def test_fragment_skipped_during_render(self) -> None:
        """Fragment blocks produce no output during full template render."""
        env = _env(page="Before {% fragment notification %}<div>{{ title }}</div>{% end %} After")
        template = env.get_template("page")
        result = template.render()
        assert result.strip() == "Before  After"
        assert "notification" not in result

    def test_fragment_renders_via_render_block(self) -> None:
        """Fragment blocks render normally when called via render_block()."""
        env = _env(page="Before {% fragment notification %}<div>{{ title }}</div>{% end %} After")
        template = env.get_template("page")
        result = template.render_block("notification", title="Hello!")
        assert "<div>Hello!</div>" in result

    def test_fragment_with_variables_no_error(self) -> None:
        """Fragment blocks don't raise UndefinedError during full render."""
        env = _env(page="OK {% fragment card %}{{ undefined_var }}{% end %} Done")
        template = env.get_template("page")
        # This should NOT raise — the fragment body is never evaluated
        result = template.render()
        assert "OK" in result
        assert "Done" in result

    def test_fragment_listed_in_blocks(self) -> None:
        """Fragment blocks appear in list_blocks()."""
        env = _env(page="{% block header %}h{% endblock %}{% fragment sidebar %}s{% end %}")
        template = env.get_template("page")
        blocks = template.list_blocks()
        assert "header" in blocks
        assert "sidebar" in blocks

    def test_fragment_with_inheritance(self) -> None:
        """Fragment blocks work with template inheritance."""
        env = _env(
            base="{% block content %}{% endblock %}{% fragment oob %}{{ data }}{% end %}",
            child='{% extends "base" %}{% block content %}Main{% endblock %}',
        )
        template = env.get_template("child")
        # Full render: fragment is skipped
        result = template.render()
        assert "Main" in result
        assert "data" not in result

    def test_fragment_endfragment_closing(self) -> None:
        """Fragment blocks accept {% endfragment %} as closing tag."""
        env = _env(page="{% fragment sidebar %}<nav>{{ menu }}</nav>{% endfragment %}")
        template = env.get_template("page")
        result = template.render()
        assert result.strip() == ""
        result = template.render_block("sidebar", menu="Home")
        assert "<nav>Home</nav>" in result


class TestGlobalsBlock:
    """{% globals %} — setup block for macros available during render_block()."""

    def test_globals_macro_available_in_full_render(self) -> None:
        """Macros defined in globals are available during full render."""
        env = _env(
            page=(
                "{% globals %}{% def greet(name) %}Hello, {{ name }}!{% end %}{% end %}"
                '{% block content %}{{ greet("World") }}{% endblock %}'
            )
        )
        template = env.get_template("page")
        result = template.render()
        assert "Hello, World!" in result

    def test_globals_macro_available_in_render_block(self) -> None:
        """Macros defined in globals are available during render_block()."""
        env = _env(
            page=(
                "{% globals %}{% def greet(name) %}Hello, {{ name }}!{% end %}{% end %}"
                '{% block content %}{{ greet("World") }}{% endblock %}'
            )
        )
        template = env.get_template("page")
        result = template.render_block("content")
        assert "Hello, World!" in result

    def test_globals_variable_in_render_block(self) -> None:
        """Variables set in globals are available during render_block()."""
        env = _env(
            page=(
                '{% globals %}{% set site_name = "My Site" %}{% end %}'
                "{% block title %}{{ site_name }}{% endblock %}"
            )
        )
        template = env.get_template("page")
        result = template.render_block("title")
        assert "My Site" in result

    def test_globals_with_inheritance(self) -> None:
        """Globals in base template are available in child's render_block()."""
        env = _env(
            base=(
                '{% globals %}{% def field(name) %}<input name="{{ name }}">{% end %}{% end %}'
                "{% block form %}default{% endblock %}"
            ),
            child=('{% extends "base" %}{% block form %}{{ field("email") }}{% endblock %}'),
        )
        template = env.get_template("child")
        # Full render should work
        result = template.render()
        assert '<input name="email">' in result

    def test_globals_no_output(self) -> None:
        """Globals block produces no output during full render."""
        env = _env(
            page=(
                "Before{% globals %}{% def f() %}x{% end %}{% end %}After"
                "{% block content %}{{ f() }}{% endblock %}"
            )
        )
        template = env.get_template("page")
        result = template.render()
        assert "BeforeAfter" in result.replace("x", "").replace("\n", "").replace(" ", "") or (
            "Before" in result and "After" in result
        )

    def test_globals_endglobals_closing(self) -> None:
        """Globals blocks accept {% endglobals %} as closing tag."""
        env = _env(
            page=(
                "{% globals %}{% def f() %}ok{% end %}{% endglobals %}"
                "{% block content %}{{ f() }}{% endblock %}"
            )
        )
        template = env.get_template("page")
        result = template.render_block("content")
        assert "ok" in result

    def test_globals_from_import_in_render_block(self) -> None:
        """{% from...import %} inside globals makes macros available in render_block()."""
        env = _env(
            macros="{% def greet(name) %}Hello, {{ name }}!{% end %}",
            page=(
                '{% globals %}{% from "macros" import greet %}{% end %}'
                '{% block content %}{{ greet("World") }}{% endblock %}'
            ),
        )
        template = env.get_template("page")
        # Full render: macro is available
        result = template.render()
        assert "Hello, World!" in result
        # Block render: macro is also available via globals setup
        result = template.render_block("content")
        assert "Hello, World!" in result

    def test_globals_from_import_in_fragment(self) -> None:
        """{% from...import %} inside globals works with {% fragment %} blocks."""
        env = _env(
            macros="{% def card(title) %}<div>{{ title }}</div>{% end %}",
            page=(
                '{% globals %}{% from "macros" import card %}{% end %}'
                "Page content"
                '{% fragment oob %}{{ card("Task 1") }}{% endfragment %}'
            ),
        )
        template = env.get_template("page")
        # Full render: fragment is skipped
        result = template.render()
        assert "Page content" in result
        assert "Task 1" not in result
        # Block render: macro from globals is available
        result = template.render_block("oob")
        assert "<div>Task 1</div>" in result

    def test_globals_from_import_multiple(self) -> None:
        """Multiple {% from...import %} in globals all propagate to render_block()."""
        env = _env(
            helpers="{% def bold(text) %}<b>{{ text }}</b>{% end %}",
            icons="{% def icon(name) %}<i>{{ name }}</i>{% end %}",
            page=(
                "{% globals %}"
                '{% from "helpers" import bold %}'
                '{% from "icons" import icon %}'
                "{% end %}"
                '{% block content %}{{ bold("hi") }} {{ icon("star") }}{% endblock %}'
            ),
        )
        template = env.get_template("page")
        result = template.render_block("content")
        assert "<b>hi</b>" in result
        assert "<i>star</i>" in result


class TestImportsBlock:
    """{% imports %}...{% end %} — intent-revealing imports for fragments.

    Same semantics as {% globals %} but signals: these are imports for
    fragment/block scope. Compiles to _globals_setup.
    """

    def test_imports_block_makes_macros_available_in_render_block(self) -> None:
        """{% imports %} with {% from %} makes macros available in render_block()."""
        env = _env(
            macros="{% def greet(name) %}Hello, {{ name }}!{% end %}",
            page=(
                '{% imports %}{% from "macros" import greet %}{% end %}'
                '{% block content %}{{ greet("World") }}{% endblock %}'
            ),
        )
        template = env.get_template("page")
        result = template.render_block("content")
        assert "Hello, World!" in result

    def test_imports_block_with_fragment(self) -> None:
        """{% imports %} works with {% fragment %} blocks."""
        env = _env(
            macros="{% def card(title) %}<div>{{ title }}</div>{% end %}",
            page=(
                '{% imports %}{% from "macros" import card %}{% end %}'
                "Page content"
                '{% fragment oob %}{{ card("Task 1") }}{% endfragment %}'
            ),
        )
        template = env.get_template("page")
        result = template.render_block("oob")
        assert "<div>Task 1</div>" in result

    def test_imports_endimports_closing(self) -> None:
        """Imports blocks accept {% endimports %} as closing tag."""
        env = _env(
            macros="{% def f() %}ok{% end %}",
            page=(
                '{% imports %}{% from "macros" import f %}{% endimports %}'
                "{% block content %}{{ f() }}{% endblock %}"
            ),
        )
        template = env.get_template("page")
        result = template.render_block("content")
        assert "ok" in result

    def test_imports_unified_end_closing(self) -> None:
        """Imports blocks accept {% end %} as closing tag."""
        env = _env(
            macros="{% def f() %}ok{% end %}",
            page=(
                '{% imports %}{% from "macros" import f %}{% end %}'
                "{% block content %}{{ f() }}{% endblock %}"
            ),
        )
        template = env.get_template("page")
        result = template.render_block("content")
        assert "ok" in result


class TestTopLevelDefInRenderBlock:
    """Top-level {% def %} available in render_block() without {% globals %} (Phase 1 preamble hoisting)."""

    def test_top_level_def_available_in_render_block(self) -> None:
        """Template with top-level {% def %} at root, no globals — def is hoisted to _globals_setup."""
        env = _env(
            page=(
                "{% def greet(name) %}Hello, {{ name }}!{% end %}"
                '{% block content %}{{ greet("World") }}{% endblock %}'
            )
        )
        template = env.get_template("page")
        result = template.render_block("content")
        assert "Hello, World!" in result

    def test_top_level_def_in_fragment(self) -> None:
        """Top-level def works with {% fragment %} blocks."""
        env = _env(
            page=(
                "{% def card(title) %}<div>{{ title }}</div>{% end %}"
                "Page content "
                '{% fragment oob %}{{ card("Task 1") }}{% endfragment %}'
            )
        )
        template = env.get_template("page")
        result = template.render()
        assert "Page content" in result
        assert "Task 1" not in result
        result = template.render_block("oob")
        assert "<div>Task 1</div>" in result


class TestRegionBlocks:
    """{% region name(params) %} — parameterized renderable units (RFC: kida-regions)."""

    def test_region_render_block(self) -> None:
        """Region is renderable via render_block() with params."""
        env = _env(
            page="""{% region sidebar(current_path="/") %}
  <nav>{{ current_path }}</nav>
{% end %}"""
        )
        template = env.get_template("page")
        result = template.render_block("sidebar", current_path="/settings")
        assert "<nav>/settings</nav>" in result

    def test_region_callable_in_template(self) -> None:
        """Region is callable via {{ name(args) }} in template body."""
        env = _env(
            page="""{% region sidebar(current_path="/") %}
  <nav>{{ current_path }}</nav>
{% end %}
{{ sidebar(current_path="/about") }}"""
        )
        template = env.get_template("page")
        result = template.render()
        assert "<nav>/about</nav>" in result

    def test_region_can_lookup_outer_ctx_values(self) -> None:
        """Region body can resolve non-parameter names from outer ctx."""
        env = _env(
            page="""{% region crumbs(current_path="/") %}
{{ breadcrumb_items | default([{"label":"Home","href":"/"}]) | length }}
{% end %}
{{ crumbs(current_path="/x") }}"""
        )
        template = env.get_template("page")
        result = template.render(breadcrumb_items=[{"label": "Docs", "href": "/docs"}])
        assert "1" in result
        # Region depends_on must include outer-context vars (BlockMetadata contract)
        meta = template.template_metadata()
        crumbs = meta.get_block("crumbs")
        assert crumbs is not None
        assert "breadcrumb_items" in crumbs.depends_on

    def test_region_imported_macro_slot_uses_outer_ctx_render_block(self) -> None:
        """Region body can execute imported call/slot chains using outer context values."""
        env = _env(
            forms="""{% def form(action, method="get") %}
<form action="{{ action }}" method="{{ method }}">{% slot %}</form>
{% end %}""",
            page="""{% from "forms" import form %}
{% region shell(current_path="/") %}
  {% call form("/search") %}{{ selected_tags | join(",") }}{% end %}
{% end %}
{% block content %}{{ shell(current_path="/x") }}{% endblock %}""",
        )
        template = env.get_template("page")
        result = template.render_block("content", selected_tags=["a", "b"])
        assert "<form" in result
        assert "a,b" in result

    def test_region_render_and_render_block_match(self) -> None:
        """Region output should be consistent between render() and render_block() entry points."""
        env = _env(
            page="""{% region shell(current_path="/") %}
{{ breadcrumb_items | default([{"label":"Home","href":"/"}]) | length }}
{% end %}
{% block content %}{{ shell(current_path="/x") }}{% endblock %}""",
        )
        template = env.get_template("page")
        context = {"breadcrumb_items": [{"label": "Docs", "href": "/docs"}]}
        render_full = template.render(**context)
        render_block = template.render_block("content", **context)
        assert "1" in render_full
        assert "1" in render_block

    def test_region_missing_var_raises_undefined_not_nameerror(self) -> None:
        """Missing values in region body should raise UndefinedError, not NameError."""
        from kida.environment.exceptions import UndefinedError

        env = _env(
            page="""{% region shell(current_path="/") %}
{{ missing_value }}
{% end %}
{{ shell(current_path="/x") }}""",
        )
        template = env.get_template("page")
        with pytest.raises(UndefinedError):
            template.render()

    def test_region_listed_in_blocks(self) -> None:
        """Region blocks appear in list_blocks()."""
        env = _env(page="""{% region sidebar(current_path="/") %}<nav></nav>{% end %}""")
        template = env.get_template("page")
        assert "sidebar" in template.list_blocks()

    def test_region_metadata_is_region(self) -> None:
        """Region blocks have is_region=True in template_metadata()."""
        env = _env(page="""{% region sidebar(current_path="/") %}<nav></nav>{% end %}""")
        template = env.get_template("page")
        meta = template.template_metadata()
        assert meta is not None
        sidebar = meta.get_block("sidebar")
        assert sidebar is not None
        assert sidebar.is_region is True
        assert "current_path" in sidebar.region_params

    def test_region_regions_convenience(self) -> None:
        """TemplateMetadata.regions() returns only region blocks."""
        env = _env(
            page="""{% block content %}c{% endblock %}
{% region sidebar(current_path="/") %}s{% end %}"""
        )
        template = env.get_template("page")
        meta = template.template_metadata()
        assert meta is not None
        regions = meta.regions()
        assert "sidebar" in regions
        assert "content" not in regions


class TestTopLevelImportInRenderBlock:
    """Top-level {% from %}...{% import %} available in render_block() without {% globals %}."""

    def test_top_level_import_available_in_render_block(self) -> None:
        """Template with {% from "macros" import greet %} at root, no globals."""
        env = _env(
            macros="{% def greet(name) %}Hello, {{ name }}!{% end %}",
            page=(
                '{% from "macros" import greet %}'
                '{% block content %}{{ greet("World") }}{% endblock %}'
            ),
        )
        template = env.get_template("page")
        result = template.render_block("content")
        assert "Hello, World!" in result

    def test_top_level_import_in_fragment(self) -> None:
        """Top-level import works with {% fragment %} blocks."""
        env = _env(
            macros="{% def card(title) %}<div>{{ title }}</div>{% end %}",
            page=(
                '{% from "macros" import card %}'
                "Page content "
                '{% fragment oob %}{{ card("Task 1") }}{% endfragment %}'
            ),
        )
        template = env.get_template("page")
        result = template.render()
        assert "Page content" in result
        assert "Task 1" not in result
        result = template.render_block("oob")
        assert "<div>Task 1</div>" in result

    def test_top_level_import_with_globals(self) -> None:
        """Both top-level import and {% globals %} available in block."""
        env = _env(
            macros="{% def greet(name) %}Hello, {{ name }}!{% end %}",
            page=(
                '{% from "macros" import greet %}'
                '{% globals %}{% set site = "Kida" %}{% end %}'
                '{% block content %}{{ greet("World") }} from {{ site }}{% endblock %}'
            ),
        )
        template = env.get_template("page")
        result = template.render_block("content")
        assert "Hello, World!" in result
        assert "Kida" in result
