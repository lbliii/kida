"""Source-compilation versus bytecode-cache differential corpus.

Every fixture declares the render surfaces that apply to it. The oracle compares
semantic output or structured failures, compiler warnings, source locations,
preserved introspection data, and cache fallback behavior.
"""

from __future__ import annotations

import pickle
import warnings
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import pytest

from kida import DictLoader, Environment, ErrorCode, Template
from kida.bytecode_cache import BytecodeCache, hash_source
from kida.environment.core import _hash_static_context
from kida.exceptions import TemplateError


class RenderMode(Enum):
    """Public render entrypoints classified by the differential matrix."""

    FULL = "full"
    STREAM = "stream"
    STREAM_ASYNC = "stream_async"
    ASYNC = "async"
    BLOCK = "block"
    BLOCK_STREAM_ASYNC = "block_stream_async"
    COMPOSITION = "composition"


ALL_MODES = frozenset(RenderMode)
BLOCK_MODES = frozenset({RenderMode.BLOCK, RenderMode.BLOCK_STREAM_ASYNC})
FULL_MODES = frozenset(
    {
        RenderMode.FULL,
        RenderMode.STREAM,
        RenderMode.STREAM_ASYNC,
        RenderMode.ASYNC,
    }
)
NO_UNSUPPORTED_MODES: tuple[tuple[RenderMode, str], ...] = ()
NO_BLOCK_MODES = (
    (RenderMode.BLOCK, "fixture intentionally declares no named block"),
    (RenderMode.BLOCK_STREAM_ASYNC, "fixture intentionally declares no named block"),
)


@dataclass(frozen=True)
class DifferentialCase:
    """One bounded cache differential and its explicit surface contract."""

    name: str
    files: dict[str, str]
    target: str
    context: dict[str, Any]
    expected_full: str | None
    expected_block: str | None
    expected_composition: str | None
    block_name: str | None
    block_overrides: dict[str, str]
    unsupported_modes: tuple[tuple[RenderMode, str], ...]
    static_context: dict[str, Any] | None = None
    preserve_ast: bool = True
    expected_warning_codes: tuple[ErrorCode, ...] = ()
    error_modes: frozenset[RenderMode] = frozenset()
    record_state: str = "clean"
    compare_introspection: bool = False

    @property
    def applicable_modes(self) -> frozenset[RenderMode]:
        return ALL_MODES - {mode for mode, _reason in self.unsupported_modes}


CASES = [
    DifferentialCase(
        name="inheritance",
        files={
            "base.html": "<main>{% block content %}base{% endblock %}</main>",
            "page.html": (
                '{% extends "base.html" %}{% block content %}Hello {{ name }}{% endblock %}'
            ),
        },
        target="page.html",
        context={"name": "Ada"},
        expected_full="<main>Hello Ada</main>",
        expected_block="Hello Ada",
        expected_composition="<main><strong>override</strong></main>",
        block_name="content",
        block_overrides={"content": "<strong>override</strong>"},
        unsupported_modes=NO_UNSUPPORTED_MODES,
    ),
    DifferentialCase(
        name="imports",
        files={
            "components.html": "{% def badge(label) %}<b>{{ label }}</b>{% end %}",
            "page.html": (
                '{% from "components.html" import badge %}'
                "{% block content %}{{ badge(label) }}{% endblock %}"
            ),
        },
        target="page.html",
        context={"label": "new"},
        expected_full="<b>new</b>",
        expected_block="<b>new</b>",
        expected_composition="<i>override</i>",
        block_name="content",
        block_overrides={"content": "<i>override</i>"},
        unsupported_modes=NO_UNSUPPORTED_MODES,
    ),
    DifferentialCase(
        name="static-context",
        files={"page.html": "{% block content %}{{ site.title }}{% endblock %}"},
        target="page.html",
        context={},
        static_context={"site": {"title": "Kida"}},
        expected_full="Kida",
        expected_block="Kida",
        expected_composition="static override",
        block_name="content",
        block_overrides={"content": "static override"},
        unsupported_modes=NO_UNSUPPORTED_MODES,
    ),
    DifferentialCase(
        name="preserved-ast",
        files={
            "page.html": (
                '{% let brand = "Kida" %}{% block content %}{{ brand }}:{{ count }}{% endblock %}'
            )
        },
        target="page.html",
        context={"count": 3},
        expected_full="Kida:3",
        expected_block="Kida:3",
        expected_composition="AST override",
        block_name="content",
        block_overrides={"content": "AST override"},
        unsupported_modes=NO_UNSUPPORTED_MODES,
        compare_introspection=True,
    ),
    DifferentialCase(
        name="compiler-warnings",
        files={
            "page.html": (
                "{% let value = 1 %}"
                "{% if true %}{% set value = 2 %}{% end %}"
                "{% block content %}{{ item ?? fallback | upper }}{% endblock %}"
            )
        },
        target="page.html",
        context={"item": None, "fallback": "ok"},
        expected_full="OK",
        expected_block="OK",
        expected_composition="warning override",
        block_name="content",
        block_overrides={"content": "warning override"},
        unsupported_modes=NO_UNSUPPORTED_MODES,
        expected_warning_codes=(
            ErrorCode.JINJA2_SET_SCOPING,
            ErrorCode.FILTER_PRECEDENCE,
        ),
    ),
    DifferentialCase(
        name="runtime-diagnostic",
        files={"page.html": "{{ 1 / zero }}"},
        target="page.html",
        context={"zero": 0},
        expected_full=None,
        expected_block=None,
        expected_composition=None,
        block_name=None,
        block_overrides={},
        unsupported_modes=NO_BLOCK_MODES,
        error_modes=FULL_MODES | {RenderMode.COMPOSITION},
    ),
    DifferentialCase(
        name="corrupt-record-fallback",
        files={"page.html": "{% block content %}recovered{% endblock %}"},
        target="page.html",
        context={},
        expected_full="recovered",
        expected_block="recovered",
        expected_composition="corrupt override",
        block_name="content",
        block_overrides={"content": "corrupt override"},
        unsupported_modes=NO_UNSUPPORTED_MODES,
        record_state="corrupt",
    ),
    DifferentialCase(
        name="incompatible-record-fallback",
        files={"page.html": "{% block content %}compatible{% endblock %}"},
        target="page.html",
        context={},
        expected_full="compatible",
        expected_block="compatible",
        expected_composition="incompatible override",
        block_name="content",
        block_overrides={"content": "incompatible override"},
        unsupported_modes=NO_UNSUPPORTED_MODES,
        preserve_ast=False,
        record_state="incompatible",
    ),
]


