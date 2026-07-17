"""Conservative, opt-in extraction-candidate diagnostics.

The advisor combines independent structural, interaction/accessibility, and
lexical-boundary signals. It does not compute a universal score and never
rewrites source: the inferred props and slots are review inputs, not proof that
an extraction is desirable.
"""

from __future__ import annotations

import bisect
import json
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import TYPE_CHECKING

from kida.analysis.dependencies import DependencyWalker
from kida.analysis.shape_profiles import _facts, _ShapeParser, _walk
from kida.diagnostics import (
    Diagnostic,
    DiagnosticConfidence,
    DiagnosticReport,
    DiagnosticSeverity,
    RelatedLocation,
    SourcePosition,
    SourceSpan,
)
from kida.environment import Environment
from kida.exceptions import ErrorCode
from kida.lexer import Lexer
from kida.nodes import (
    AsyncFor,
    Block,
    CallBlock,
    Const,
    Def,
    For,
    FuncCall,
    Name,
    Node,
    Output,
    Provide,
    Region,
    Template,
    Tuple,
)
from kida.template import Template as CompiledTemplate

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence


_INTERACTIVE_TAGS = frozenset({"a", "button", "input", "select", "textarea"})
_REPEATED_BOUNDARY_TAGS = frozenset({"article", "form", "li", "section"})
_VOID_TAGS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source"}
)


@dataclass(slots=True)
class _HtmlElement:
    tag: str
    attrs: tuple[tuple[str, str | None], ...]
    start: int
    start_end: int
    end: int | None = None
    children: list[_HtmlElement] = field(default_factory=list)


class _HtmlStructureParser(HTMLParser):
    """Collect source-accurate literal HTML structure without dependencies."""

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=False)
        self.source = source
        self.roots: list[_HtmlElement] = []
        self._stack: list[_HtmlElement] = []
        self._line_starts = [0]
        self._line_starts.extend(index + 1 for index, char in enumerate(source) if char == "\n")

    def _offset(self) -> int:
        line, column = self.getpos()
        return self._line_starts[line - 1] + column

    def _append(self, element: _HtmlElement) -> None:
        target = self._stack[-1].children if self._stack else self.roots
        target.append(element)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        start = self._offset()
        text = self.get_starttag_text() or ""
        element = _HtmlElement(
            tag=tag,
            attrs=tuple(attrs),
            start=start,
            start_end=start + len(text),
        )
        self._append(element)
        if tag in _VOID_TAGS:
            element.end = element.start_end
        else:
            self._stack.append(element)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if self._stack and self._stack[-1].tag == tag:
            self._stack[-1].end = self._stack[-1].start_end
            self._stack.pop()

    def handle_endtag(self, tag: str) -> None:
        start = self._offset()
        closing = self.source.find(">", start)
        end = len(self.source) if closing < 0 else closing + 1
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index].tag != tag:
                continue
            self._stack[index].end = end
            del self._stack[index:]
            return


def _json_list(values: Iterable[str]) -> str:
    return json.dumps(sorted(set(values)), separators=(",", ":"))


def _metadata(**values: str) -> tuple[tuple[str, str], ...]:
    return tuple(sorted(values.items()))


def _line_starts(source: str) -> list[int]:
    starts = [0]
    starts.extend(index + 1 for index, char in enumerate(source) if char == "\n")
    return starts


def _offset(starts: Sequence[int], position: SourcePosition) -> int:
    assert position.column is not None
    return starts[position.line - 1] + position.column


def _position(starts: Sequence[int], offset: int) -> SourcePosition:
    line_index = bisect.bisect_right(starts, offset) - 1
    return SourcePosition(line=line_index + 1, column=offset - starts[line_index])


def _element_span(element: _HtmlElement, *, path: str, starts: Sequence[int]) -> SourceSpan:
    assert element.end is not None
    return SourceSpan(
        path=path,
        start=_position(starts, element.start),
        end=_position(starts, element.end),
    )


def _element_fingerprint(
    element: _HtmlElement, cache: dict[int, tuple[object, ...]]
) -> tuple[object, ...]:
    cached = cache.get(id(element))
    if cached is not None:
        return cached
    fingerprint = (
        element.tag,
        tuple(sorted(name for name, _value in element.attrs)),
        tuple(_element_fingerprint(child, cache) for child in element.children),
    )
    cache[id(element)] = fingerprint
    return fingerprint


def _all_elements(elements: Sequence[_HtmlElement]) -> list[_HtmlElement]:
    result: list[_HtmlElement] = []
    for element in elements:
        result.append(element)
        result.extend(_all_elements(element.children))
    return result


