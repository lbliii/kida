"""Deterministic, policy-neutral template shape profiles.

This module measures source structure without rendering and without turning the
facts into advice.  The parser subclass records block-end positions only for an
explicit profiling call; ordinary parsing and compilation are unchanged.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, final

from kida.analysis.attributes import extract_literal_attributes
from kida.analysis.dependencies import DependencyWalker
from kida.diagnostics import SourcePosition, SourceSpan
from kida.environment import Environment
from kida.lexer import Lexer
from kida.nodes import (
    AsyncFor,
    Block,
    Const,
    Def,
    Expr,
    For,
    FuncCall,
    If,
    Match,
    Name,
    Node,
    Region,
    Slot,
    SlotBlock,
    Template,
    Try,
    While,
)
from kida.parser import Parser
from kida.template import Template as CompiledTemplate

if TYPE_CHECKING:
    from kida._types import Token

ShapeProfileKind = Literal["template", "definition", "region", "block"]

_PROFILE_CONTRACT = "kida.shape-profiles"
_PROFILE_CONTRACT_VERSION = 1


def _position_dict(position: SourcePosition | None) -> dict[str, int | None] | None:
    if position is None:
        return None
    return {"column": position.column, "line": position.line}


def _span_dict(span: SourceSpan) -> dict[str, object]:
    return {
        "end": _position_dict(span.end),
        "path": span.path,
        "start": _position_dict(span.start),
    }


@final
@dataclass(frozen=True, slots=True)
class ShapeFacts:
    """Independent measurements for one template-owned source region."""

    node_count: int
    source_lines: int
    max_depth: int
    branch_count: int
    loop_count: int
    dynamic_expression_count: int
    dynamic_density_basis_points: int
    component_call_count: int
    slot_count: int
    literal_attribute_count: int
    repeated_shape_groups: int
    context_dependencies: tuple[str, ...]
    structural_fingerprint: str

    def __post_init__(self) -> None:
        counts = (
            self.node_count,
            self.source_lines,
            self.max_depth,
            self.branch_count,
            self.loop_count,
            self.dynamic_expression_count,
            self.component_call_count,
            self.slot_count,
            self.literal_attribute_count,
            self.repeated_shape_groups,
        )
        if any(value < 0 for value in counts):
            raise ValueError("shape fact counts must not be negative")
        if not 0 <= self.dynamic_density_basis_points <= 10_000:
            raise ValueError("dynamic density must be between 0 and 10,000 basis points")
        if self.context_dependencies != tuple(sorted(set(self.context_dependencies))):
            raise ValueError("context dependencies must be unique and sorted")
        if any(not dependency.strip() for dependency in self.context_dependencies):
            raise ValueError("context dependencies must not be empty")
        if len(self.structural_fingerprint) != 64:
            raise ValueError("structural fingerprint must be a SHA-256 hex digest")
        try:
            int(self.structural_fingerprint, 16)
        except ValueError as error:
            raise ValueError("structural fingerprint must be a SHA-256 hex digest") from error

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible mapping with deterministic field values."""
        return {
            "branch_count": self.branch_count,
            "component_call_count": self.component_call_count,
            "context_dependencies": list(self.context_dependencies),
            "dynamic_density_basis_points": self.dynamic_density_basis_points,
            "dynamic_expression_count": self.dynamic_expression_count,
            "literal_attribute_count": self.literal_attribute_count,
            "loop_count": self.loop_count,
            "max_depth": self.max_depth,
            "node_count": self.node_count,
            "repeated_shape_groups": self.repeated_shape_groups,
            "slot_count": self.slot_count,
            "source_lines": self.source_lines,
            "structural_fingerprint": self.structural_fingerprint,
        }


@final
@dataclass(frozen=True, slots=True)
class ShapeProfile:
    """Shape facts and exact ownership span for one analyzed region."""

    kind: ShapeProfileKind
    name: str | None
    span: SourceSpan
    facts: ShapeFacts

    def __post_init__(self) -> None:
        if self.kind not in {"template", "definition", "region", "block"}:
            raise ValueError(f"unsupported shape profile kind: {self.kind}")
        if self.name is not None and not self.name.strip():
            raise ValueError("shape profile name must not be empty")
        if not self.span.is_exact:
            raise ValueError("shape profile requires an exact source span")

    def to_dict(self) -> dict[str, object]:
        """Return this profile as a deterministic JSON-compatible mapping."""
        return {
            "facts": self.facts.to_dict(),
            "kind": self.kind,
            "name": self.name,
            "span": _span_dict(self.span),
        }


