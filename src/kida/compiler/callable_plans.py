"""Immutable signature plans for def and region lowering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from kida.nodes import Def, Region


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
