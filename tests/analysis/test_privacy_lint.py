"""Tests for static privacy lint findings."""

from __future__ import annotations

from kida import Environment
from kida.analysis.privacy import lint_privacy


def test_privacy_lint_reports_sensitive_context_paths() -> None:
    env = Environment()
    template = env.from_string("{{ user.email }} {{ session.token }}", name="profile.html")

    findings = lint_privacy(template)

    assert [(f.code, f.kind, f.path) for f in findings] == [
        ("K-PRI-001", "sensitive-context-path", "session.token"),
        ("K-PRI-001", "sensitive-context-path", "user.email"),
    ]
    assert {f.template_name for f in findings} == {"profile.html"}


def test_privacy_lint_redacts_secret_like_literals() -> None:
    env = Environment()
    template = env.from_string("{{ 'api_key=sk_live_1234567890' }}", name="fixture.html")

    findings = lint_privacy(template)

    assert len(findings) == 1
    assert findings[0].code == "K-PRI-002"
    assert findings[0].kind == "secret-like-literal"
    assert "sk_live" not in findings[0].message


def test_privacy_lint_reports_safe_sensitive_values() -> None:
    env = Environment()
    template = env.from_string("{{ user.private_note | safe }}", name="profile.html")

    findings = lint_privacy(template)

    assert ("K-PRI-003", "safe-sensitive-value", "user.private_note") in [
        (f.code, f.kind, f.path) for f in findings
    ]


def test_privacy_lint_reports_broad_context_output() -> None:
    env = Environment()
    template = env.from_string("{{ context }}", name="debug.html")

    findings = lint_privacy(template)

    assert [(f.code, f.kind, f.path) for f in findings] == [
        ("K-PRI-004", "broad-context-output", "context")
    ]


def test_privacy_lint_reports_dynamic_include() -> None:
    env = Environment()
    template = env.from_string("{% include template_name %}", name="page.html")

    findings = lint_privacy(template)

    assert [(f.code, f.kind) for f in findings] == [("K-PRI-005", "dynamic-template-name")]


def test_privacy_lint_no_ast_returns_empty() -> None:
    env = Environment()
    template = env.from_string("{{ user.email }}")
    template._optimized_ast = None

    assert lint_privacy(template) == []
