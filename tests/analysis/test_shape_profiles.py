"""Public contract and behavioral proof for deterministic shape profiles."""

from __future__ import annotations

import inspect
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
from pathlib import Path

import pytest

from kida import DictLoader, Environment
from kida.analysis import (
    ShapeFacts,
    ShapeProfile,
    ShapeProfileReport,
    profile_source,
    profile_template,
)
from kida.bytecode_cache import BytecodeCache, hash_source
from kida.parser import ParseError

SOURCE = """{% template page: dict, items: list %}
{% def card(item: dict) %}
<article class="card" data-kind="project">
  <h2>{{ item.title }}</h2>
  {% for action in item.actions %}
    {{ button(label=action.label, url=action.url) }}
  {% endfor %}
  <footer>{{ site.name }}</footer>
</article>
{% enddef %}
{% region status(value: str) %}<span class="status">{{ value }}</span>{% end %}
{% block body %}{{ card(item=page.featured) }}{% endblock %}
"""

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "encapsulation_advisor"
REPORT_SNAPSHOT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "shape_profiles" / "report.json"
)


def _profile(report: ShapeProfileReport, kind: str, name: str) -> ShapeProfile:
    return next(
        profile for profile in report.profiles if profile.kind == kind and profile.name == name
    )


def _offset(source: str, line: int, column: int) -> int:
    lines = source.splitlines(keepends=True)
    return sum(len(value) for value in lines[: line - 1]) + column


def _slice(source: str, profile: ShapeProfile) -> str:
    assert profile.span.start is not None
    assert profile.span.end is not None
    return source[
        _offset(source, profile.span.start.line, profile.span.start.column) : _offset(
            source, profile.span.end.line, profile.span.end.column
        )
    ]


def test_public_shape_profile_contract_is_additive_and_analysis_only() -> None:
    import kida
    import kida.analysis as analysis

    expected = {
        "ShapeFacts",
        "ShapeProfile",
        "ShapeProfileKind",
        "ShapeProfileReport",
        "profile_source",
        "profile_template",
    }

    assert expected <= set(analysis.__all__)
    assert expected.isdisjoint(kida.__all__)
    assert [field.name for field in fields(ShapeFacts)] == [
        "node_count",
        "source_lines",
        "max_depth",
        "branch_count",
        "loop_count",
        "dynamic_expression_count",
        "dynamic_density_basis_points",
        "component_call_count",
        "slot_count",
        "literal_attribute_count",
        "repeated_shape_groups",
        "context_dependencies",
        "structural_fingerprint",
    ]
    assert [field.name for field in fields(ShapeProfile)] == [
        "kind",
        "name",
        "span",
        "facts",
    ]
    assert [field.name for field in fields(ShapeProfileReport)] == [
        "template_name",
        "profiles",
        "partial",
    ]
    assert str(inspect.signature(profile_source)) == (
        "(source: 'str', *, name: 'str' = '<string>', "
        "environment: 'Environment | None' = None) -> 'ShapeProfileReport'"
    )
    assert str(inspect.signature(profile_template)) == (
        "(template: 'CompiledTemplate') -> 'ShapeProfileReport'"
    )


def test_profile_source_reports_independent_facts_and_exact_owner_spans() -> None:
    report = profile_source(SOURCE, name="components/page.kida")

    assert [(profile.kind, profile.name) for profile in report.profiles] == [
        ("template", "components/page.kida"),
        ("definition", "card"),
        ("region", "status"),
        ("block", "body"),
    ]
    assert all(profile.span.is_exact for profile in report.profiles)

    card = _profile(report, "definition", "card")
    assert _slice(SOURCE, card).startswith("def card(item: dict)")
    assert _slice(SOURCE, card).endswith("enddef %}")
    assert card.facts.loop_count == 1
    assert card.facts.component_call_count == 1
    assert card.facts.literal_attribute_count == 2
    assert card.facts.context_dependencies == ("button", "site.name")
    assert len(card.facts.structural_fingerprint) == 64

    status = _profile(report, "region", "status")
    assert _slice(SOURCE, status).endswith("end %}")
    assert status.facts.context_dependencies == ()

    body = _profile(report, "block", "body")
    assert _slice(SOURCE, body).endswith("endblock %}")
    assert body.facts.component_call_count == 1