def _element_metrics(elements: Sequence[_HtmlElement]) -> tuple[int, int]:
    interactive = 0
    accessibility = 0
    seen: set[int] = set()
    for element in _all_elements(elements):
        if id(element) in seen:
            continue
        seen.add(id(element))
        interactive += element.tag in _INTERACTIVE_TAGS
        accessibility += sum(
            name.startswith("aria-")
            or name in {"alt", "datetime", "for", "id", "name", "role", "scope"}
            for name, _value in element.attrs
        )
    return interactive, accessibility


def _elements_inside(elements: Sequence[_HtmlElement], start: int, end: int) -> list[_HtmlElement]:
    return [
        element
        for element in _all_elements(elements)
        if element.end is not None and start <= element.start and element.end <= end
    ]


def _root_names(paths: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({path.split(".", 1)[0] for path in paths}))


def _target_names(node: Node) -> tuple[str, ...]:
    if isinstance(node, Name):
        return (node.name,)
    if isinstance(node, Tuple):
        return tuple(sorted(name for item in node.items for name in _target_names(item)))
    return ()


def _component_dependencies(node: Node) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                current.func.name
                for current, _depth in _walk(node)
                if isinstance(current, FuncCall)
                and isinstance(current.func, Name)
                and current.func.name != "consume"
            }
        )
    )


def _consume_dependencies(node: Node) -> tuple[str, ...]:
    dependencies: set[str] = set()
    for current, _depth in _walk(node):
        if not isinstance(current, FuncCall) or not isinstance(current.func, Name):
            continue
        if current.func.name != "consume" or not current.args:
            continue
        first = current.args[0]
        if isinstance(first, Const) and isinstance(first.value, str):
            dependencies.add(first.value)
        else:
            dependencies.add("<dynamic>")
    return tuple(sorted(dependencies))


def _possible_slots(elements: Sequence[_HtmlElement]) -> tuple[str, ...]:
    slots: set[str] = set()
    for element in elements:
        class_value = next((value for name, value in element.attrs if name == "class"), None)
        if class_value is None:
            continue
        if any(part == "actions" or part.endswith("-actions") for part in class_value.split()):
            slots.add("actions")
    return tuple(sorted(slots))


def _span_for_block(
    node: Node,
    *,
    path: str,
    block_type: str,
    profile_spans: dict[tuple[str, int, int], SourcePosition],
) -> SourceSpan:
    end = profile_spans.get((block_type, node.lineno, node.col_offset))
    if end is None:
        raise ValueError(
            f"missing exact end span for {block_type} at {node.lineno}:{node.col_offset}"
        )
    return SourceSpan(
        path=path,
        start=SourcePosition(line=node.lineno, column=node.col_offset),
        end=end,
    )


def _inside(span: SourceSpan, container: SourceSpan, starts: Sequence[int]) -> bool:
    assert span.start is not None and span.end is not None
    assert container.start is not None and container.end is not None
    return _offset(starts, container.start) <= _offset(starts, span.start) and _offset(
        starts, span.end
    ) <= _offset(starts, container.end)


def _boundary_spans(
    ast: Template,
    *,
    path: str,
    profile_spans: dict[tuple[str, int, int], SourcePosition],
) -> tuple[SourceSpan, ...]:
    block_types = {Def: "def", Region: "region", CallBlock: "call"}
    spans: list[SourceSpan] = []
    for node, _depth in _walk(ast):
        block_type = (
            "fragment"
            if isinstance(node, Block) and node.fragment
            else "block"
            if isinstance(node, Block)
            else next(
                (value for node_type, value in block_types.items() if isinstance(node, node_type)),
                None,
            )
        )
        if block_type is not None:
            spans.append(
                _span_for_block(
                    node,
                    path=path,
                    block_type=block_type,
                    profile_spans=profile_spans,
                )
            )
    return tuple(spans)


def _provided_names_for_span(
    ast: Template,
    span: SourceSpan,
    *,
    path: str,
    starts: Sequence[int],
    profile_spans: dict[tuple[str, int, int], SourcePosition],
) -> tuple[str, ...]:
    names: set[str] = set()
    for node, _depth in _walk(ast):
        if not isinstance(node, Provide):
            continue
        provide_span = _span_for_block(
            node,
            path=path,
            block_type="provide",
            profile_spans=profile_spans,
        )
        if _inside(span, provide_span, starts):
            names.add(node.name)
    return tuple(sorted(names))


