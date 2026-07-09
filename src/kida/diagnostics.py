"""Public, surface-neutral diagnostics for Kida tooling.

The functions in this module expose the same immutable facts used by
``kida check`` without inheriting CLI stream or exit-code policy. Locations use
1-based lines and 0-based columns; end positions are exclusive when present.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from os import PathLike
from pathlib import Path
from typing import Protocol, final

from kida.environment import Environment


class DiagnosticSeverity(StrEnum):
    """Severity assigned by the diagnostic producer."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class DiagnosticConfidence(StrEnum):
    """How conclusively Kida can make a diagnostic claim."""

    PROVEN = "proven"
    CONSERVATIVE = "conservative"
    RUNTIME_ONLY = "runtime-only"
    UNKNOWN = "unknown"


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


@final
@dataclass(frozen=True, slots=True)
class SourcePosition:
    """One source position using a 1-based line and optional 0-based column."""

    line: int
    column: int | None = None

    def __post_init__(self) -> None:
        if self.line < 1:
            raise ValueError("line must be 1-based")
        if self.column is not None and self.column < 0:
            raise ValueError("column must be 0-based")


@final
@dataclass(frozen=True, slots=True)
class SourceSpan:
    """Logical template path and optional half-open source range."""

    path: str | None = None
    start: SourcePosition | None = None
    end: SourcePosition | None = None

    def __post_init__(self) -> None:
        if self.path is not None:
            _require_text(self.path, "path")
        if self.end is not None and self.start is None:
            raise ValueError("end position requires a start position")
        if self.start is None or self.end is None:
            return
        if self.end.line < self.start.line:
            raise ValueError("end position must not precede start position")
        if (
            self.end.line == self.start.line
            and self.start.column is not None
            and self.end.column is not None
            and self.end.column < self.start.column
        ):
            raise ValueError("end position must not precede start position")

    @property
    def is_exact(self) -> bool:
        """Return whether the span is precise enough for a source edit."""
        return (
            self.path is not None
            and self.start is not None
            and self.start.column is not None
            and self.end is not None
            and self.end.column is not None
        )


@final
@dataclass(frozen=True, slots=True)
class RelatedLocation:
    """A labeled source location related to the primary finding."""

    label: str
    span: SourceSpan

    def __post_init__(self) -> None:
        _require_text(self.label, "related location label")


@final
@dataclass(frozen=True, slots=True)
class SafeEdit:
    """An unambiguous replacement over an exact source span."""

    span: SourceSpan
    replacement: str
    description: str | None = None

    def __post_init__(self) -> None:
        if not self.span.is_exact:
            raise ValueError("safe edit requires a path and exact start/end columns")
        if self.description is not None:
            _require_text(self.description, "safe edit description")


@final
@dataclass(frozen=True, slots=True)
class DiagnosticSnippet:
    """Plain source lines surrounding a diagnostic."""

    lines: tuple[tuple[int, str], ...]
    error_line: int
    column: int | None = None

    def __post_init__(self) -> None:
        if self.error_line < 1:
            raise ValueError("snippet error_line must be 1-based")
        if self.column is not None and self.column < 0:
            raise ValueError("snippet column must be 0-based")
        previous = 0
        for line, _content in self.lines:
            if line <= previous:
                raise ValueError("snippet line numbers must be positive and increasing")
            previous = line