@dataclass(frozen=True)
class ErrorFacts:
    """Stable structured fields exposed by a render failure."""

    type_name: str
    message: str
    compact: str | None
    code: str | None
    template_name: str | None
    template: str | None
    lineno: int | None
    expression: str | None
    suggestion: str | None
    source_snippet: tuple[tuple[str, ...], int, int | None] | None
    template_stack: tuple[Any, ...]
    component_stack: tuple[Any, ...]
    cause: tuple[str, str] | None


@dataclass(frozen=True)
class RenderOutcome:
    output: str | None
    error: ErrorFacts | None


def _error_facts(exc: Exception) -> ErrorFacts:
    code = getattr(exc, "code", None)
    snippet = getattr(exc, "source_snippet", None)
    snippet_facts = None
    if snippet is not None:
        snippet_facts = (tuple(snippet.lines), snippet.error_line, snippet.column)
    cause = exc.__cause__
    compact = exc.format_compact() if isinstance(exc, TemplateError) else None
    return ErrorFacts(
        type_name=type(exc).__name__,
        message=str(exc),
        compact=compact,
        code=getattr(code, "value", None),
        template_name=getattr(exc, "template_name", None),
        template=getattr(exc, "template", None),
        lineno=getattr(exc, "lineno", None),
        expression=getattr(exc, "expression", None),
        suggestion=getattr(exc, "suggestion", None),
        source_snippet=snippet_facts,
        template_stack=tuple(getattr(exc, "template_stack", ())),
        component_stack=tuple(getattr(exc, "component_stack", ())),
        cause=(type(cause).__name__, str(cause)) if cause is not None else None,
    )


def _warning_facts(template: Template) -> tuple[tuple[Any, ...], ...]:
    return tuple(
        (
            warning.code,
            warning.message,
            warning.template_name,
            warning.lineno,
            warning.suggestion,
        )
        for warning in template.warnings
    )


def _emitted_warning_facts(
    emitted: list[warnings.WarningMessage],
) -> tuple[tuple[str, str], ...]:
    return tuple((item.category.__name__, str(item.message)) for item in emitted)


def _environment(case: DifferentialCase, cache: BytecodeCache) -> Environment:
    return Environment(
        loader=DictLoader(case.files),
        bytecode_cache=cache,
        preserve_ast=case.preserve_ast,
        static_context=case.static_context,
    )


def _compile(
    case: DifferentialCase,
    cache: BytecodeCache,
) -> tuple[Template, list[warnings.WarningMessage]]:
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        template = _environment(case, cache).get_template(case.target)
    return template, emitted


