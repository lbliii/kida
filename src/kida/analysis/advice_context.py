"""Immutable, framework-neutral context facts for opt-in shape advice."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import final

from kida.diagnostics import Diagnostic, SourcePosition, SourceSpan

type AdviceFactValue = str | int | float | bool | None


@final
@dataclass(frozen=True, slots=True)
class AdviceContext:
    """Adapter-supplied scalar facts scoped to one exact profiled span."""

    span: SourceSpan
    facts: tuple[tuple[str, AdviceFactValue], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.span, SourceSpan):
            raise TypeError("advice context span must be a SourceSpan")
        if not self.span.is_exact:
            raise ValueError("advice context requires an exact SourceSpan")
        if not isinstance(self.facts, tuple):
            raise TypeError("advice context facts must be a tuple of pairs")
        normalized: list[tuple[str, AdviceFactValue]] = []
        seen: set[str] = set()
        for fact in self.facts:
            if not isinstance(fact, tuple) or len(fact) != 2:
                raise TypeError("advice context facts must contain (name, scalar) pairs")
            name, value = fact
            if not isinstance(name, str) or not name.strip():
                raise ValueError("advice context fact names must be non-empty strings")
            if name in seen:
                raise ValueError(f"duplicate advice context fact: {name}")
            if value is not None and not isinstance(value, (str, int, float, bool)):
                raise TypeError("advice context fact values must be literal scalars")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("advice context float facts must be finite")
            seen.add(name)
            normalized.append((name, value))
        object.__setattr__(self, "facts", tuple(sorted(normalized)))


def _position_key(position: SourcePosition) -> tuple[int, int]:
    assert position.column is not None
    return position.line, position.column


def _contains(container: SourceSpan, nested: SourceSpan) -> bool:
    if not container.is_exact or not nested.is_exact or container.path != nested.path:
        return False
    assert container.start is not None and container.end is not None
    assert nested.start is not None and nested.end is not None
    return _position_key(container.start) <= _position_key(nested.start) and _position_key(
        nested.end
    ) <= _position_key(container.end)


def _recognized(context: AdviceContext) -> dict[str, AdviceFactValue]:
    facts = dict(context.facts)
    recognized: dict[str, AdviceFactValue] = {}
    consumer_context = facts.get("consumer_context")
    if consumer_context in {"iterated", "repeated"}:
        recognized["consumer_context"] = consumer_context
    for name in ("preserve_boundary", "response_boundary"):
        if facts.get(name) is True:
            recognized[name] = True
    if "role" in facts:
        recognized["role"] = facts["role"]
    visibility = facts.get("visibility")
    if visibility in {"package", "public"}:
        recognized["visibility"] = visibility
    return recognized


def _context_key(context: AdviceContext) -> tuple[object, ...]:
    assert context.span.path is not None
    assert context.span.start is not None and context.span.end is not None
    return (
        context.span.path,
        _position_key(context.span.start),
        _position_key(context.span.end),
        context.facts,
    )


def _span_key(span: SourceSpan) -> tuple[object, ...]:
    assert span.start is not None and span.end is not None
    return span.path, _position_key(span.start), _position_key(span.end)


def _transparent_spans(contexts: tuple[AdviceContext, ...], *, path: str) -> tuple[SourceSpan, ...]:
    spans = {
        context.span
        for context in contexts
        if context.span.path == path
        and _recognized(context).get("consumer_context") in {"iterated", "repeated"}
    }
    return tuple(sorted(spans, key=_span_key))


def _preserves_span(span: SourceSpan, contexts: tuple[AdviceContext, ...]) -> bool:
    for context in contexts:
        if context.span != span:
            continue
        facts = _recognized(context)
        if facts.get("preserve_boundary") is True or facts.get("response_boundary") is True:
            return True
        if facts.get("visibility") in {"package", "public"}:
            return True
    return False


def _enrich_diagnostic(
    diagnostic: Diagnostic,
    contexts: tuple[AdviceContext, ...],
) -> Diagnostic:
    from dataclasses import replace

    matches = [
        context
        for context in contexts
        if _recognized(context) and _contains(context.span, diagnostic.span)
    ]
    if not matches:
        return diagnostic
    matches.sort(key=_context_key)
    payload = [
        {
            "facts": _recognized(context),
            "span": {
                "end": {
                    "column": context.span.end.column,
                    "line": context.span.end.line,
                },
                "path": context.span.path,
                "start": {
                    "column": context.span.start.column,
                    "line": context.span.start.line,
                },
            },
        }
        for context in matches
        if context.span.start is not None and context.span.end is not None
    ]
    metadata = dict(diagnostic.metadata)
    metadata["advice_context"] = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    notes = diagnostic.notes
    if any(
        _recognized(context).get("consumer_context") in {"iterated", "repeated"}
        and (
            _recognized(context).get("preserve_boundary") is True
            or _recognized(context).get("response_boundary") is True
        )
        for context in matches
    ):
        notes = (
            *notes,
            "Adapter context preserves the outer boundary while exposing this nested candidate.",
        )
    return replace(diagnostic, metadata=tuple(sorted(metadata.items())), notes=notes)


__all__ = ["AdviceContext", "AdviceFactValue"]
