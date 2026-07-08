"""Private, surface-neutral diagnostic facts.

This module is deliberately not exported from :mod:`kida`.  It gives internal
collectors one immutable representation without committing the public Python,
CLI, JSON, SARIF, or LSP contracts that may eventually consume it.

Locations use Kida's existing convention: lines are 1-based and columns are
0-based.  End positions are exclusive when present.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, final


class DiagnosticSeverity(StrEnum):
    """Policy-neutral severity carried by an internal diagnostic."""

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
    """Complete internal facts for one Kida finding.

    The record carries facts only.  Ordering, de-duplication, exit policy, and
    surface serialization belong to later layers so this type cannot silently
    set CLI or schema policy.
    """

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