@final
@dataclass(frozen=True, slots=True)
class ShapeProfileReport:
    """Policy-neutral result of one shape-profile request."""

    template_name: str
    profiles: tuple[ShapeProfile, ...]
    partial: bool = False

    def __post_init__(self) -> None:
        if not self.template_name.strip():
            raise ValueError("template name must not be empty")

    def to_dict(self) -> dict[str, object]:
        """Return the stable shape-profile v1 structured representation."""
        return {
            "contract": _PROFILE_CONTRACT,
            "contract_version": _PROFILE_CONTRACT_VERSION,
            "partial": self.partial,
            "profiles": [profile.to_dict() for profile in self.profiles],
            "template_name": self.template_name,
        }


class _ShapeParser(Parser):
    """Parser that records exact block ranges for this analysis call only."""

    __slots__ = ("_profile_stack", "profile_spans")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.profile_spans: dict[tuple[str, int, int], SourcePosition] = {}
        self._profile_stack: list[tuple[str, int, int]] = []

    def _push_block(self, block_type: str, token: Token | None = None) -> None:
        tok = token or self._current
        super()._push_block(block_type, token)
        self._profile_stack.append((block_type, tok.lineno, tok.col_offset))

    def _pop_block(self, expected: str | None = None) -> str:
        end_token = self._current
        block_type = super()._pop_block(expected)
        opened = self._profile_stack.pop()
        self.profile_spans[opened] = SourcePosition(
            line=end_token.lineno,
            column=end_token.col_offset + len(end_token.value),
        )
        return block_type


def _walk(node: Node, depth: int = 0) -> list[tuple[Node, int]]:
    walked = [(node, depth)]
    for child in node.iter_child_nodes():
        walked.extend(_walk(child, depth + 1))
    return walked


def _shape_inventory(node: Node) -> tuple[str, Counter[str]]:
    inventory: Counter[str] = Counter()

    def visit(current: Node) -> tuple[str, int]:
        children = [visit(child) for child in current.iter_child_nodes()]
        digest = hashlib.sha256(type(current).__name__.encode())
        for child_digest, _child_size in children:
            digest.update(b"\0")
            digest.update(child_digest.encode())
        fingerprint = digest.hexdigest()
        size = 1 + sum(item[1] for item in children)
        if size >= 4:
            inventory[fingerprint] += 1
        return fingerprint, size

    root_fingerprint, _root_size = visit(node)
    return root_fingerprint, inventory


def _branch_count(nodes: list[Node]) -> int:
    total = 0
    for node in nodes:
        if isinstance(node, If):
            total += 1 + len(node.elif_) + bool(node.else_)
        elif isinstance(node, Match):
            total += len(node.cases)
        elif isinstance(node, Try) or (isinstance(node, (For, AsyncFor)) and node.empty):
            total += 1
    return total


def _source_line_count(span: SourceSpan) -> int:
    if span.start is None or span.end is None:
        return 0
    if span.start == span.end:
        return 0
    lines = span.end.line - span.start.line + 1
    if span.end.column == 0 and span.end.line > span.start.line:
        lines -= 1
    return lines


def _facts(node: Node, span: SourceSpan) -> ShapeFacts:
    walked = _walk(node)
    nodes = [current for current, _depth in walked]
    dynamic_expressions = sum(
        isinstance(current, Expr)
        and not isinstance(current, Const)
        and not (isinstance(current, Name) and current.ctx != "load")
        for current in nodes
    )
    fingerprint, shape_inventory = _shape_inventory(node)
    node_count = len(nodes)
    return ShapeFacts(
        node_count=node_count,
        source_lines=_source_line_count(span),
        max_depth=max(depth for _current, depth in walked),
        branch_count=_branch_count(nodes),
        loop_count=sum(isinstance(current, (For, AsyncFor, While)) for current in nodes),
        dynamic_expression_count=dynamic_expressions,
        dynamic_density_basis_points=round(dynamic_expressions * 10_000 / node_count),
        component_call_count=sum(
            isinstance(current, FuncCall) and isinstance(current.func, Name) for current in nodes
        ),
        slot_count=sum(isinstance(current, (Slot, SlotBlock)) for current in nodes),
        literal_attribute_count=len(extract_literal_attributes(node)),
        repeated_shape_groups=sum(count > 1 for count in shape_inventory.values()),
        context_dependencies=tuple(sorted(DependencyWalker().analyze(node))),
        structural_fingerprint=fingerprint,
    )