def _diagnostic(
    *,
    span: SourceSpan,
    message: str,
    signals: Sequence[str],
    props: Sequence[str],
    slots: Sequence[str],
    context_dependencies: Sequence[str],
    component_dependencies: Sequence[str],
    provide_dependencies: Sequence[str],
    candidate_kind: str,
    related_locations: tuple[RelatedLocation, ...] = (),
    extra_metadata: tuple[tuple[str, str], ...] = (),
) -> Diagnostic:
    code = ErrorCode.MODULARITY_EXTRACTION_CANDIDATE
    metadata = dict(
        _metadata(
            candidate_kind=candidate_kind,
            component_dependencies=_json_list(component_dependencies),
            context_dependencies=_json_list(context_dependencies),
            existing_boundary_conflicts="[]",
            possible_slots=_json_list(slots),
            provide_consume_dependencies=_json_list(provide_dependencies),
            signals=_json_list(signals),
            tentative_props=_json_list(props),
        )
    )
    metadata.update(extra_metadata)
    return Diagnostic(
        code=code.value,
        category=code.category,
        severity=DiagnosticSeverity.INFO,
        title="Extraction candidate",
        kind="extraction-candidate",
        message=message,
        span=span,
        suggestion=(
            "Consider a typed local component at this boundary; review the tentative props "
            "and slots before changing source."
        ),
        safe_edit=None,
        related_locations=related_locations,
        confidence=DiagnosticConfidence.CONSERVATIVE,
        notes=(
            "Independent signals suggest a boundary, but reuse and product ownership need "
            "human judgment.",
            "Kida does not offer an automatic edit for extraction candidates.",
        ),
        documentation_url=code.docs_url,
        metadata=tuple(sorted(metadata.items())),
    )