async def _render_outcome(
    template: Template,
    case: DifferentialCase,
    mode: RenderMode,
) -> RenderOutcome:
    try:
        if mode is RenderMode.FULL:
            output = template.render(**case.context)
        elif mode is RenderMode.STREAM:
            output = "".join(template.render_stream(**case.context))
        elif mode is RenderMode.STREAM_ASYNC:
            output = "".join(
                [chunk async for chunk in template.render_stream_async(**case.context)]
            )
        elif mode is RenderMode.ASYNC:
            output = await template.render_async(**case.context)
        elif mode is RenderMode.BLOCK:
            assert case.block_name is not None
            output = template.render_block(case.block_name, **case.context)
        elif mode is RenderMode.BLOCK_STREAM_ASYNC:
            assert case.block_name is not None
            output = "".join(
                [
                    chunk
                    async for chunk in template.render_block_stream_async(
                        case.block_name, **case.context
                    )
                ]
            )
        else:
            output = template.render_with_blocks(case.block_overrides, **case.context)
    except Exception as exc:  # The differential compares the full structured failure.
        return RenderOutcome(output=None, error=_error_facts(exc))
    return RenderOutcome(output=output, error=None)


def _expected_output(case: DifferentialCase, mode: RenderMode) -> str | None:
    if mode in BLOCK_MODES:
        return case.expected_block
    if mode is RenderMode.COMPOSITION:
        return case.expected_composition
    return case.expected_full


def _artifact_path(case: DifferentialCase, cache: BytecodeCache) -> Path:
    context_hash = _hash_static_context(case.static_context)
    return cache._make_path(
        case.target,
        hash_source(case.files[case.target]),
        context_hash=context_hash,
    )


def _mutate_record(case: DifferentialCase, path: Path) -> bytes:
    if case.record_state == "corrupt":
        malformed = b"not a Kida cache record"
    elif case.record_state == "incompatible":
        # This fixture uses preserve_ast=False, so appending a non-Node pickle
        # creates an incompatible optional-AST section without touching code.
        malformed = path.read_bytes() + pickle.dumps("not a Kida AST", protocol=5)
    else:
        return path.read_bytes()
    path.write_bytes(malformed)
    return malformed


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
async def test_source_and_bytecode_cache_contracts_match(
    tmp_path: Path,
    case: DifferentialCase,
) -> None:
    cache = BytecodeCache(tmp_path / "cache")
    source_template, source_emitted = _compile(case, cache)
    artifact_path = _artifact_path(case, cache)
    pristine_artifact = artifact_path.read_bytes()
    loaded_artifact = _mutate_record(case, artifact_path)

    cached_template, cached_emitted = _compile(case, cache)

    assert _warning_facts(cached_template) == _warning_facts(source_template)
    assert tuple(warning.code for warning in source_template.warnings) == (
        case.expected_warning_codes
    )
    assert _emitted_warning_facts(cached_emitted) == _emitted_warning_facts(source_emitted)

    if case.compare_introspection:
        assert source_template._optimized_ast is not None
        assert cached_template._optimized_ast is not None
        assert cached_template.template_metadata() == source_template.template_metadata()
        assert cached_template.list_blocks() == source_template.list_blocks()
    elif not case.preserve_ast:
        assert source_template._optimized_ast is None
        assert cached_template._optimized_ast is None

    if case.record_state == "clean":
        assert artifact_path.read_bytes() == pristine_artifact
    else:
        assert artifact_path.read_bytes() != loaded_artifact
        context_hash = _hash_static_context(case.static_context)
        cached_code, _cached_ast, _precomputed = cache.get(
            case.target,
            hash_source(case.files[case.target]),
            context_hash=context_hash,
        )
        assert cached_code is not None

    for mode in case.applicable_modes:
        source_outcome = await _render_outcome(source_template, case, mode)
        cached_outcome = await _render_outcome(cached_template, case, mode)
        assert cached_outcome == source_outcome, f"{case.name} diverged for {mode.value}"
        if mode in case.error_modes:
            assert source_outcome.error is not None
            assert source_outcome.error.code == ErrorCode.ZERO_DIVISION.value
            assert source_outcome.error.template_name == case.target
            assert source_outcome.error.lineno == 1
        else:
            assert source_outcome == RenderOutcome(
                output=_expected_output(case, mode),
                error=None,
            )


def test_every_fixture_classifies_every_render_mode() -> None:
    for case in CASES:
        unsupported = {mode for mode, reason in case.unsupported_modes if reason}
        assert case.applicable_modes | unsupported == ALL_MODES
        assert case.applicable_modes.isdisjoint(unsupported)
        assert len(unsupported) == len(case.unsupported_modes)
        if case.block_name is None:
            assert unsupported >= BLOCK_MODES
        else:
            assert not (BLOCK_MODES & unsupported)
