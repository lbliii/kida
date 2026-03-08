"""Render-output regression guards for duplication/emptiness failures."""

from kida import DictLoader, Environment


def _env(**templates: str) -> Environment:
    return Environment(loader=DictLoader(templates))


def test_nonempty_template_render_is_not_empty() -> None:
    env = _env(page="<main>{{ title }}</main>")
    template = env.get_template("page")
    result = template.render(title="Autodoc")
    assert result.strip()
    assert "<main>Autodoc</main>" in result


def test_loop_render_output_count_matches_input_count_exactly() -> None:
    env = _env(page="{% for item in items %}<li>{{ item }}</li>{% endfor %}")
    template = env.get_template("page")
    items = [f"item-{i}" for i in range(25)]
    result = template.render(items=items)
    assert result.count("<li>") == len(items)
    assert result.count("</li>") == len(items)


def test_include_chain_renders_expected_occurrence_count() -> None:
    env = _env(
        row='<div class="row">row</div>',
        page=('{% include "row" %}{% include "row" %}{% include "row" %}{% include "row" %}'),
    )
    template = env.get_template("page")
    result = template.render()
    assert result.count('<div class="row">') == 4


def test_inheritance_block_does_not_duplicate_parent_and_child_content() -> None:
    env = _env(
        base='<body>{% block content %}<p class="base">base</p>{% endblock %}</body>',
        child=('{% extends "base" %}{% block content %}<p class="child">child</p>{% endblock %}'),
    )
    template = env.get_template("child")
    result = template.render()
    assert result.count('<p class="child">') == 1
    assert '<p class="base">' not in result


def test_stream_output_matches_render_output_for_large_template() -> None:
    env = _env(page="{% for i in range(count) %}<section>{{ i }}</section>{% endfor %}")
    template = env.get_template("page")
    context = {"count": 300}
    rendered = template.render(**context)
    streamed = "".join(template.render_stream(**context))
    assert streamed == rendered


def test_fragment_skipped_in_full_render_preserves_non_fragment_content() -> None:
    env = _env(
        page=(
            'before{% fragment details %}<details class="autodoc-member"></details>{% end %}after'
        )
    )
    template = env.get_template("page")
    result = template.render()
    assert "before" in result
    assert "after" in result
    assert '<details class="autodoc-member">' not in result


def test_repeated_renders_do_not_accumulate_exported_collection_state() -> None:
    """
    Regression guard: export-accumulated collections must not grow across renders.

    This was the practical failure mode behind autodoc output bloat.
    """
    env = _env(
        page=(
            "{% let items = [] %}"
            "{% for x in values %}{% export items = items + [x] %}{% end %}"
            "{% for x in items %}<li>{{ x }}</li>{% end %}"
        )
    )
    template = env.get_template("page")
    first = template.render(values=["a", "b", "c"])
    second = template.render(values=["a", "b", "c"])
    assert first.count("<li>") == 3
    assert second.count("<li>") == 3
    assert first == second
