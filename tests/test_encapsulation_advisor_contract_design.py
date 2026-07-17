"""Evidence-only probes for the encapsulation-advisor contract.

The profiler in this test is intentionally private. It measures candidate
dimensions against real parser output without adding an analyzer, diagnostic,
CLI flag, schema, or public API before the contract is reviewed.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from kida import Environment
from kida.analysis.dependencies import DependencyWalker
from kida.lexer import Lexer
from kida.nodes import (
    AsyncFor,
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

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "encapsulation_advisor"
TEMPLATE_ROOT = FIXTURE_ROOT / "templates"
MANIFEST = FIXTURE_ROOT / "manifest.json"
PROFILES = FIXTURE_ROOT / "profiles.json"
CONTRACT = ROOT / "docs" / "audit" / "encapsulation-advisor-contract.md"

_INTERACTIVE_TAG = re.compile(r"<(?:a|button|input|select|textarea)\b", re.IGNORECASE)
_MARKUP_BLOCK = re.compile(
    r"<(?P<tag>article|form|li|tr)\b[^>]*>.*?</(?P=tag)>",
    re.IGNORECASE | re.DOTALL,
)
_MARKUP_TAG = re.compile(r"</?([a-z][a-z0-9-]*)\b", re.IGNORECASE)


def _parse(source: str, name: str) -> Template:
    env = Environment()
    tokens = list(Lexer(source, env._lexer_config).tokenize())
    return Parser(
        tokens,
        name=name,
        filename=name,
        source=source,
        autoescape=env.select_autoescape(name),
    ).parse()


def _walk(node: Node, depth: int = 0) -> list[tuple[Node, int]]:
    walked = [(node, depth)]
    for child in node.iter_child_nodes():
        walked.extend(_walk(child, depth + 1))
    return walked


def _subtree_size(node: Node) -> int:
    return 1 + sum(_subtree_size(child) for child in node.iter_child_nodes())


def _shape(node: Node) -> tuple[str, tuple[Any, ...]]:
    return type(node).__name__, tuple(_shape(child) for child in node.iter_child_nodes())


def _markup_shape(block: str) -> tuple[str, ...]:
    return tuple(tag.lower() for tag in _MARKUP_TAG.findall(block))


def _component_call_count(nodes: list[Node]) -> int:
    return sum(isinstance(node, FuncCall) and isinstance(node.func, Name) for node in nodes)


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


def _profile(source: str, name: str) -> dict[str, object]:
    ast = _parse(source, name)
    walked = _walk(ast)
    nodes = [node for node, _depth in walked]
    dynamic_expressions = sum(
        isinstance(node, Expr)
        and not isinstance(node, Const)
        and not (isinstance(node, Name) and node.ctx != "load")
        for node in nodes
    )
    ast_shapes = Counter(
        _shape(node)
        for node in nodes
        if not isinstance(node, Template) and _subtree_size(node) >= 4
    )
    markup_shapes = Counter(
        shape
        for block in _MARKUP_BLOCK.finditer(source)
        if (shape := _markup_shape(block.group(0)))
    )
    node_count = len(nodes)
    return {
        "ast_repeated_shape_groups": sum(count > 1 for count in ast_shapes.values()),
        "branch_count": _branch_count(nodes),
        "component_call_count": _component_call_count(nodes),
        "context_dependencies": sorted(DependencyWalker().analyze(ast)),
        "definition_count": sum(isinstance(node, (Def, Region)) for node in nodes),
        "dynamic_density_basis_points": round(dynamic_expressions * 10_000 / node_count),
        "dynamic_expression_count": dynamic_expressions,
        "interactive_element_count": len(_INTERACTIVE_TAG.findall(source)),
        "loop_count": sum(isinstance(node, (For, AsyncFor, While)) for node in nodes),
        "markup_repeated_shape_groups": sum(count > 1 for count in markup_shapes.values()),
        "max_depth": max(depth for _node, depth in walked),
        "node_count": node_count,
        "slot_count": sum(isinstance(node, (Slot, SlotBlock)) for node in nodes),
        "source_lines": len(source.splitlines()),
    }


def _measured_profiles() -> dict[str, object]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cases = {}
    for case in manifest["cases"]:
        source = (TEMPLATE_ROOT / case["file"]).read_text(encoding="utf-8")
        cases[case["id"]] = _profile(source, case["file"])
    return {
        "cases": cases,
        "contract": "kida.encapsulation-advisor-profiles",
        "contract_version": 1,
    }


def test_labeled_corpus_and_profiles_are_deterministic() -> None:
    manifest_text = MANIFEST.read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    profile_text = PROFILES.read_text(encoding="utf-8")
    expected_profiles = json.loads(profile_text)

    assert manifest_text == json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    assert profile_text == json.dumps(expected_profiles, indent=2, sort_keys=True) + "\n"
    assert _measured_profiles() == expected_profiles
    assert [case["id"] for case in manifest["cases"]] == sorted(
        case["id"] for case in manifest["cases"]
    )


def test_corpus_protects_positive_negative_and_inverse_advice() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    classifications = Counter(case["classification"] for case in manifest["cases"])
    profiles = _measured_profiles()["cases"]

    assert classifications == {
        "extract-candidate": 2,
        "flatten-candidate": 1,
        "keep-component": 1,
        "keep-inline": 3,
    }
    assert (
        profiles["healthy-layout"]["source_lines"]
        > profiles["message-row-candidate"]["source_lines"]
    )
    assert (
        profiles["healthy-layout"]["node_count"] < profiles["message-row-candidate"]["node_count"]
    )
    assert (
        profiles["monolithic-report"]["branch_count"]
        >= profiles["message-row-candidate"]["branch_count"]
    )
    assert profiles["route-composition"]["component_call_count"] > 0
    assert profiles["pass-through-component"]["definition_count"] == 1
    assert profiles["repeated-actions-candidate"]["markup_repeated_shape_groups"] > 0


def test_dimensions_remain_independent_and_no_opaque_score_is_committed() -> None:
    profiles = _measured_profiles()["cases"]
    dimensions = (
        "node_count",
        "max_depth",
        "branch_count",
        "loop_count",
        "dynamic_expression_count",
        "dynamic_density_basis_points",
        "ast_repeated_shape_groups",
        "markup_repeated_shape_groups",
        "component_call_count",
        "slot_count",
        "interactive_element_count",
    )
    for dimension in dimensions:
        assert len({profile[dimension] for profile in profiles.values()}) > 1

    serialized = json.dumps(profiles)
    assert '"score"' not in serialized
    assert '"complexity"' not in serialized


def test_decision_record_freezes_advisory_semantics_and_failure_modes() -> None:
    contract = CONTRACT.read_text(encoding="utf-8")

    for heading in (
        "## Evidence Corpus",
        "## Independent Shape Facts",
        "## Advisory Diagnostic Contract",
        "## Candidate And Suppression Semantics",
        "## Output And Compatibility Decision",
        "## Calibration Gate",
        "## Signal Failure Modes",
    ):
        assert heading in contract

    for decision in (
        "DiagnosticSeverity.INFO",
        "DiagnosticConfidence.CONSERVATIVE",
        "non-failing by default",
        "no safe edit",
        "No source-level suppression syntax",
        "K-MOD-102",
        "K-MOD-103",
        "No opaque aggregate score",
    ):
        assert decision in contract
