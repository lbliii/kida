"""Executable probes for the Jinja migration transform-safety audit.

These tests describe current behavior only. They do not implement a source
rewriter or establish a new migration API.
"""

from __future__ import annotations

import warnings
from types import SimpleNamespace

import pytest
from jinja2 import DictLoader as JinjaDictLoader
from jinja2 import Environment as JinjaEnvironment

from kida import DictLoader, Environment, TemplateSyntaxError, UndefinedError
from kida.exceptions import ErrorCode, MigrationWarning


@pytest.fixture
def flask_macro_pair() -> tuple[str, str]:
    """A restricted Flask/Jinja macro and its keyword-only Kida rewrite."""
    jinja_source = """\
{# keep: Flask helper formatting #}
{% macro badge(label, tone="info") -%}
  <span class="badge {{ tone }}">{{ label }}</span>
{%- endmacro %}
{{ badge(label, tone="success") }}
"""
    kida_source = jinja_source.replace("{% macro", "{% def").replace("{%- endmacro", "{%- enddef")
    return jinja_source, kida_source


@pytest.fixture
def django_template_source() -> str:
    """A representative Django template with framework-owned vocabulary."""
    return """\
{% load humanize %}
<a href="{% url 'invoice-detail' invoice.pk %}">
  {{ invoice.created_at | naturaltime }}
</a>
"""


def test_explicit_closers_are_an_already_accepted_noop() -> None:
    source = (
        "{% if visible %}{% for item in items %}[{{ item }}]{% endfor %}{% else %}hidden{% endif %}"
    )
    context = {"visible": True, "items": ("a", "b")}

    jinja_output = JinjaEnvironment(autoescape=True).from_string(source).render(**context)
    kida_output = Environment(autoescape=True).from_string(source).render(**context)

    assert kida_output == jinja_output == "[a][b]"


def test_restricted_macro_keyword_edit_is_equivalent_and_preserves_layout(
    flask_macro_pair: tuple[str, str],
) -> None:
    jinja_source, kida_source = flask_macro_pair

    assert kida_source == jinja_source.replace("{% macro", "{% def").replace(
        "{%- endmacro", "{%- enddef"
    )
    assert "{# keep: Flask helper formatting #}" in kida_source
    assert "\n  <span" in kida_source

    jinja_output = JinjaEnvironment(autoescape=True).from_string(jinja_source).render(label="Ready")
    kida_output = Environment(autoescape=True).from_string(kida_source).render(label="Ready")

    assert kida_output.strip() == jinja_output.strip()


def test_set_scope_requires_block_sensitive_analysis() -> None:
    if_source = "{% set value = 1 %}{% if true %}{% set value = 2 %}{% endif %}{{ value }}"
    loop_source = (
        "{% set value = 1 %}{% for item in [1] %}{% set value = 2 %}{% endfor %}{{ value }}"
    )

    assert JinjaEnvironment().from_string(if_source).render() == "2"
    assert Environment().from_string(if_source).render() == "1"
    assert JinjaEnvironment().from_string(loop_source).render() == "1"
    assert Environment().from_string(loop_source).render() == "1"


def test_k_warn_002_is_advisory_and_has_no_edit_payload() -> None:
    source = "{% let value = 1 %}{% if true %}{% set value = 2 %}{% endif %}{{ value }}"

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        template = Environment(jinja2_compat_warnings=True).from_string(source)

    assert [warning.code for warning in template.warnings] == [ErrorCode.JINJA2_SET_SCOPING]
    assert (
        template.warnings[0].suggestion == "Use {% export value = ... %} to write to outer scope."
    )
    assert not hasattr(template.warnings[0], "safe_edit")
    assert any(issubclass(item.category, MigrationWarning) for item in captured)


def test_dynamic_include_can_render_but_has_no_static_template_identity() -> None:
    templates = {"page.html": "{% include template_name %}", "partial.html": "partial"}

    jinja_output = (
        JinjaEnvironment(loader=JinjaDictLoader(templates))
        .get_template("page.html")
        .render(template_name="partial.html")
    )
    kida_template = Environment(loader=DictLoader(templates)).get_template("page.html")

    assert kida_template.render(template_name="partial.html") == jinja_output == "partial"
    metadata = kida_template.template_metadata()
    assert metadata is not None
    assert metadata.top_level_depends_on == frozenset({"template_name"})


def test_super_requires_manual_inheritance_redesign() -> None:
    templates = {
        "base.html": "{% block body %}Base{% endblock %}",
        "child.html": (
            '{% extends "base.html" %}{% block body %}{{ super() }}+Child{% endblock %}'
        ),
    }

    assert (
        JinjaEnvironment(loader=JinjaDictLoader(templates)).get_template("child.html").render()
        == "Base+Child"
    )
    with pytest.raises(UndefinedError, match="super"):
        Environment(loader=DictLoader(templates)).get_template("child.html").render()


def test_namespace_mutation_is_not_a_keyword_rewrite() -> None:
    source = (
        "{% set ns = namespace(count=0) %}"
        "{% for item in [1, 2] %}"
        "{% set ns.count = ns.count + 1 %}"
        "{% endfor %}"
        "{{ ns.count }}"
    )

    assert JinjaEnvironment().from_string(source).render() == "2"
    with pytest.raises(TemplateSyntaxError):
        Environment().from_string(source)


def test_flask_implicit_global_requires_environment_inventory() -> None:
    source = "{% macro current_path() %}{{ request.path }}{% endmacro %}{{ current_path() }}"
    request = SimpleNamespace(path="/settings")
    jinja_env = JinjaEnvironment()

    assert jinja_env.from_string(source, globals={"request": request}).render() == "/settings"

    kida_source = source.replace("{% macro", "{% def").replace("{% endmacro", "{% enddef")
    with pytest.raises(UndefinedError, match="request"):
        Environment().from_string(kida_source).render()

    kida_env = Environment()
    kida_env.add_global("request", request)
    assert kida_env.from_string(kida_source).render() == "/settings"


def test_django_tags_and_filters_require_framework_specific_mapping(
    django_template_source: str,
) -> None:
    with pytest.raises(TemplateSyntaxError, match="Unknown block keyword: load"):
        Environment().from_string(django_template_source)


def test_missing_filter_and_test_fail_during_kida_compilation() -> None:
    with pytest.raises(TemplateSyntaxError, match="Unknown filter 'naturaltime'"):
        Environment().from_string("{{ created_at | naturaltime }}")
    with pytest.raises(TemplateSyntaxError, match="Unknown test 'feature_enabled'"):
        Environment().from_string("{% if flag is feature_enabled %}yes{% endif %}")


def test_jinja_macro_metadata_requires_manual_review(
    flask_macro_pair: tuple[str, str],
) -> None:
    jinja_source, kida_source = flask_macro_pair
    jinja_source += '{{ badge.arguments | join(",") }}'
    kida_source += '{{ badge.arguments | join(",") }}'

    assert "label,tone" in JinjaEnvironment().from_string(jinja_source).render(label="Ready")
    with pytest.raises(UndefinedError, match="arguments"):
        Environment().from_string(kida_source).render(label="Ready")
