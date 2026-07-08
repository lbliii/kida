"""Private diagnostic collection for ``kida check``.

The collector preserves the existing human-output phase order while giving
JSON and SARIF renderers one deduplicated set of canonical diagnostics.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
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
from kida.analysis.analyzer import BlockAnalyzer
from kida.diagnostics import (
    Diagnostic,
    DiagnosticConfidence,
    DiagnosticSeverity,
    DiagnosticSnippet,
    SafeEdit,
    SourcePosition,
    SourceSpan,
    apply_safe_edits,
)
from kida.exceptions import ErrorCode, TemplateError, TemplateSyntaxError, build_source_snippet
from kida.lexer import Lexer, LexerError
from kida.parser import Parser

if TYPE_CHECKING:
    from pathlib import Path

    from kida.nodes import Template as TemplateNode
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
    "extension": 8,
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


def _exception_diagnostic(exc: Exception, path: str | None) -> Diagnostic:
    if isinstance(exc, TemplateError):
        diagnostic = convert_template_error(exc)
        return _with_path(diagnostic, path) if path is not None else diagnostic
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


def _extension_failure_diagnostic(extension: object, path: str, exc: Exception) -> Diagnostic:
    code = ErrorCode.RUNTIME_ERROR
    extension_name = type(extension).__name__
    return Diagnostic(
        code=code.value,
        category=code.category,
        severity=DiagnosticSeverity.ERROR,
        message=(f"Extension {extension_name}.diagnose() failed: {type(exc).__name__}: {exc}"),
        span=SourceSpan(path=path),
        title="Extension diagnostic failure",
        kind="extension-diagnostic-failure",
        suggestion="Fix or disable the extension's diagnostic hook.",
        confidence=DiagnosticConfidence.RUNTIME_ONLY,
        documentation_url=code.docs_url,
    )


def _safe_edit_snapshot(source: str, edit: SafeEdit) -> DiagnosticSnippet:
    start = edit.span.start
    end = edit.span.end
    if start is None or end is None:  # SafeEdit already enforces exact positions.
        raise ValueError("safe edit range must be exact")
    lines = [line.removesuffix("\r") for line in source.split("\n")]
    if end.line > len(lines):
        raise ValueError(f"safe edit line {end.line} is outside the current source")
    return DiagnosticSnippet(
        lines=tuple(
            (line_number, lines[line_number - 1]) for line_number in range(start.line, end.line + 1)
        ),
        error_line=start.line,
        column=start.column,
    )


def _normalize_extension_diagnostic(
    diagnostic: Diagnostic,
    *,
    extension: object,
    source: str,
    path: str,
) -> Diagnostic:
    namespace = getattr(extension, "diagnostic_namespace", None)
    extension_name = type(extension).__name__
    if namespace is None:
        raise ValueError(
            f"{extension_name} must declare diagnostic_namespace before returning findings"
        )
    if re.fullmatch(rf"K-{re.escape(namespace)}-[0-9]{{3}}", diagnostic.code) is None:
        raise ValueError(
            f"{extension_name} diagnostic code {diagnostic.code!r} is outside namespace "
            f"K-{namespace}-NNN"
        )
    if diagnostic.category != "extension":
        raise ValueError(
            f"{extension_name} diagnostic {diagnostic.code} must use category='extension'"
        )
    if diagnostic.confidence is DiagnosticConfidence.UNKNOWN:
        raise ValueError(f"{extension_name} diagnostic {diagnostic.code} must declare confidence")
    if diagnostic.span.path not in (None, path):
        raise ValueError(
            f"{extension_name} diagnostic {diagnostic.code} must target current template {path!r}"
        )

    normalized = diagnostic
    if diagnostic.span.path is None:
        normalized = replace(
            normalized,
            span=SourceSpan(
                path=path,
                start=diagnostic.span.start,
                end=diagnostic.span.end,
            ),
        )

    edit = normalized.safe_edit
    if edit is not None:
        if edit.span.path != path:
            raise ValueError(
                f"{extension_name} diagnostic {diagnostic.code} safe edit must target {path!r}"
            )
        if normalized.source_snippet is None:
            normalized = replace(normalized, source_snippet=_safe_edit_snapshot(source, edit))
        apply_safe_edits(source, (normalized,), path=path)
    elif normalized.source_snippet is None and normalized.span.start is not None:
        normalized = replace(
            normalized,
            source_snippet=_snippet(
                source,
                normalized.span.start.line,
                normalized.span.start.column,
            ),
        )
    return normalized


def _collect_extension_diagnostics(
    collector: _Collector,
    *,
    env: Environment,
    ast: TemplateNode,
    source: str,
    name: str,
) -> None:
    if not env._extension_instances:
        return

    from kida.extensions import ExtensionDiagnosticContext
    from kida.template.introspection import _collect_def_metadata

    imported_defs = env._collect_imported_def_metadata(ast, name)
    definitions = {**imported_defs, **_collect_def_metadata(ast, name)}
    context = ExtensionDiagnosticContext(
        template_name=name,
        source=source,
        ast=ast,
        definitions=definitions,
    )
    for extension in env._extension_instances:
        try:
            findings = extension.diagnose(context)
            if not isinstance(findings, Iterable):
                raise TypeError("diagnose() must return an iterable of Diagnostic records")
            normalized: list[Diagnostic] = []
            for finding in findings:
                if not isinstance(finding, Diagnostic):
                    raise TypeError("diagnose() must return only Diagnostic records")
                normalized.append(
                    _normalize_extension_diagnostic(
                        finding,
                        extension=extension,
                        source=source,
                        path=name,
                    )
                )
        except Exception as exc:
            collector.add(
                _extension_failure_diagnostic(extension, name, exc),
                phase="extension",
                text="",
            )
            collector.partial = True
            continue
        for diagnostic in sorted(normalized, key=_diagnostic_key):
            collector.add(diagnostic, phase="extension", text="")


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


def _strict_closing_diagnostic(
    source: str,
    *,
    path: str,
    lineno: int,
    column: int,
    closing: str,
) -> Diagnostic:
    code = ErrorCode.UNSUPPORTED_SYNTAX
    replacement = f"end{closing}"
    return Diagnostic(
        code=code.value,
        category=code.category,
        severity=DiagnosticSeverity.WARNING,
        message=f"unified {{% end %}} closes '{closing}'",
        span=SourceSpan(path=path, start=SourcePosition(lineno, column)),
        title="Strict closing tag",
        kind="strict-closing-tag",
        suggestion=f"Prefer {_explicit_close_suggestion(closing)}.",
        safe_edit=SafeEdit(
            span=SourceSpan(
                path=path,
                start=SourcePosition(lineno, column),
                end=SourcePosition(lineno, column + len("end")),
            ),
            replacement=replacement,
            description=f"Replace the unified closer with '{replacement}'.",
        ),
        confidence=DiagnosticConfidence.PROVEN,
        documentation_url=code.docs_url,
        source_snippet=_snippet(source, lineno, column),
    )


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
                diagnostic = _strict_closing_diagnostic(
                    source,
                    path=rel,
                    lineno=lineno,
                    column=col,
                    closing=closing,
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


def collect_source_diagnostics(
    source: str,
    *,
    name: str,
    environment: Environment | None,
    strict: bool,
    validate_calls: bool,
    a11y: bool,
    typed: bool,
    lint_fragile_paths: bool,
) -> CheckResult:
    """Collect canonical diagnostics for one unsaved source buffer.

    The source is parsed directly rather than compiled through
    :meth:`Environment.from_string`, so it never enters template or bytecode
    caches. A caller-supplied environment is consulted only for parser settings,
    extensions, autoescape selection, and imported definition metadata.
    """
    from pathlib import Path

    env = environment or Environment(validate_calls=False, bytecode_cache=False)
    collector = _Collector(Path(name))
    try:
        lexer = Lexer(source, env._lexer_config)
        tokens = list(lexer.tokenize())
        parser = Parser(
            tokens,
            name=name,
            filename=None,
            source=source,
            autoescape=env.select_autoescape(name),
            extension_tags=env._extension_tags or None,
        )
        ast = parser.parse()
    except (TemplateError, LexerError) as exc:
        collector.add(
            _exception_diagnostic(exc, name),
            phase="load",
            text=f"{name}: {exc}",
        )
        collector.partial = True
        return collector.build(exit_code=1)

    if strict:
        for lineno, col, closing in parser._unified_end_closures:
            collector.add(
                _strict_closing_diagnostic(
                    source,
                    path=name,
                    lineno=lineno,
                    column=col,
                    closing=closing,
                ),
                phase="strict",
                text="",
            )

    analyzer = BlockAnalyzer()
    if validate_calls:
        imported_defs = env._collect_imported_def_metadata(ast, name)
        converted_calls = [
            convert_call_validation(issue, template_name=name)
            for issue in analyzer.validate_calls_with_external_defs(ast, imported_defs)
        ]
        for diagnostic in sorted(converted_calls, key=_diagnostic_key):
            collector.add(diagnostic, phase="component-call", text="")

        converted_types = [
            convert_type_mismatch(item, template_name=name)
            for item in analyzer.validate_call_types_with_external_defs(ast, imported_defs)
        ]
        for diagnostic in sorted(converted_types, key=_diagnostic_key):
            collector.add(diagnostic, phase="component-type", text="")

    if typed:
        from kida.analysis.type_checker import check_types

        converted = [convert_type_issue(issue, template_name=name) for issue in check_types(ast)]
        for diagnostic in sorted(converted, key=_diagnostic_key):
            collector.add(diagnostic, phase="type", text="")

    if lint_fragile_paths:
        from kida.analysis.fragile_paths import check_fragile_paths

        converted = [
            convert_fragile_path_issue(issue, template_name=name)
            for issue in check_fragile_paths(ast, name)
        ]
        for diagnostic in sorted(converted, key=_diagnostic_key):
            collector.add(diagnostic, phase="fragile-path", text="")

    if a11y:
        from kida.analysis.a11y import check_a11y

        converted = [convert_a11y_issue(issue, template_name=name) for issue in check_a11y(ast)]
        for diagnostic in sorted(converted, key=_diagnostic_key):
            collector.add(diagnostic, phase="accessibility", text="")

    _collect_extension_diagnostics(
        collector,
        env=env,
        ast=ast,
        source=source,
        name=name,
    )

    return collector.build(exit_code=1 if collector.keys else 0)
