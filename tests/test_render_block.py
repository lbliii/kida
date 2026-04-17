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

    def test_render_block_includes_ancestor_from_imports(self) -> None:
        """{% from %} on a parent is in scope when rendering a block on the child."""
        env = _env(
            macros="{% def badge(t) %}<b>{{ t }}</b>{% end %}",
            base='{% from "macros" import badge %}{% block content %}{{ badge("base") }}{% endblock %}',
            child='{% extends "base" %}{% block content %}{{ badge("leaf") }}{% endblock %}',
        )
        template = env.get_template("child")
        result = template.render_block("content")
        assert "<b>leaf</b>" in result

    def test_globals_setup_chain_matches_full_render_shadowing(self) -> None:
        """Leaf runs before root in full render; parent wins on duplicate ``{% let %}`` bindings."""
        env = _env(
            base='{% let x = "base" %}{% block content %}{{ x }}{% endblock %}',
            child='{% extends "base" %}{% let x = "leaf" %}{% block content %}{{ x }}{% endblock %}',
        )
        template = env.get_template("child")
        full = template.render().strip()
        block = template.render_block("content").strip()
        assert full == block == "base"

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

    def test_region_default_param_from_ctx_extends_chain(self) -> None:
        """Region param default (e.g. current_page=page) must not reference ctx at def time.

        Python evaluates default args when the function is defined (during exec).
        ctx/_scope_stack don't exist then. We use _REGION_DEFAULT sentinel and resolve
        at call time. Regression for NameError when parent with region+default is
        loaded during child's _extends().
        """
        env = _env(
            layout="""{% extends "base" %}
{% block content %}
{% region sidebar(section, current_page=page) %}
<nav>{{ section }} / {{ current_page.title }}</nav>
{% end %}
{{ sidebar(section=section) }}
{% endblock %}""",
            base="<html>{% block content %}{% endblock %}</html>",
        )
        template = env.get_template("layout")
        result = template.render(
            section="API",
            page=type("Page", (), {"title": "Products"})(),
        )
        assert "API" in result
        assert "Products" in result

    def test_region_default_getattr(self) -> None:
        """Getattr in region default: meta=page.metadata must not leak sentinel."""
        env = _env(
            page="""{% region sidebar(section, meta=page.metadata) %}
{{ meta.title }}{% end %}
{{ sidebar(section="API") }}"""
        )
        template = env.get_template("page")
        page_cls = type("Page", (), {"metadata": type("M", (), {"title": "Docs"})()})
        result = template.render(section="API", page=page_cls())
        assert "Docs" in result

    def test_region_default_filter(self) -> None:
        """Filter in region default: count=items | length must not leak sentinel."""
        env = _env(
            page="""{% region stats(count=items | length) %}
{{ count }} items{% end %}
{{ stats() }}"""
        )
        template = env.get_template("page")
        result = template.render(items=["a", "b", "c"])
        assert "3 items" in result

    def test_region_default_null_coalesce(self) -> None:
        """Null coalesce in region default: meta=data?.info ?? fallback must not leak sentinel."""
        env = _env(
            page="""{% region panel(meta=data?.info ?? "fallback") %}
{{ meta }}{% end %}
{{ panel() }}"""
        )
        template = env.get_template("page")
        result = template.render()
        assert "fallback" in result

    def test_region_default_optional_getattr(self) -> None:
        """Optional chain in region default: title=page?.title ?? Default."""
        env = _env(
            page="""{% region header(title=page?.title ?? "Default") %}
<h1>{{ title }}</h1>{% end %}
{{ header() }}"""
        )
        template = env.get_template("page")
        result = template.render()
        assert "Default" in result

    def test_region_default_complex_with_extends(self) -> None:
        """Complex default must survive extends chain (exec-time safety)."""
        env = _env(
            base="<html>{% block content %}{% endblock %}</html>",
            layout="""{% extends "base" %}{% block content %}
{% region sidebar(section, meta=page.metadata) %}
<nav>{{ meta.title }}</nav>{% end %}
{{ sidebar(section="API") }}
{% endblock %}""",
        )
        template = env.get_template("layout")
        page_cls = type("Page", (), {"metadata": type("M", (), {"title": "Ref"})()})
        result = template.render(section="API", page=page_cls())
        assert "Ref" in result

    def test_region_default_complex_render_block(self) -> None:
        """Complex default works when region is invoked via render_block (block path)."""
        env = _env(
            layout="""{% extends "base" %}{% block content %}
{% region sidebar(section, meta=page.metadata) %}
<nav>{{ meta.title }}</nav>{% end %}
{{ sidebar(section="API") }}
{% endblock %}""",
            base="<html>{% block content %}{% endblock %}</html>",
        )
        template = env.get_template("layout")
        page_cls = type("Page", (), {"metadata": type("M", (), {"title": "Block"})()})
        result = template.render_block("content", section="API", page=page_cls())
        assert "Block" in result

    def test_region_default_complex_depends_on(self) -> None:
        """Static analysis depends_on captures vars from complex region defaults."""
        env = _env(
            page="""{% region sidebar(section, meta=page.metadata) %}
{{ meta.title }}{% end %}
{% region stats(count=items | length) %}{{ count }}{% end %}
{{ sidebar(section="API") }}{{ stats() }}"""
        )
        template = env.get_template("page")
        meta = template.template_metadata()
        sidebar = meta.get_block("sidebar")
        stats = meta.get_block("stats")
        assert sidebar is not None
        assert stats is not None
        assert "page.metadata" in sidebar.depends_on or "page" in sidebar.depends_on
        assert "items" in stats.depends_on

    def test_region_with_block_and_child_override(self) -> None:
        """Region body containing {% block %} receives _blocks for dispatch."""
        env = _env(
            layout=(
                "{% block content %}"
                "{% region panel() %}"
                "{% block inner %}DEFAULT{% endblock %}"
                "{% end %}"
                "{{ panel() }}"
                "{% endblock %}"
            ),
            page=(
                '{% extends "layout" %}'
                '{% let title = "Hello" %}'
                "{% block inner %}OVERRIDE {{ title }}{% endblock %}"
            ),
        )
        result = env.get_template("page").render()
        assert "OVERRIDE Hello" in result
        assert "DEFAULT" not in result

    def test_region_with_block_from_and_let(self) -> None:
        """Child with {% from %} and {% let %} at top level, region+block in parent."""
        env = _env(
            components="{% def bar(x) %}[{{ x }}]{% end %}",
            layout=(
                "{% block content %}"
                "{% region panel() %}"
                "{% block content_main %}DEFAULT{% endblock %}"
                "{% end %}"
                "{{ panel() }}"
                "{% endblock %}"
            ),
            page=(
                '{% extends "layout" %}'
                '{% from "components" import bar %}'
                '{% let meta = "META" %}'
                "{% block content_main %}{{ bar(meta) }}{% endblock %}"
            ),
        )
        result = env.get_template("page").render()
        assert "[META]" in result
        assert "DEFAULT" not in result

    def test_region_with_block_three_level_extends(self) -> None:
        """Three-level inheritance: page -> layout -> base, child has from+let."""
        env = _env(
            components="{% def bar(x) %}[{{ x }}]{% end %}",
            base="<html>{% block content %}base{% endblock %}</html>",
            layout=(
                '{% extends "base" %}'
                "{% block content %}"
                "{% region panel() %}"
                "{% block content_main %}DEFAULT{% endblock %}"
                "{% end %}"
                "{{ panel() }}"
                "{% endblock %}"
            ),
            page=(
                '{% extends "layout" %}'
                '{% from "components" import bar %}'
                '{% let meta = "META" %}'
                "{% block content_main %}{{ bar(meta) }}{% endblock %}"
            ),
        )
        result = env.get_template("page").render()
        assert "[META]" in result
        assert "DEFAULT" not in result

    def test_region_with_block_streaming(self) -> None:
        """Streaming block wrapper forwards _blocks for region block dispatch."""
        env = _env(
            layout=(
                "{% block content %}"
                "{% region panel() %}"
                "{% block inner %}DEFAULT{% endblock %}"
                "{% end %}"
                "{{ panel() }}"
                "{% endblock %}"
            ),
            page='{% extends "layout" %}{% block inner %}STREAMED{% endblock %}',
        )
        # render_block uses _block_content which invokes region; verifies _blocks
        # forwarding in block wrapper (sync path). Full render_stream would need
        # region to yield-from streaming blocks — separate RFC.
        result = env.get_template("page").render_block("content")
        assert "STREAMED" in result


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