@final
@dataclass(frozen=True, slots=True)
class Diagnostic:
    """One immutable Kida finding, independent of its output surface."""

    code: str
    category: str
    severity: DiagnosticSeverity
    message: str
    span: SourceSpan = SourceSpan()
    title: str | None = None
    kind: str | None = None
    suggestion: str | None = None
    safe_edit: SafeEdit | None = None
    related_locations: tuple[RelatedLocation, ...] = ()
    confidence: DiagnosticConfidence = DiagnosticConfidence.UNKNOWN
    notes: tuple[str, ...] = ()
    documentation_url: str | None = None
    source_snippet: DiagnosticSnippet | None = None
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.code, "diagnostic code")
        _require_text(self.category, "diagnostic category")
        _require_text(self.message, "diagnostic message")
        if self.title is not None:
            _require_text(self.title, "diagnostic title")
        if self.kind is not None:
            _require_text(self.kind, "diagnostic kind")
        if self.suggestion is not None:
            _require_text(self.suggestion, "diagnostic suggestion")
        if self.documentation_url is not None:
            _require_text(self.documentation_url, "diagnostic documentation URL")
        for note in self.notes:
            _require_text(note, "diagnostic note")
        seen_metadata: set[str] = set()
        for key, _value in self.metadata:
            _require_text(key, "diagnostic metadata key")
            if key in seen_metadata:
                raise ValueError(f"duplicate diagnostic metadata key: {key}")
            seen_metadata.add(key)


class DiagnosticConverter[SourceT](Protocol):
    """Pure conversion boundary from one producer record to ``Diagnostic``."""

    def __call__(self, source: SourceT, /) -> Diagnostic: ...


@final
@dataclass(frozen=True, slots=True)
class DiagnosticOptions:
    """Opt-in static checks shared by source and directory diagnosis."""

    strict: bool = False
    validate_calls: bool = False
    a11y: bool = False
    typed: bool = False
    lint_fragile_paths: bool = False


_DEFAULT_OPTIONS = DiagnosticOptions()


@final
@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    """Policy-neutral result of one programmatic diagnostic request."""

    diagnostics: tuple[Diagnostic, ...]
    partial: bool = False


def diagnose_directory(
    root: str | PathLike[str],
    *,
    options: DiagnosticOptions = _DEFAULT_OPTIONS,
) -> DiagnosticReport:
    """Diagnose templates below *root* with the same collection as ``kida check``."""
    from kida._check import collect_check_diagnostics

    if not isinstance(root, (str, PathLike)):
        raise TypeError("root must be a string or path-like object")
    result = collect_check_diagnostics(
        Path(root),
        strict=options.strict,
        validate_calls=options.validate_calls,
        a11y=options.a11y,
        typed=options.typed,
        lint_fragile_paths=options.lint_fragile_paths,
    )
    return DiagnosticReport(diagnostics=result.diagnostics, partial=result.partial)


def diagnose_source(
    source: str,
    *,
    name: str = "<string>",
    environment: Environment | None = None,
    options: DiagnosticOptions = _DEFAULT_OPTIONS,
) -> DiagnosticReport:
    """Diagnose an in-memory template without adding it to environment caches.

    A supplied environment contributes lexer/parser configuration, extensions,
    autoescape selection, and loader-backed imported component metadata. Kida
    does not mutate its registries; resolving imports may use that environment's
    existing thread-safe template cache.
    """
    if not isinstance(source, str):
        raise TypeError("source must be a string")
    _require_text(name, "template name")
    if environment is not None and not isinstance(environment, Environment):
        raise TypeError("environment must be a kida.Environment")

    from kida._check import collect_source_diagnostics

    result = collect_source_diagnostics(
        source,
        name=name,
        environment=environment,
        strict=options.strict,
        validate_calls=options.validate_calls,
        a11y=options.a11y,
        typed=options.typed,
        lint_fragile_paths=options.lint_fragile_paths,
    )
    return DiagnosticReport(diagnostics=result.diagnostics, partial=result.partial)


def diagnostic_from_exception(
    error: Exception,
    *,
    path: str | None = None,
) -> Diagnostic:
    """Convert a Kida template or lexer exception into one public diagnostic.

    ``TypeError`` is raised for unrelated Python exceptions so framework
    adapters cannot accidentally relabel arbitrary application failures as Kida
    diagnostics.
    """
    from kida._check import _exception_diagnostic
    from kida.exceptions import TemplateError
    from kida.lexer import LexerError

    if not isinstance(error, (TemplateError, LexerError)):
        raise TypeError(f"unsupported diagnostic exception: {type(error).__name__}")
    return _exception_diagnostic(error, path)