def _source_end(source: str) -> SourcePosition:
    line = source.count("\n") + 1
    column = len(source.rsplit("\n", 1)[-1])
    return SourcePosition(line=line, column=column)


def _block_type(node: Node) -> str | None:
    if isinstance(node, Def):
        return "def"
    if isinstance(node, Region):
        return "region"
    if isinstance(node, Block):
        return "fragment" if node.fragment else "block"
    return None


def _profile_kind(node: Node) -> ShapeProfileKind | None:
    if isinstance(node, Def):
        return "definition"
    if isinstance(node, Region):
        return "region"
    if isinstance(node, Block):
        return "block"
    return None


def _profile_name(node: Node) -> str | None:
    if isinstance(node, (Def, Region, Block)):
        return node.name
    return None


def _region_span(
    node: Node,
    *,
    path: str,
    profile_spans: dict[tuple[str, int, int], SourcePosition],
) -> SourceSpan:
    block_type = _block_type(node)
    if block_type is None:
        raise TypeError(f"unsupported profile node: {type(node).__name__}")
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


def _build_profiles(
    ast: Template,
    *,
    source: str,
    path: str,
    profile_spans: dict[tuple[str, int, int], SourcePosition],
) -> tuple[ShapeProfile, ...]:
    template_span = SourceSpan(
        path=path,
        start=SourcePosition(line=1, column=0),
        end=_source_end(source),
    )
    template_profile = ShapeProfile(
        kind="template",
        name=path,
        span=template_span,
        facts=_facts(ast, template_span),
    )
    nested: list[ShapeProfile] = []
    for node, _depth in _walk(ast):
        kind = _profile_kind(node)
        if kind is None:
            continue
        span = _region_span(node, path=path, profile_spans=profile_spans)
        nested.append(
            ShapeProfile(
                kind=kind,
                name=_profile_name(node),
                span=span,
                facts=_facts(node, span),
            )
        )
    nested.sort(
        key=lambda profile: (
            profile.span.start.line if profile.span.start else 0,
            profile.span.start.column if profile.span.start else 0,
            profile.kind,
            profile.name or "",
        )
    )
    return (template_profile, *nested)


def profile_source(
    source: str,
    *,
    name: str = "<string>",
    environment: Environment | None = None,
) -> ShapeProfileReport:
    """Profile in-memory template source without rendering or caching it."""
    if not isinstance(source, str):
        raise TypeError("source must be a string")
    if not isinstance(name, str):
        raise TypeError("name must be a string")
    if not name.strip():
        raise ValueError("name must not be empty")
    if environment is not None and not isinstance(environment, Environment):
        raise TypeError("environment must be a kida.Environment")

    env = environment or Environment()
    tokens = tuple(Lexer(source, env._lexer_config).tokenize())
    parser = _ShapeParser(
        tokens,
        name=name,
        filename=name,
        source=source,
        autoescape=env.select_autoescape(name),
        extension_tags=env._extension_tags or None,
    )
    ast = parser.parse()
    return ShapeProfileReport(
        template_name=name,
        profiles=_build_profiles(
            ast,
            source=source,
            path=name,
            profile_spans=parser.profile_spans,
        ),
    )


def profile_template(template: CompiledTemplate) -> ShapeProfileReport:
    """Profile a compiled template from its retained source.

    Re-parsing is intentional: the result describes source shape rather than
    optimization artifacts, so fresh compilations and bytecode-cache hits have
    identical profiles.  A partial empty report is returned only when the
    compiled template no longer has retained source or its environment.
    """
    if not isinstance(template, CompiledTemplate):
        raise TypeError("template must be a kida.Template")
    name = template.name or "<string>"
    source = template._source
    environment = template._env_ref()
    if source is None or environment is None:
        return ShapeProfileReport(template_name=name, profiles=(), partial=True)
    return profile_source(source, name=name, environment=environment)


__all__ = [
    "ShapeFacts",
    "ShapeProfile",
    "ShapeProfileKind",
    "ShapeProfileReport",
    "profile_source",
    "profile_template",
]