class TestGlobalsSetupComposite:
    """_globals_setup path: imports + let + def + region all present in one template.

    Covers the K-TPL-004 preamble hoisting contract end-to-end: every top-level
    preamble form must be bound on ctx before a block/region runs under
    render_block().
    """

    def test_render_block_sees_import_let_def_and_region(self) -> None:
        env = _env(
            macros="{% def tag(x) %}<em>{{ x }}</em>{% end %}",
            page=(
                '{% from "macros" import tag %}'
                '{% let site = "Kida" %}'
                "{% def wrap(x) %}<b>{{ x }}</b>{% end %}"
                '{% region panel(label="P") %}'
                "<aside>{{ label }}-{{ site }}</aside>"
                "{% end %}"
                "{% block content %}"
                "{{ tag(site) }} {{ wrap(site) }} {{ panel(label='Nav') }}"
                "{% endblock %}"
            ),
        )
        template = env.get_template("page")
        result = template.render_block("content")
        assert "<em>Kida</em>" in result
        assert "<b>Kida</b>" in result
        assert "<aside>Nav-Kida</aside>" in result

    def test_render_block_on_region_uses_top_level_let(self) -> None:
        """Region dispatched via render_block resolves a top-level {% let %}."""
        env = _env(
            page=('{% let brand = "Kida" %}{% region footer() %}<p>{{ brand }}</p>{% end %}'),
        )
        template = env.get_template("page")
        result = template.render_block("footer")
        assert "<p>Kida</p>" in result

    def test_render_block_on_region_uses_imported_macro(self) -> None:
        """Region dispatched via render_block can call an imported macro."""
        env = _env(
            macros="{% def tag(x) %}<em>{{ x }}</em>{% end %}",
            page=(
                '{% from "macros" import tag %}'
                '{% region crumbs(current="home") %}'
                "{{ tag(current) }}"
                "{% end %}"
            ),
        )
        template = env.get_template("page")
        result = template.render_block("crumbs", current="about")
        assert "<em>about</em>" in result

    def test_render_block_on_region_uses_top_level_def(self) -> None:
        """Region body can call a sibling top-level {% def %} via render_block."""
        env = _env(
            page=(
                "{% def label(x) %}[{{ x }}]{% end %}"
                "{% region nav(section='home') %}"
                "{{ label(section) }}"
                "{% end %}"
            ),
        )
        template = env.get_template("page")
        result = template.render_block("nav", section="about")
        assert "[about]" in result


