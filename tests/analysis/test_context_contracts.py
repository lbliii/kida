"""Tests for route-agnostic context contract checks."""

from __future__ import annotations

from kida import DictLoader, Environment
from kida.analysis.context_contracts import check_context_contract


def test_context_contract_accepts_dotted_paths() -> None:
    env = Environment()
    template = env.from_string("{{ page.title }} {{ site.name }}", name="page.html")

    issues = check_context_contract(template, {"page.title", "site.name"})

    assert issues == []


def test_context_contract_reports_missing_dotted_paths() -> None:
    env = Environment()
    template = env.from_string("{{ page.title }} {{ site.name }}", name="page.html")

    issues = check_context_contract(template, {"page"})

    assert [issue.path for issue in issues] == ["page.title", "site.name"]
    assert all(issue.code == "K-CTX-001" for issue in issues)
    assert all(issue.severity == "error" for issue in issues)
    assert issues[0].template_name == "page.html"
    assert "route context contract" in (issues[0].suggestion or "")


def test_context_contract_accepts_nested_mapping_shape() -> None:
    env = Environment()
    template = env.from_string("{{ page.title }} {{ page.author.name }}", name="page.html")

    issues = check_context_contract(
        template,
        {"page": {"title": str, "author": {"name": str}}},
    )

    assert issues == []


def test_context_contract_accounts_for_optional_and_globals() -> None:
    env = Environment(
        loader=DictLoader({"page.html": "{{ page.title }} {{ csrf_token }} {{ flash.message }}"})
    )
    template = env.get_template("page.html")

    issues = check_context_contract(
        template,
        {"page.title"},
        optional={"flash.message"},
        globals={"csrf_token"},
    )

    assert issues == []


def test_context_contract_can_report_extra_paths() -> None:
    env = Environment()
    template = env.from_string("{{ page.title }}", name="page.html")

    issues = check_context_contract(
        template,
        {"page.title", "debug_payload"},
        check_extra=True,
    )

    assert [(issue.code, issue.severity, issue.path) for issue in issues] == [
        ("K-CTX-002", "warning", "debug_payload")
    ]


def test_context_contract_uses_template_dependency_scope() -> None:
    env = Environment()
    template = env.from_string(
        "{% def card(title) %}{{ title }} {{ site.name }}{% end %}{{ card(page.title) }}",
        name="components.html",
    )

    issues = check_context_contract(template, {"page.title", "site.name"})

    assert issues == []