def _loop_diagnostics(
    ast: Template,
    *,
    path: str,
    starts: Sequence[int],
    profile_spans: dict[tuple[str, int, int], SourcePosition],
    html_elements: Sequence[_HtmlElement],
    boundary_spans: Sequence[SourceSpan],
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for node, _depth in _walk(ast):
        if not isinstance(node, (For, AsyncFor)):
            continue
        span = _span_for_block(
            node,
            path=path,
            block_type="for",
            profile_spans=profile_spans,
        )
        if any(_inside(span, boundary, starts) for boundary in boundary_spans):
            continue
        facts = _facts(node, span)
        assert span.start is not None and span.end is not None
        start = _offset(starts, span.start)
        end = _offset(starts, span.end)
        elements = _elements_inside(html_elements, start, end)
        interactive, accessibility = _element_metrics(elements)
        body = Template(lineno=node.lineno, col_offset=node.col_offset, body=node.body)
        dependencies = tuple(sorted(DependencyWalker().analyze(body)))
        component_dependencies = _component_dependencies(body)
        target_names = _target_names(node.target)
        excluded = {*component_dependencies, "consume", "loop"}
        props = tuple(
            sorted(
                set(target_names)
                | {root for root in _root_names(dependencies) if root not in excluded}
            )
        )
        outer_dependencies = tuple(
            path_value
            for path_value in dependencies
            if path_value.split(".", 1)[0] not in {*target_names, *excluded}
        )

        substantial = facts.source_lines >= 8 and facts.node_count >= 24
        owns_interaction = interactive >= 2 and accessibility >= 2
        narrow_boundary = 1 <= len(props) <= 4
        has_behavior = facts.branch_count >= 1 and facts.dynamic_expression_count >= 8
        if not (substantial and owns_interaction and narrow_boundary and has_behavior):
            continue

        signals = [
            "iterated-region",
            "substantial-structure",
            "interactive-accessibility-structure",
            "narrow-lexical-boundary",
        ]
        if facts.repeated_shape_groups:
            signals.append("repeated-normalized-subtree")
        slots = _possible_slots(elements)
        provide_dependencies = _consume_dependencies(body)
        provide_dependencies = tuple(
            sorted(
                set(provide_dependencies)
                | set(
                    _provided_names_for_span(
                        ast,
                        span,
                        path=path,
                        starts=starts,
                        profile_spans=profile_spans,
                    )
                )
            )
        )
        diagnostics.append(
            _diagnostic(
                span=span,
                message=(
                    f"This loop-owned region has {facts.source_lines} source lines, "
                    f"{interactive} interactive elements, and {len(props)} tentative inputs; "
                    "those independent signals may support a local component boundary."
                ),
                signals=signals,
                props=props,
                slots=slots,
                context_dependencies=outer_dependencies,
                component_dependencies=component_dependencies,
                provide_dependencies=provide_dependencies,
                candidate_kind="iterated-region",
                extra_metadata=_metadata(
                    accessibility_relationships=str(accessibility),
                    branch_count=str(facts.branch_count),
                    interactive_elements=str(interactive),
                    loop_local_names=_json_list(target_names),
                    outer_names=_json_list(_root_names(outer_dependencies)),
                    referenced_local_names=_json_list(target_names),
                    source_lines=str(facts.source_lines),
                ),
            )
        )
    return diagnostics


def _source_fact_points(
    ast: Template, starts: Sequence[int]
) -> tuple[tuple[int, tuple[str, ...], tuple[str, ...], tuple[str, ...]], ...]:
    points: list[tuple[int, tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = []
    walker = DependencyWalker()
    for node, _depth in _walk(ast):
        if isinstance(node, Output):
            points.append(
                (
                    starts[node.lineno - 1] + node.col_offset,
                    tuple(sorted(walker.analyze(node))),
                    _component_dependencies(node),
                    _consume_dependencies(node),
                )
            )
    return tuple(sorted(points))


def _facts_in_element(
    source_fact_points: Sequence[tuple[int, tuple[str, ...], tuple[str, ...], tuple[str, ...]]],
    source_fact_offsets: Sequence[int],
    element: _HtmlElement,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    assert element.end is not None
    dependencies: set[str] = set()
    components: set[str] = set()
    consume_dependencies: set[str] = set()
    first = bisect.bisect_left(source_fact_offsets, element.start)
    last = bisect.bisect_left(source_fact_offsets, element.end, lo=first)
    for _offset_value, values, calls, consumes in source_fact_points[first:last]:
        dependencies.update(values)
        components.update(calls)
        consume_dependencies.update(consumes)
    return (
        tuple(sorted(dependencies)),
        tuple(sorted(components)),
        tuple(sorted(consume_dependencies)),
    )


def _repeated_groups(elements: Sequence[_HtmlElement]) -> list[list[_HtmlElement]]:
    groups: list[list[_HtmlElement]] = []
    fingerprint_cache: dict[int, tuple[object, ...]] = {}
    parents: list[Sequence[_HtmlElement]] = [elements]
    parents.extend(element.children for element in _all_elements(elements))
    for siblings in parents:
        by_shape: dict[tuple[object, ...], list[_HtmlElement]] = {}
        for sibling in siblings:
            if sibling.end is None or sibling.tag not in _REPEATED_BOUNDARY_TAGS:
                continue
            by_shape.setdefault(_element_fingerprint(sibling, fingerprint_cache), []).append(
                sibling
            )
        groups.extend(group for group in by_shape.values() if len(group) >= 2)
    return groups


def _repeated_diagnostics(
    ast: Template,
    *,
    path: str,
    source: str,
    starts: Sequence[int],
    html_elements: Sequence[_HtmlElement],
    boundary_spans: Sequence[SourceSpan],
    profile_spans: dict[tuple[str, int, int], SourcePosition],
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    source_fact_points = _source_fact_points(ast, starts)
    source_fact_offsets = tuple(point[0] for point in source_fact_points)
    for group in _repeated_groups(html_elements):
        primary = group[0]
        span = _element_span(primary, path=path, starts=starts)
        if any(_inside(span, boundary, starts) for boundary in boundary_spans):
            continue
        interactive, accessibility = _element_metrics([primary])
        source_lines = source[primary.start : primary.end].count("\n") + 1
        occurrence_facts = [
            _facts_in_element(source_fact_points, source_fact_offsets, element) for element in group
        ]
        dependency_groups = [facts[0] for facts in occurrence_facts]
        component_dependencies = tuple(
            sorted({name for facts in occurrence_facts for name in facts[1]})
        )
        consume_dependencies = {name for facts in occurrence_facts for name in facts[2]}
        excluded_roots = {*component_dependencies, "consume"}
        roots = _root_names(path_value for values in dependency_groups for path_value in values)
        roots = tuple(root for root in roots if root not in excluded_roots)
        substantial = source_lines >= 4
        owns_interaction = interactive >= 1 and accessibility >= 1
        narrow_variation = bool(roots) and len(roots) <= len(group) * 2
        if not (substantial and owns_interaction and narrow_variation):
            continue

        related = tuple(
            RelatedLocation(
                label=f"Equivalent repeated sibling {index}",
                span=_element_span(element, path=path, starts=starts),
            )
            for index, element in enumerate(group[1:], start=2)
        )
        diagnostics.append(
            _diagnostic(
                span=span,
                message=(
                    f"{len(group)} sibling <{primary.tag}> regions repeat the same interactive "
                    f"and accessibility structure while varying {len(roots)} lexical inputs."
                ),
                signals=(
                    "normalized-repeated-siblings",
                    "interactive-accessibility-structure",
                    "narrow-varying-input-boundary",
                ),
                props=roots,
                slots=(),
                context_dependencies=tuple(
                    sorted(
                        {
                            value
                            for values in dependency_groups
                            for value in values
                            if value.split(".", 1)[0] not in excluded_roots
                        }
                    )
                ),
                component_dependencies=component_dependencies,
                provide_dependencies=tuple(
                    sorted(
                        consume_dependencies
                        | set(
                            _provided_names_for_span(
                                ast,
                                span,
                                path=path,
                                starts=starts,
                                profile_spans=profile_spans,
                            )
                        )
                    )
                ),
                candidate_kind="repeated-siblings",
                related_locations=related,
                extra_metadata=_metadata(
                    accessibility_relationships=str(accessibility),
                    interactive_elements=str(interactive),
                    occurrence_count=str(len(group)),
                    occurrence_dependencies=json.dumps(
                        [list(values) for values in dependency_groups], separators=(",", ":")
                    ),
                    source_lines=str(source_lines),
                ),
            )
        )
    return diagnostics


def _parse(
    source: str, *, name: str, environment: Environment
) -> tuple[Template, dict[tuple[str, int, int], SourcePosition]]:
    tokens = tuple(Lexer(source, environment._lexer_config).tokenize())
    parser = _ShapeParser(
        tokens,
        name=name,
        filename=name,
        source=source,
        autoescape=environment.select_autoescape(name),
        extension_tags=environment._extension_tags or None,
    )
    return parser.parse(), parser.profile_spans


def _advise_extraction_source(
    source: str,
    *,
    name: str,
    environment: Environment,
    transparent_boundaries: tuple[SourceSpan, ...] = (),
) -> DiagnosticReport:
    """Collect candidates with selected existing boundaries open to nested advice."""
    ast, profile_spans = _parse(source, name=name, environment=environment)
    starts = _line_starts(source)
    html_parser = _HtmlStructureParser(source)
    html_parser.feed(source)
    html_parser.close()
    boundaries = _boundary_spans(
        ast,
        path=name,
        profile_spans=profile_spans,
    )
    boundaries = tuple(
        boundary for boundary in boundaries if boundary not in transparent_boundaries
    )
    diagnostics = _loop_diagnostics(
        ast,
        path=name,
        starts=starts,
        profile_spans=profile_spans,
        html_elements=html_parser.roots,
        boundary_spans=boundaries,
    )
    repeated = _repeated_diagnostics(
        ast,
        path=name,
        source=source,
        starts=starts,
        html_elements=html_parser.roots,
        boundary_spans=boundaries,
        profile_spans=profile_spans,
    )
    repeated_spans = tuple(diagnostic.span for diagnostic in repeated)
    diagnostics = [
        diagnostic
        for diagnostic in diagnostics
        if not any(
            _inside(repeated_span, diagnostic.span, starts) for repeated_span in repeated_spans
        )
    ]
    diagnostics.extend(repeated)
    diagnostics.sort(
        key=lambda diagnostic: (
            diagnostic.span.start.line if diagnostic.span.start else 0,
            diagnostic.span.start.column if diagnostic.span.start else 0,
            diagnostic.message,
        )
    )
    return DiagnosticReport(diagnostics=tuple(diagnostics))


def advise_extraction_source(
    source: str,
    *,
    name: str = "<string>",
    environment: Environment | None = None,
) -> DiagnosticReport:
    """Return conservative extraction candidates for one in-memory template."""
    if not isinstance(source, str):
        raise TypeError("source must be a string")
    if not isinstance(name, str):
        raise TypeError("name must be a string")
    if not name.strip():
        raise ValueError("name must not be empty")
    if environment is not None and not isinstance(environment, Environment):
        raise TypeError("environment must be a kida.Environment")

    return _advise_extraction_source(
        source,
        name=name,
        environment=environment or Environment(),
    )


def advise_extraction_template(template: CompiledTemplate) -> DiagnosticReport:
    """Return extraction candidates from a compiled template's retained source."""
    if not isinstance(template, CompiledTemplate):
        raise TypeError("template must be a kida.Template")
    source = template._source
    environment = template._env_ref()
    if source is None or environment is None:
        return DiagnosticReport(diagnostics=(), partial=True)
    return advise_extraction_source(
        source,
        name=template.name or "<string>",
        environment=environment,
    )


__all__ = ["advise_extraction_source", "advise_extraction_template"]
