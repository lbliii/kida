"""Tests for static escape and trusted-markup audit findings."""

from __future__ import annotations

from kida import Environment
from kida.analysis.escape_audit import audit_escaping


def test_audit_reports_escaped_output_site() -> None:
    env = Environment()
    template = env.from_string("{{ page.title }}", name="page.html")

    findings = audit_escaping(template)

    assert [(f.code, f.kind, f.expression) for f in findings] == [
        ("K-ESC-001", "escaped-output", "page.title")
    ]
    assert findings[0].template_name == "page.html"


def test_audit_reports_safe_filter_with_reason() -> None:
    env = Environment()
    template = env.from_string(
        '{{ body_html | safe(reason="sanitized by bleach") }}',
        name="post.html",
    )

    findings = audit_escaping(template, include_output_sites=False)

    assert len(findings) == 1
    assert findings[0].code == "K-ESC-002"
    assert findings[0].kind == "safe-filter"
    assert findings[0].expression == "body_html"
    assert "sanitized by bleach" in findings[0].message
    assert findings[0].suggestion is None


def test_audit_reports_safe_filter_without_reason() -> None:
    env = Environment()
    template = env.from_string("{{ body_html | safe }}", name="post.html")

    findings = audit_escaping(template, include_output_sites=False)

    assert len(findings) == 1
    assert findings[0].code == "K-ESC-002"
    assert findings[0].severity == "warning"
    assert "safe(reason=" in (findings[0].suggestion or "")


def test_audit_reports_autoescape_disabled_output() -> None:
    env = Environment(autoescape=False)
    template = env.from_string("{{ body_html }}", name="raw.html")

    findings = audit_escaping(template)

    assert [(f.code, f.kind) for f in findings] == [
        ("K-ESC-003", "unescaped-output"),
    ]


def test_audit_reports_tojson_and_xmlattr() -> None:
    env = Environment()
    template = env.from_string(
        "{{ payload | tojson(attr=true) }} {{ attrs | xmlattr }}",
        name="data.html",
    )

    findings = audit_escaping(template, include_output_sites=False)

    assert [(f.code, f.kind, f.expression) for f in findings] == [
        ("K-ESC-004", "tojson", "payload"),
        ("K-ESC-005", "xmlattr", "attrs"),
    ]


def test_audit_no_ast_returns_empty() -> None:
    env = Environment()
    template = env.from_string("{{ value }}")
    template._optimized_ast = None

    assert audit_escaping(template) == []