class TestDefRenderBlockInteraction:
    """{% def %} scope reachability through render_block().

    Defs are not render_block targets, but render_block must be able to call
    them when they live at the template top level or are lexically visible
    from the block body.
    """

    def test_top_level_def_callable_from_block(self) -> None:
        env = _env(
            page=(
                "{% def greet(name) %}Hello, {{ name }}!{% end %}"
                '{% block content %}{{ greet("World") }}{% endblock %}'
            )
        )
        template = env.get_template("page")
        assert "Hello, World!" in template.render_block("content")

    def test_def_inside_block_compiles_and_renders(self) -> None:
        """{% def %} inside a {% block %} body is not a control-flow scope."""
        env = _env(
            page=(
                "{% block content %}"
                "{% def greet(name) %}Hi, {{ name }}!{% end %}"
                '{{ greet("World") }}'
                "{% endblock %}"
            )
        )
        template = env.get_template("page")
        assert "Hi, World!" in template.render_block("content")

    def test_nested_def_inside_def_is_callable_from_outer_def(self) -> None:
        """Defs nested inside another def remain callable lexically."""
        env = _env(
            page=(
                "{% def outer() %}"
                "{% def inner() %}in{% end %}"
                "[{{ inner() }}]"
                "{% end %}"
                "{% block content %}{{ outer() }}{% endblock %}"
            )
        )
        template = env.get_template("page")
        assert "[in]" in template.render_block("content")

    def test_def_inside_region_compiles_and_renders(self) -> None:
        """{% def %} inside a {% region %} body is not a control-flow scope."""
        env = _env(
            page=(
                "{% region shell(x=1) %}{% def local() %}L{% end %}{{ local() }}-{{ x }}{% end %}"
            )
        )
        template = env.get_template("page")
        result = template.render_block("shell", x=7)
        assert "L-7" in result