def _source_offset(source: str, position: SourcePosition, *, path: str) -> int:
    line_starts = [0]
    line_starts.extend(index + 1 for index, char in enumerate(source) if char == "\n")
    if position.line > len(line_starts):
        raise ValueError(f"stale safe edit for {path}:{position.line}: line no longer exists")

    start = line_starts[position.line - 1]
    newline = source.find("\n", start)
    end = len(source) if newline == -1 else newline
    if end > start and source[end - 1] == "\r":
        end -= 1
    column = position.column
    if column is None or column > end - start:
        raise ValueError(f"stale safe edit for {path}:{position.line}: column no longer exists")
    return start + column


def _verify_edit_snapshot(
    source: str,
    diagnostic: Diagnostic,
    edit: SafeEdit,
    *,
    path: str,
) -> tuple[int, int, str]:
    snippet = diagnostic.source_snippet
    if snippet is None:
        raise ValueError(f"safe edit for {path} has no source snapshot")
    start = edit.span.start
    end = edit.span.end
    if start is None or end is None:  # SafeEdit validates this; retain a defensive boundary.
        raise ValueError(f"safe edit for {path} has an inexact range")

    current_lines = [line.removesuffix("\r") for line in source.split("\n")]
    expected_lines = dict(snippet.lines)
    for line_number in range(start.line, end.line + 1):
        expected = expected_lines.get(line_number)
        if expected is None:
            raise ValueError(
                f"safe edit for {path}:{line_number} has an incomplete source snapshot"
            )
        if line_number > len(current_lines) or current_lines[line_number - 1] != expected:
            raise ValueError(f"stale safe edit for {path}:{line_number}: source changed")

    start_offset = _source_offset(source, start, path=path)
    end_offset = _source_offset(source, end, path=path)
    return start_offset, end_offset, edit.replacement


def apply_safe_edits(
    source: str,
    diagnostics: Iterable[Diagnostic],
    *,
    path: str,
) -> str:
    """Apply non-overlapping, snapshot-matched safe edits for one template.

    Diagnostics for other paths and diagnostics without a safe edit are
    ignored. A ``ValueError`` is raised before any edit is applied when the
    current source differs from the captured source lines, a snapshot is
    incomplete, or two selected edits overlap.
    """
    if not isinstance(source, str):
        raise TypeError("source must be a string")
    if not isinstance(path, str):
        raise TypeError("path must be a string")
    _require_text(path, "template path")
    if not isinstance(diagnostics, Iterable):
        raise TypeError("diagnostics must be iterable")

    replacements: list[tuple[int, int, str]] = []
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, Diagnostic):
            raise TypeError("diagnostics must contain Diagnostic records")
        edit = diagnostic.safe_edit
        if edit is None or edit.span.path != path:
            continue
        replacements.append(_verify_edit_snapshot(source, diagnostic, edit, path=path))

    replacements.sort(key=lambda item: (item[0], item[1]))
    previous_end = -1
    previous_start = -1
    for start, end, _replacement in replacements:
        if start < previous_end or start == previous_start:
            raise ValueError(f"overlapping safe edits for {path}")
        previous_start = start
        previous_end = end

    result = source
    for start, end, replacement in reversed(replacements):
        result = result[:start] + replacement + result[end:]
    return result


__all__ = [
    "Diagnostic",
    "DiagnosticConfidence",
    "DiagnosticConverter",
    "DiagnosticOptions",
    "DiagnosticReport",
    "DiagnosticSeverity",
    "DiagnosticSnippet",
    "RelatedLocation",
    "SafeEdit",
    "SourcePosition",
    "SourceSpan",
    "apply_safe_edits",
    "diagnose_directory",
    "diagnose_source",
    "diagnostic_from_exception",
]