def test_structured_output_is_stable_json_without_advisory_policy() -> None:
    first = profile_source(SOURCE, name="page.kida").to_dict()
    second = profile_source(SOURCE, name="page.kida").to_dict()

    assert first == second
    assert first["contract"] == "kida.shape-profiles"
    assert first["contract_version"] == 1
    serialized = json.dumps(first, sort_keys=True)
    assert '"score"' not in serialized
    assert '"severity"' not in serialized
    assert '"suggestion"' not in serialized


def test_structured_output_matches_the_versioned_golden_snapshot() -> None:
    source = (FIXTURE_ROOT / "templates" / "healthy_component.kida").read_text(encoding="utf-8")
    expected_text = REPORT_SNAPSHOT.read_text(encoding="utf-8")
    expected = json.loads(expected_text)

    assert expected_text == json.dumps(expected, indent=2, sort_keys=True) + "\n"
    assert profile_source(source, name="healthy_component.kida").to_dict() == expected


def test_production_profiles_preserve_the_approved_evidence_measurements() -> None:
    manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    expected = json.loads((FIXTURE_ROOT / "profiles.json").read_text(encoding="utf-8"))["cases"]
    comparable = {
        "node_count",
        "source_lines",
        "max_depth",
        "branch_count",
        "loop_count",
        "dynamic_expression_count",
        "dynamic_density_basis_points",
        "component_call_count",
        "slot_count",
        "context_dependencies",
    }

    for case in manifest["cases"]:
        source = (FIXTURE_ROOT / "templates" / case["file"]).read_text(encoding="utf-8")
        facts = profile_source(source, name=case["file"]).profiles[0].facts.to_dict()
        assert {key: facts[key] for key in comparable} == {
            key: expected[case["id"]][key] for key in comparable
        }
        assert facts["repeated_shape_groups"] == expected[case["id"]]["ast_repeated_shape_groups"]


def test_profile_template_matches_fresh_and_bytecode_cache_hits(tmp_path) -> None:
    templates = {"page.kida": SOURCE}
    cache = BytecodeCache(tmp_path / "cache")

    first_env = Environment(loader=DictLoader(templates), bytecode_cache=cache)
    first = profile_template(first_env.get_template("page.kida"))
    cached_code, cached_ast, _precomputed = cache.get("page.kida", hash_source(SOURCE))
    assert cached_code is not None
    assert cached_ast is not None

    second_env = Environment(loader=DictLoader(templates), bytecode_cache=cache)
    second = profile_template(second_env.get_template("page.kida"))

    assert first == second


def test_profile_template_works_when_compiled_ast_is_not_preserved() -> None:
    env = Environment(preserve_ast=False)
    template = env.from_string(SOURCE, name="page.kida")

    report = profile_template(template)

    assert report.partial is False
    assert report.profiles[0].facts.node_count > 0


def test_profile_calls_share_no_mutable_traversal_state() -> None:
    expected = profile_source(SOURCE, name="page.kida")

    with ThreadPoolExecutor(max_workers=8) as executor:
        reports = list(
            executor.map(
                lambda _index: profile_source(SOURCE, name="page.kida"),
                range(64),
            )
        )

    assert reports == [expected] * 64


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: profile_source(42), "source must be a string"),
        (lambda: profile_source("", name=42), "name must be a string"),
        (lambda: profile_source("", name="  "), "name must not be empty"),
        (
            lambda: profile_source("", environment=object()),
            "environment must be a kida.Environment",
        ),
        (lambda: profile_template(object()), "template must be a kida.Template"),
    ],
)
def test_profile_entry_points_reject_invalid_public_inputs(call, message: str) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        call()


def test_profile_source_preserves_parser_failures() -> None:
    with pytest.raises(ParseError):
        profile_source("{% if broken %}", name="broken.kida")
