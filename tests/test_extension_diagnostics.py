"""Public and isolation contracts for extension-provided diagnostics."""

from __future__ import annotations

import inspect
import operator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, fields, replace

import pytest

import kida
import kida.extensions as extensions
from kida import DictLoader, Environment
from kida.diagnostics import (
    Diagnostic,
    DiagnosticConfidence,
    DiagnosticOptions,
    DiagnosticSeverity,
    DiagnosticSnippet,
    SafeEdit,
    SourcePosition,
    SourceSpan,
    apply_safe_edits,
    diagnose_source,
)
from kida.extensions import Extension, ExtensionDiagnosticContext


def _finding(
    *,
    code: str = "K-ACME-001",
    category: str = "extension",
    confidence: DiagnosticConfidence = DiagnosticConfidence.PROVEN,
    path: str | None = None,
    message: str = "Extension finding",
    safe_edit: SafeEdit | None = None,
    source_snippet: DiagnosticSnippet | None = None,
) -> Diagnostic:
    return Diagnostic(
        code=code,
        category=category,
        severity=DiagnosticSeverity.WARNING,
        message=message,
        span=SourceSpan(path=path, start=SourcePosition(1, 0)),
        title="Extension finding",
        kind="extension-rule",
        suggestion="Update the extension-owned pattern.",
        safe_edit=safe_edit,
        confidence=confidence,
        source_snippet=source_snippet,
    )


def test_extension_diagnostic_public_contract_and_legacy_default() -> None:
    env = Environment(extensions=[Extension])
    template = env.from_string("hello", name="page.html")
    ast = template._optimized_ast
    assert ast is not None
    context = ExtensionDiagnosticContext("page.html", "hello", ast, {})

    assert extensions.__all__ == ["Extension", "ExtensionDiagnosticContext"]
    assert "ExtensionDiagnosticContext" not in kida.__all__
    assert [field.name for field in fields(ExtensionDiagnosticContext)] == [
        "template_name",
        "source",
        "ast",
        "definitions",
    ]
    assert str(inspect.signature(Extension.diagnose)) == (
        "(self, context: 'ExtensionDiagnosticContext') -> 'Iterable[Diagnostic]'"
    )
    assert env._extension_instances[0].diagnose(context) == ()
    with pytest.raises(TypeError):
        operator.setitem(context.definitions, "card", object())
    with pytest.raises(FrozenInstanceError):
        context.__setattr__("source", "changed")


@pytest.mark.parametrize(
    ("namespace", "match"),
    [
        ("acme", "2-12 uppercase ASCII"),
        ("A", "2-12 uppercase ASCII"),
        ("ACME_TOO_LONG", "2-12 uppercase ASCII"),
        (123, "2-12 uppercase ASCII"),
        ("RUN", "reserved by Kida"),
    ],
)
def test_extension_diagnostic_namespace_validation(namespace: object, match: str) -> None:
    class InvalidNamespace(Extension):
        diagnostic_namespace = namespace

    with pytest.raises(ValueError, match=match):
        Environment(extensions=[InvalidNamespace])


def test_extension_diagnostic_namespaces_must_be_unique() -> None:
    class First(Extension):
        diagnostic_namespace = "ACME"

    class Second(Extension):
        diagnostic_namespace = "ACME"

    with pytest.raises(ValueError, match="already owned by First"):
        Environment(extensions=[First, Second])


def test_extension_receives_visible_component_metadata_and_normalized_location() -> None:
    seen: list[ExtensionDiagnosticContext] = []

    class SignatureExtension(Extension):
        diagnostic_namespace = "ACME"

        def diagnose(self, context: ExtensionDiagnosticContext):
            seen.append(context)
            assert context.definitions["card"].params[0].name == "title"
            assert context.definitions["local"].params[0].annotation == "int"
            return (_finding(), _finding())

    env = Environment(
        loader=DictLoader({"components.html": "{% def card(title: str) %}{{ title }}{% end %}"}),
        extensions=[SignatureExtension],
    )
    source = (
        '{% from "components.html" import card %}\n{% def local(count: int) %}{{ count }}{% end %}'
    )

    report = diagnose_source(source, name="page.html", environment=env)

    assert report.partial is False
    assert len(report.diagnostics) == 1
    diagnostic = report.diagnostics[0]
    assert diagnostic.code == "K-ACME-001"
    assert diagnostic.span.path == "page.html"
    assert diagnostic.source_snippet is not None
    assert diagnostic.source_snippet.lines[0][1] == '{% from "components.html" import card %}'
    assert seen[0].template_name == "page.html"
    assert seen[0].source == source


