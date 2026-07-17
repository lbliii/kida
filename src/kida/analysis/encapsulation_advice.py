"""Conservative inverse advice for exact pass-through components.

This module analyzes an explicitly owned set of parsed templates as one call
graph. It emits flattening advice only when a definition has one same-owner
caller and its complete body preserves an identical downstream component
interface without adding markup, behavior, context, or policy.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from kida.analysis.extraction_advice import _span_for_block, _walk
from kida.diagnostics import (
    Diagnostic,
    DiagnosticConfidence,
    DiagnosticSeverity,
    RelatedLocation,
    SourcePosition,
    SourceSpan,
)
from kida.exceptions import ErrorCode
from kida.nodes import (
    CallBlock,
    Const,
    Data,
    Def,
    FromImport,
    FuncCall,
    Getattr,
    Import,
    Name,
    Node,
    Output,
    Slot,
    Template,
)
from kida.utils.template_keys import resolve_template_name

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence


_ComponentKey = tuple[str, str]


@dataclass(frozen=True, slots=True)
class _OwnedTemplate:
    owner: str
    name: str
    source_path: str
    ast: Template
    profile_spans: dict[tuple[str, int, int], SourcePosition]


@dataclass(frozen=True, slots=True)
class _Definition:
    key: _ComponentKey
    owner: str
    source_path: str
    node: Def
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class _CallSite:
    owner: str
    template: str
    span: SourceSpan


def _json_list(values: Iterable[str]) -> str:
    return json.dumps(sorted(set(values)), separators=(",", ":"))


def _shape(value: Any) -> object:
    """Return a location-neutral immutable shape for interface defaults."""
    if isinstance(value, Node):
        return (
            type(value).__name__,
            tuple(
                (name, _shape(getattr(value, name)))
                for name in value.__dataclass_fields__
                if name not in {"lineno", "col_offset"}
            ),
        )
    if isinstance(value, dict):
        return tuple(sorted((str(key), _shape(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_shape(item) for item in value)
    return value


def _same_interface(wrapper: Def, downstream: Def) -> bool:
    if wrapper.vararg is not None or wrapper.kwarg is not None:
        return False
    if downstream.vararg is not None or downstream.kwarg is not None:
        return False
    wrapper_params = tuple((param.name, param.annotation) for param in wrapper.params)
    downstream_params = tuple((param.name, param.annotation) for param in downstream.params)
    return wrapper_params == downstream_params and _shape(wrapper.defaults) == _shape(
        downstream.defaults
    )


def _forwarded_props(call: FuncCall, definition: Def) -> tuple[str, ...] | None:
    if call.dyn_args is not None or call.dyn_kwargs is not None:
        return None
    expected = tuple(param.name for param in definition.params)
    if len(call.args) + len(call.kwargs) != len(expected):
        return None

    forwarded: list[str] = []
    for index, value in enumerate(call.args):
        if not isinstance(value, Name) or value.name != expected[index]:
            return None
        forwarded.append(value.name)
    for name, value in call.kwargs.items():
        if name not in expected or not isinstance(value, Name) or value.name != name:
            return None
        forwarded.append(name)
    if set(forwarded) != set(expected):
        return None
    return tuple(sorted(forwarded))


def _slot_names(definition: Def) -> tuple[str, ...]:
    return tuple(
        sorted({current.name for current, _depth in _walk(definition) if isinstance(current, Slot)})
    )


def _forwarded_slots(call: CallBlock) -> tuple[str, ...] | None:
    slots: list[str] = []
    for body in call.slots.values():
        for node in body:
            if isinstance(node, Data) and not node.value.strip():
                continue
            if not isinstance(node, Slot) or node.bindings or node.body:
                return None
            slots.append(node.name)
    if len(slots) > 1 or len(slots) != len(set(slots)):
        return None
    return tuple(sorted(slots))


def _body_forwarding_call(definition: Def) -> tuple[FuncCall, tuple[str, ...]] | None:
    meaningful = [
        node for node in definition.body if not (isinstance(node, Data) and not node.value.strip())
    ]
    if len(meaningful) != 1:
        return None
    only = meaningful[0]
    if isinstance(only, Output) and isinstance(only.expr, FuncCall):
        return only.expr, ()
    if isinstance(only, CallBlock) and isinstance(only.call, FuncCall):
        slots = _forwarded_slots(only)
        if slots is not None:
            return only.call, slots
    return None


def _literal_template_name(node: Node) -> str | None:
    if isinstance(node, Const) and isinstance(node.value, str):
        return node.value
    return None


def _imports(
    template: _OwnedTemplate,
) -> tuple[dict[str, _ComponentKey], dict[str, str]]:
    names: dict[str, _ComponentKey] = {}
    modules: dict[str, str] = {}
    for node, _depth in _walk(template.ast):
        if isinstance(node, FromImport):
            raw_name = _literal_template_name(node.template)
            if raw_name is None:
                continue
            resolved = resolve_template_name(raw_name, caller=template.name)
            for original, alias in node.names:
                names[alias or original] = (resolved, original)
        elif isinstance(node, Import):
            raw_name = _literal_template_name(node.template)
            if raw_name is not None:
                modules[node.target] = resolve_template_name(raw_name, caller=template.name)
    return names, modules


def _resolve_call(
    call: FuncCall,
    *,
    template_name: str,
    definitions: dict[_ComponentKey, _Definition],
    imported_names: dict[str, _ComponentKey],
    imported_modules: dict[str, str],
) -> _ComponentKey | None:
    if isinstance(call.func, Name):
        local = (template_name, call.func.name)
        imported = imported_names.get(call.func.name)
        if local in definitions and imported is not None and imported != local:
            return None
        if local in definitions:
            return local
        return imported if imported in definitions else None
    if (
        isinstance(call.func, Getattr)
        and isinstance(call.func.obj, Name)
        and call.func.obj.name in imported_modules
    ):
        imported = (imported_modules[call.func.obj.name], call.func.attr)
        return imported if imported in definitions else None
    return None


def _definition_records(templates: Sequence[_OwnedTemplate]) -> dict[_ComponentKey, _Definition]:
    definitions: dict[_ComponentKey, _Definition] = {}
    for template in templates:
        for node, _depth in _walk(template.ast):
            if not isinstance(node, Def):
                continue
            key = (template.name, node.name)
            definitions[key] = _Definition(
                key=key,
                owner=template.owner,
                source_path=template.source_path,
                node=node,
                span=_span_for_block(
                    node,
                    path=template.name,
                    block_type="def",
                    profile_spans=template.profile_spans,
                ),
            )
    return definitions


def _call_graph(
    templates: Sequence[_OwnedTemplate],
    definitions: dict[_ComponentKey, _Definition],
) -> tuple[
    dict[_ComponentKey, list[_CallSite]],
    dict[int, _ComponentKey],
]:
    calls: dict[_ComponentKey, list[_CallSite]] = defaultdict(list)
    resolutions: dict[int, _ComponentKey] = {}
    for template in templates:
        imported_names, imported_modules = _imports(template)
        for node, _depth in _walk(template.ast):
            if not isinstance(node, FuncCall):
                continue
            target = _resolve_call(
                node,
                template_name=template.name,
                definitions=definitions,
                imported_names=imported_names,
                imported_modules=imported_modules,
            )
            if target is None:
                continue
            resolutions[id(node)] = target
            calls[target].append(
                _CallSite(
                    owner=template.owner,
                    template=template.name,
                    span=SourceSpan(
                        path=template.name,
                        start=SourcePosition(line=node.lineno, column=node.col_offset),
                    ),
                )
            )
    for sites in calls.values():
        sites.sort(
            key=lambda site: (
                site.template,
                site.span.start.line if site.span.start else -1,
                site.span.start.column if site.span.start else -1,
            )
        )
    return calls, resolutions


def _diagnostic(
    definition: _Definition,
    downstream: _Definition,
    caller: _CallSite,
    *,
    props: Sequence[str],
    slots: Sequence[str],
) -> Diagnostic:
    code = ErrorCode.MODULARITY_PASS_THROUGH_COMPONENT
    signals = [
        "exact-interface-forwarding",
        "no-owned-markup-or-behavior",
        "same-owner-downstream",
        "single-downstream-component",
        "single-same-owner-caller",
    ]
    if slots:
        signals.append("single-slot-forwarding")
    prop_word = "prop" if len(props) == 1 else "props"
    slot_clause = f" and {len(slots)} slot" if slots else ""
    return Diagnostic(
        code=code.value,
        category=code.category,
        severity=DiagnosticSeverity.INFO,
        title="Pass-through component",
        kind="flatten-candidate",
        message=(
            f"Component '{definition.node.name}' has one same-owner caller and only forwards "
            f"{len(props)} identically named {prop_word}{slot_clause} to "
            f"'{downstream.node.name}' without owning markup or behavior."
        ),
        span=definition.span,
        suggestion=(
            f"Consider calling '{downstream.node.name}' directly from '{caller.template}'. "
            "Keep the wrapper if it represents a documented public, product, test, or adapter boundary."
        ),
        safe_edit=None,
        related_locations=(
            RelatedLocation(label="Only same-owner caller", span=caller.span),
            RelatedLocation(label="Forwarded component", span=downstream.span),
        ),
        confidence=DiagnosticConfidence.CONSERVATIVE,
        notes=(
            "The finding requires exact interface forwarding and no owned template policy.",
            "Cross-root callers or downstream components, reused wrappers, markup, control flow, accessibility structure, and context boundaries suppress this advice.",
        ),
        documentation_url=code.docs_url,
        metadata=tuple(
            sorted(
                {
                    "caller_count": "1",
                    "caller_templates": _json_list((caller.template,)),
                    "candidate_kind": "pass-through-component",
                    "component_name": definition.node.name,
                    "downstream_component": downstream.node.name,
                    "downstream_owner": downstream.owner,
                    "downstream_template": downstream.key[0],
                    "forwarded_props": _json_list(props),
                    "forwarded_slots": _json_list(slots),
                    "interface_match": "exact",
                    "owner": definition.owner,
                    "signals": _json_list(signals),
                    "source_path": definition.source_path,
                }.items()
            )
        ),
    )


def _advise_flattening(templates: Sequence[_OwnedTemplate]) -> tuple[Diagnostic, ...]:
    definitions = _definition_records(templates)
    calls, resolutions = _call_graph(templates, definitions)
    diagnostics: list[Diagnostic] = []
    for key, definition in sorted(definitions.items()):
        callers = calls.get(key)
        if callers is None or len(callers) != 1 or callers[0].owner != definition.owner:
            continue
        forwarding = _body_forwarding_call(definition.node)
        if forwarding is None:
            continue
        call, forwarded_slots = forwarding
        downstream_key = resolutions.get(id(call))
        if downstream_key is None or downstream_key == key:
            continue
        downstream = definitions[downstream_key]
        if downstream.owner != definition.owner:
            continue
        if not _same_interface(definition.node, downstream.node):
            continue
        forwarded_props = _forwarded_props(call, definition.node)
        if forwarded_props is None:
            continue
        if forwarded_slots != _slot_names(downstream.node):
            continue
        diagnostics.append(
            _diagnostic(
                definition,
                downstream,
                callers[0],
                props=forwarded_props,
                slots=forwarded_slots,
            )
        )
    diagnostics.sort(
        key=lambda diagnostic: (
            diagnostic.span.path or "",
            diagnostic.span.start.line if diagnostic.span.start else -1,
            diagnostic.span.start.column if diagnostic.span.start else -1,
            diagnostic.message,
        )
    )
    return tuple(diagnostics)


__all__: list[str] = []
