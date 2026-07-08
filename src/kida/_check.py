"""Private diagnostic collection for ``kida check``.

The collector preserves the existing human-output phase order while giving
JSON and SARIF renderers one deduplicated set of canonical diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, final

from kida import Environment, FileSystemLoader
from kida._diagnostic_adapters import (
    convert_a11y_issue,
    convert_call_validation,
    convert_fragile_path_issue,
    convert_template_error,
    convert_type_issue,
    convert_type_mismatch,
)
from kida._diagnostics import (
    Diagnostic,
    DiagnosticConfidence,
    DiagnosticSeverity,
    DiagnosticSnippet,
    SourcePosition,
    SourceSpan,
)
from kida.analysis.analyzer import BlockAnalyzer
from kida.exceptions import ErrorCode, TemplateError, TemplateSyntaxError, build_source_snippet
from kida.lexer import Lexer, LexerError
from kida.parser import Parser

if TYPE_CHECKING:
    from pathlib import Path

    from kida.template import Template


_TEMPLATE_GLOBS = ("*.html", "*.kida")
_PHASE_ORDER = {
    "configuration": 0,
    "load": 1,
    "strict": 2,
    "component-call": 3,
    "component-type": 4,
    "type": 5,
    "fragile-path": 6,
    "accessibility": 7,
}


@final
@dataclass(frozen=True, slots=True)
class CheckDiagnosticEvent:
    """One canonical diagnostic plus its compatibility text rendering."""

    diagnostic: Diagnostic
    phase: str
    text: str


@final
@dataclass(frozen=True, slots=True)
class CheckSummaryEvent:
    """One human-only phase or final summary line."""

    phase: str
    text: str


type CheckEvent = CheckDiagnosticEvent | CheckSummaryEvent


@final
@dataclass(frozen=True, slots=True)
class CheckResult:
    """Complete result of one check invocation."""

    root: str
    events: tuple[CheckEvent, ...]
    partial: bool
    exit_code: int

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        """Return diagnostics ordered by phase, path, range, code, and message."""
        diagnostic_events = (
            event for event in self.events if isinstance(event, CheckDiagnosticEvent)
        )
        return tuple(
            event.diagnostic
            for event in sorted(
                diagnostic_events,
                key=lambda event: (
                    _PHASE_ORDER[event.phase],
                    *_diagnostic_key(event.diagnostic),
                ),
            )
        )


class _Collector:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.events: list[CheckEvent] = []
        self.keys: set[tuple[object, ...]] = set()
        self.partial = False

    def add(self, diagnostic: Diagnostic, *, phase: str, text: str) -> bool:
        key = _diagnostic_key(diagnostic)
        if key in self.keys:
            return False
        self.keys.add(key)
        self.events.append(CheckDiagnosticEvent(diagnostic=diagnostic, phase=phase, text=text))
        return True

    def summary(self, *, phase: str, text: str) -> None:
        self.events.append(CheckSummaryEvent(phase=phase, text=text))

    def build(self, *, exit_code: int) -> CheckResult:
        return CheckResult(
            root=str(self.root),
            events=tuple(self.events),
            partial=self.partial,
            exit_code=exit_code,
        )


def _iter_templates(root: Path) -> list[Path]:
    seen: set[Path] = set()
    for glob in _TEMPLATE_GLOBS:
        seen.update(root.rglob(glob))
    return sorted(seen)


def _diagnostic_key(diagnostic: Diagnostic) -> tuple[object, ...]:
    span = diagnostic.span
    return (
        diagnostic.code,
        span.path,
        span.start.line if span.start else -1,
        span.start.column if span.start and span.start.column is not None else -1,
        span.end.line if span.end else -1,
        span.end.column if span.end and span.end.column is not None else -1,
        diagnostic.message,
    )


def _with_path(diagnostic: Diagnostic, path: str) -> Diagnostic:
    return replace(
        diagnostic,
        span=SourceSpan(path=path, start=diagnostic.span.start, end=diagnostic.span.end),
    )


def _snippet(source: str, line: int, column: int | None) -> DiagnosticSnippet:
    snippet = build_source_snippet(source, line, column=column)
    return DiagnosticSnippet(
        lines=snippet.lines,
        error_line=snippet.error_line,
        column=snippet.column,
    )


def _exception_diagnostic(exc: Exception, path: str) -> Diagnostic:
    if isinstance(exc, TemplateError):
        return _with_path(convert_template_error(exc), path)
    if isinstance(exc, LexerError):
        code = ErrorCode.SYNTAX_ERROR
        return Diagnostic(
            code=code.value,
            category=code.category,
            severity=DiagnosticSeverity.ERROR,
            message=exc.message,
            span=SourceSpan(path=path, start=SourcePosition(exc.lineno, exc.col_offset)),
            title="Lexer error",
            kind="syntax",
            suggestion=exc.suggestion,
            confidence=DiagnosticConfidence.PROVEN,
            documentation_url=code.docs_url,
            source_snippet=_snippet(exc.source, exc.lineno, exc.col_offset),
        )
    code = ErrorCode.RUNTIME_ERROR
    return Diagnostic(
        code=code.value,
        category=code.category,
        severity=DiagnosticSeverity.ERROR,
        message=str(exc),
        span=SourceSpan(path=path),
        title=type(exc).__name__,
        kind="check-failure",
        confidence=DiagnosticConfidence.RUNTIME_ONLY,
        documentation_url=code.docs_url,
    )


def _invalid_root_result(root: Path) -> CheckResult:
    collector = _Collector(root)
    code = ErrorCode.TEMPLATE_NOT_FOUND
    message = f"not a directory: {root}"
    collector.add(
        Diagnostic(
            code=code.value,
            category=code.category,
            severity=DiagnosticSeverity.ERROR,
            message=message,
            span=SourceSpan(path=str(root)),
            title="Invalid template directory",
            kind="configuration",
            suggestion="Pass a directory containing Kida templates.",
            confidence=DiagnosticConfidence.PROVEN,
            documentation_url=code.docs_url,
        ),
        phase="configuration",
        text=f"kida check: {message}",
    )
    collector.partial = True
    return collector.build(exit_code=2)


def _explicit_close_suggestion(block_type: str) -> str:
    if block_type == "block":
        return "{% endblock %}"
    return f"{{% end{block_type} %}}"


def collect_check_diagnostics(
    template_dir: Path,
    *,
    strict: bool,
    validate_calls: bool,
    a11y: bool,
    typed: bool,
    lint_fragile_paths: bool,
) -> CheckResult:
    """Collect all enabled ``kida check`` findings without rendering a surface."""
    root = template_dir.resolve()
    if not root.is_dir():
        return _invalid_root_result(root)

    collector = _Collector(root)
    env = Environment(loader=FileSystemLoader(str(root)), validate_calls=False)
    failed_loads: set[str] = set()
    templates: dict[str, Template] = {}
    strict_warnings = 0
    call_issues = 0

    for path in _iter_templates(root):
        rel = path.relative_to(root).as_posix()
        try:
            tpl = env.get_template(rel)
            templates[rel] = tpl
        except Exception as exc:
            collector.add(
                _exception_diagnostic(exc, rel),
                phase="load",
                text=f"{rel}: {exc}",
            )
            collector.partial = True
            failed_loads.add(rel)
            continue

        if strict:
            try:
                source = path.read_text(encoding="utf-8")
                lexer = Lexer(source, env._lexer_config)
                tokens = list(lexer.tokenize())
                sparser = Parser(
                    tokens,
                    name=rel,
                    filename=str(path),
                    source=source,
                    autoescape=env.select_autoescape(rel),
                )
                sparser.parse()
            except (OSError, TemplateSyntaxError, LexerError) as exc:
                collector.add(
                    _exception_diagnostic(exc, rel),
                    phase="strict",
                    text=f"{rel}: {exc}",
                )
                collector.partial = True
                continue
            for lineno, col, closing in sparser._unified_end_closures:
                want = _explicit_close_suggestion(closing)
                code = ErrorCode.UNSUPPORTED_SYNTAX
                diagnostic = Diagnostic(
                    code=code.value,
                    category=code.category,
                    severity=DiagnosticSeverity.WARNING,
                    message=f"unified {{% end %}} closes '{closing}'",
                    span=SourceSpan(path=rel, start=SourcePosition(lineno, col)),
                    title="Strict closing tag",
                    kind="strict-closing-tag",
                    suggestion=f"Prefer {want}.",
                    confidence=DiagnosticConfidence.PROVEN,
                    documentation_url=code.docs_url,
                )
                if collector.add(
                    diagnostic,
                    phase="strict",
                    text=(
                        f"{rel}:{lineno}: strict: unified {{% end %}} closes "
                        f"'{closing}' — prefer {want}"
                    ),
                ):
                    strict_warnings += 1

        if validate_calls and tpl._optimized_ast is not None:
            imported_defs = env._collect_imported_def_metadata(tpl._optimized_ast, rel)
            issues = BlockAnalyzer().validate_calls_with_external_defs(
                tpl._optimized_ast,
                imported_defs,
            )
            converted = [convert_call_validation(issue, template_name=rel) for issue in issues]
            for diagnostic in sorted(converted, key=_diagnostic_key):
                line = diagnostic.span.start.line if diagnostic.span.start else 0
                if collector.add(
                    diagnostic,
                    phase="component-call",
                    text=f"{rel}:{line}: {diagnostic.code}: {diagnostic.message}",
                ):
                    call_issues += 1

    if strict and strict_warnings:
        collector.summary(
            phase="strict",
            text=f"kida check: strict: {strict_warnings} unified {{% end %}} tag(s)",
        )
    if validate_calls and call_issues:
        collector.summary(
            phase="component-call",
            text=f"kida check: {call_issues} call-site issue(s)",
        )

    type_mismatches = 0
    if validate_calls:
        for path in sorted(root.rglob("*.html")):
            rel = path.relative_to(root).as_posix()
            if rel in failed_loads:
                continue
            tpl = templates[rel]
            if tpl._optimized_ast is None:
                continue
            imported_defs = env._collect_imported_def_metadata(tpl._optimized_ast, rel)
            mismatches = BlockAnalyzer().validate_call_types_with_external_defs(
                tpl._optimized_ast,
                imported_defs,
            )
            converted = [convert_type_mismatch(item, template_name=rel) for item in mismatches]
            for diagnostic in sorted(converted, key=_diagnostic_key):
                line = diagnostic.span.start.line if diagnostic.span.start else 0
                if collector.add(
                    diagnostic,
                    phase="component-type",
                    text=f"{rel}:{line}: {diagnostic.code}: type: {diagnostic.message}",
                ):
                    type_mismatches += 1
        if type_mismatches:
            collector.summary(
                phase="component-type",
                text=f"kida check: {type_mismatches} type mismatch(es) in call sites",
            )

    type_issues = 0
    if typed:
        from kida.analysis.type_checker import check_types

        for rel, tpl in templates.items():
            if rel in failed_loads or tpl._optimized_ast is None:
                continue
            converted = [
                convert_type_issue(issue, template_name=rel)
                for issue in check_types(tpl._optimized_ast)
            ]
            for diagnostic in sorted(converted, key=_diagnostic_key):
                line = diagnostic.span.start.line if diagnostic.span.start else 0
                if collector.add(
                    diagnostic,
                    phase="type",
                    text=(
                        f"{rel}:{line}: type/{diagnostic.kind} "
                        f"[{diagnostic.severity.value.upper()}]: {diagnostic.message}"
                    ),
                ):
                    type_issues += 1
        if type_issues:
            collector.summary(phase="type", text=f"kida check: {type_issues} type issue(s)")

    fragile_path_issues = 0
    if lint_fragile_paths:
        from kida.analysis.fragile_paths import check_fragile_paths

        for rel, tpl in templates.items():
            if rel in failed_loads or tpl._optimized_ast is None:
                continue
            issues = check_fragile_paths(tpl._optimized_ast, rel)
            pairs = [
                (issue, convert_fragile_path_issue(issue, template_name=rel)) for issue in issues
            ]
            for issue, diagnostic in sorted(pairs, key=lambda item: _diagnostic_key(item[1])):
                line = diagnostic.span.start.line if diagnostic.span.start else 0
                if collector.add(
                    diagnostic,
                    phase="fragile-path",
                    text=(
                        f"{rel}:{line}: lint/fragile-path [WARNING]: "
                        f'{{% {issue.statement} "{issue.target}" %}} '
                        f"is in the same folder as the caller — "
                        f'prefer "{issue.suggestion}" so folder moves stay zero-edit'
                    ),
                ):
                    fragile_path_issues += 1
        if fragile_path_issues:
            collector.summary(
                phase="fragile-path",
                text=f"kida check: {fragile_path_issues} fragile-path suggestion(s)",
            )

    a11y_issues = 0
    if a11y:
        from kida.analysis.a11y import check_a11y

        for rel, tpl in templates.items():
            if rel in failed_loads or tpl._optimized_ast is None:
                continue
            converted = [
                convert_a11y_issue(issue, template_name=rel)
                for issue in check_a11y(tpl._optimized_ast)
            ]
            for diagnostic in sorted(converted, key=_diagnostic_key):
                line = diagnostic.span.start.line if diagnostic.span.start else 0
                if collector.add(
                    diagnostic,
                    phase="accessibility",
                    text=(
                        f"{rel}:{line}: a11y/{diagnostic.kind} "
                        f"[{diagnostic.severity.value.upper()}]: {diagnostic.message}"
                    ),
                ):
                    a11y_issues += 1
        if a11y_issues:
            collector.summary(
                phase="accessibility",
                text=f"kida check: {a11y_issues} accessibility issue(s)",
            )

    total = len(collector.keys)
    if total:
        collector.summary(phase="final", text=f"kida check: {total} problem(s)")
    return collector.build(exit_code=1 if total else 0)
