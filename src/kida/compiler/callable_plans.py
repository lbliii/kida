"""Immutable semantic plans for callable lowering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from kida.nodes.output import Data

if TYPE_CHECKING:
    from kida.nodes import CallBlock, Def, Expr, Node, Region, Slot


@final
@dataclass(frozen=True, slots=True)
class CallableParameterPlan:
    """One callable parameter before Python AST assembly."""

    name: str
    annotation: str | None


@final
@dataclass(frozen=True, slots=True)
class CallableSignaturePlan:
    """Semantic callable signature shared by def and region lowering."""

    public_name: str
    function_name: str
    parameters: tuple[CallableParameterPlan, ...]
    parameter_names: tuple[str, ...]
    bound_names: tuple[str, ...]
    default_parameter_names: tuple[str, ...]
    vararg: str | None
    kwarg: str | None


@final
@dataclass(frozen=True, slots=True)
class CallSlotPlan:
    """One call-block slot before callback AST assembly."""

    name: str
    function_name: str
    body: tuple[Node, ...]
    delegates_when_nested: bool


@final
@dataclass(frozen=True, slots=True)
class CallBlockPlan:
    """Ordered slot callbacks for one call block."""

    call: Expr
    slots: tuple[CallSlotPlan, ...]
    slot_function_items: tuple[tuple[str, str], ...]


@final
@dataclass(frozen=True, slots=True)
class SlotBindingPlan:
    """One scoped binding passed from a slot placeholder."""

    name: str
    expression: Expr


@final
@dataclass(frozen=True, slots=True)
class SlotRenderPlan:
    """Slot placeholder semantics before expression and body lowering."""

    name: str
    bindings: tuple[SlotBindingPlan, ...]
    binding_names: tuple[str, ...]
    body: tuple[Node, ...]


def _build_signature_plan(
    node: Def | Region,
    *,
    function_prefix: str,
    emitted_name: str | None = None,
) -> CallableSignaturePlan:
    parameters = tuple(
        CallableParameterPlan(name=parameter.name, annotation=parameter.annotation)
        for parameter in node.params
    )
    parameter_names = tuple(parameter.name for parameter in parameters)
    variadics = tuple(name for name in (node.vararg, node.kwarg) if name is not None)
    default_count = len(node.defaults)
    default_parameter_names = parameter_names[-default_count:] if default_count else ()
    return CallableSignaturePlan(
        public_name=node.name,
        function_name=f"{function_prefix}{emitted_name or node.name}",
        parameters=parameters,
        parameter_names=parameter_names,
        bound_names=(*parameter_names, *variadics),
        default_parameter_names=default_parameter_names,
        vararg=node.vararg,
        kwarg=node.kwarg,
    )


def plan_def_signature(node: Def) -> CallableSignaturePlan:
    """Build the immutable signature plan for a template def."""
    return _build_signature_plan(node, function_prefix="_def_")


def plan_region_signature(
    node: Region,
    *,
    emitted_name: str | None = None,
) -> CallableSignaturePlan:
    """Build the immutable signature plan for a template region."""
    return _build_signature_plan(
        node,
        function_prefix="_region_",
        emitted_name=emitted_name,
    )


def _slot_body_is_empty(body: tuple[Node, ...]) -> bool:
    """Treat whitespace-only data as an empty slot body."""
    return not body or all(isinstance(child, Data) and not child.value.strip() for child in body)


def plan_call_block(node: CallBlock) -> CallBlockPlan:
    """Build ordered immutable callback plans for a call block."""
    slots = tuple(_plan_call_slot(name, tuple(body)) for name, body in node.slots.items())
    return CallBlockPlan(
        call=node.call,
        slots=slots,
        slot_function_items=tuple((slot.name, slot.function_name) for slot in slots),
    )


def _plan_call_slot(name: str, body: tuple[Node, ...]) -> CallSlotPlan:
    """Build one slot plan after freezing its body sequence."""
    return CallSlotPlan(
        name=name,
        function_name=f"_caller_{name.replace('-', '_')}",
        body=body,
        delegates_when_nested=_slot_body_is_empty(body),
    )


def plan_slot_render(node: Slot) -> SlotRenderPlan:
    """Build the immutable binding and body plan for a slot placeholder."""
    bindings = tuple(
        SlotBindingPlan(name=name, expression=expression) for name, expression in node.bindings
    )
    return SlotRenderPlan(
        name=node.name,
        bindings=bindings,
        binding_names=tuple(binding.name for binding in bindings),
        body=tuple(node.body),
    )