def test_extension_findings_follow_builtin_phases_and_safe_edits_are_verified() -> None:
    class SafeEditExtension(Extension):
        diagnostic_namespace = "ACME"

        def diagnose(self, context: ExtensionDiagnosticContext):
            start = context.source.index("bad")
            edit_span = SourceSpan(
                path=context.template_name,
                start=SourcePosition(1, start),
                end=SourcePosition(1, start + 3),
            )
            return (
                replace(
                    _finding(message="Replace bad"),
                    span=edit_span,
                    safe_edit=SafeEdit(span=edit_span, replacement="good"),
                ),
            )

    source = "{% template good: str %}{{ bad }}"
    env = Environment(extensions=[SafeEditExtension])
    report = diagnose_source(
        source,
        name="page.html",
        environment=env,
        options=DiagnosticOptions(typed=True),
    )

    assert report.diagnostics[0].code.startswith("K-TYP-")
    assert report.diagnostics[-1].code == "K-ACME-001"
    extension_finding = report.diagnostics[-1]
    assert extension_finding.source_snippet is not None
    assert apply_safe_edits(source, (extension_finding,), path="page.html") == (
        "{% template good: str %}{{ good }}"
    )


@pytest.mark.parametrize(
    "finding",
    [
        _finding(code="K-OTHER-001"),
        _finding(category="runtime"),
        _finding(confidence=DiagnosticConfidence.UNKNOWN),
        _finding(path="other.html"),
        replace(
            _finding(),
            span=SourceSpan(
                path="page.html",
                start=SourcePosition(1, 0),
                end=SourcePosition(1, 1),
            ),
            safe_edit=SafeEdit(
                span=SourceSpan(
                    path="page.html",
                    start=SourcePosition(1, 0),
                    end=SourcePosition(1, 1),
                ),
                replacement="x",
            ),
            source_snippet=DiagnosticSnippet(
                lines=((1, "stale"),),
                error_line=1,
                column=0,
            ),
        ),
    ],
)
def test_invalid_extension_findings_become_partial_core_failures(finding: Diagnostic) -> None:
    class InvalidFindingExtension(Extension):
        diagnostic_namespace = "ACME"

        def diagnose(self, context: ExtensionDiagnosticContext):
            return (finding,)

    report = diagnose_source(
        "source",
        name="page.html",
        environment=Environment(extensions=[InvalidFindingExtension]),
    )

    assert report.partial is True
    assert [item.code for item in report.diagnostics] == ["K-RUN-007"]
    assert report.diagnostics[0].kind == "extension-diagnostic-failure"
    assert "InvalidFindingExtension.diagnose() failed" in report.diagnostics[0].message


def test_failing_extension_does_not_block_peer_findings() -> None:
    class BrokenExtension(Extension):
        diagnostic_namespace = "BROKEN"

        def diagnose(self, context: ExtensionDiagnosticContext):
            raise RuntimeError("broken hook")

    class PeerExtension(Extension):
        diagnostic_namespace = "PEER"

        def diagnose(self, context: ExtensionDiagnosticContext):
            return (_finding(code="K-PEER-001", message="Peer finding"),)

    report = diagnose_source(
        "source",
        name="page.html",
        environment=Environment(extensions=[BrokenExtension, PeerExtension]),
    )

    assert report.partial is True
    assert [item.code for item in report.diagnostics] == ["K-PEER-001", "K-RUN-007"]
    assert report.diagnostics[0].message == "Peer finding"
    assert "broken hook" in report.diagnostics[1].message


def test_extension_diagnosis_is_invocation_local_under_concurrency() -> None:
    class ConcurrentExtension(Extension):
        diagnostic_namespace = "THREAD"

        def diagnose(self, context: ExtensionDiagnosticContext):
            return (
                _finding(
                    code="K-THREAD-001",
                    message=context.template_name,
                ),
            )

    env = Environment(extensions=[ConcurrentExtension])

    def run(index: int) -> tuple[str | None, str]:
        name = f"page-{index}.html"
        diagnostic = diagnose_source("source", name=name, environment=env).diagnostics[0]
        return diagnostic.span.path, diagnostic.message

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(run, range(32)))

    assert results == [(f"page-{index}.html", f"page-{index}.html") for index in range(32)]