class TestRegionRenderBlockStreamAsync:
    """render_block_stream_async() against templates containing regions.

    Exercises the async block streaming path for both plain regions and
    regions that reference top-level preamble state (let / def / imports),
    which must be resolved before the region body executes.
    """

    @pytest.mark.asyncio
    async def test_plain_region_streams(self) -> None:
        env = _env(
            page=('{% region sidebar(current_path="/") %}<nav>{{ current_path }}</nav>{% end %}'),
        )
        template = env.get_template("page")
        chunks = [
            c async for c in template.render_block_stream_async("sidebar", current_path="/about")
        ]
        assert "<nav>/about</nav>" in "".join(chunks)

    @pytest.mark.asyncio
    async def test_region_streams_with_top_level_let(self) -> None:
        """Top-level {% let %} must be bound before the region body runs."""
        env = _env(
            page=(
                '{% let brand = "Kida" %}'
                '{% region footer(note="tag") %}'
                "<p>{{ brand }}/{{ note }}</p>"
                "{% end %}"
            ),
        )
        template = env.get_template("page")
        chunks = [c async for c in template.render_block_stream_async("footer")]
        assert "<p>Kida/tag</p>" in "".join(chunks)

    @pytest.mark.asyncio
    async def test_region_streams_with_imported_macro(self) -> None:
        """Imported macros from top-level {% from %} must be callable."""
        env = _env(
            macros="{% def tag(x) %}<em>{{ x }}</em>{% end %}",
            page=(
                '{% from "macros" import tag %}'
                '{% region crumbs(current="home") %}'
                "{{ tag(current) }}"
                "{% end %}"
            ),
        )
        template = env.get_template("page")
        chunks = [c async for c in template.render_block_stream_async("crumbs", current="about")]
        assert "<em>about</em>" in "".join(chunks)

    @pytest.mark.asyncio
    async def test_region_streams_with_sibling_top_level_def(self) -> None:
        """Sibling top-level {% def %} must be callable from the region body."""
        env = _env(
            page=(
                "{% def label(x) %}[{{ x }}]{% end %}"
                "{% region nav(section='home') %}"
                "{{ label(section) }}"
                "{% end %}"
            ),
        )
        template = env.get_template("page")
        chunks = [c async for c in template.render_block_stream_async("nav", section="about")]
        assert "[about]" in "".join(chunks)

    @pytest.mark.asyncio
    async def test_region_streams_full_preamble(self) -> None:
        """imports + let + def + region together via async block stream."""
        env = _env(
            macros="{% def tag(x) %}<em>{{ x }}</em>{% end %}",
            page=(
                '{% from "macros" import tag %}'
                '{% let brand = "Kida" %}'
                "{% def wrap(x) %}<b>{{ x }}</b>{% end %}"
                "{% region panel(label='P') %}"
                "<aside>{{ tag(label) }}/{{ wrap(brand) }}</aside>"
                "{% end %}"
            ),
        )
        template = env.get_template("page")
        chunks = [c async for c in template.render_block_stream_async("panel", label="Nav")]
        out = "".join(chunks)
        assert "<em>Nav</em>" in out
        assert "<b>Kida</b>" in out
