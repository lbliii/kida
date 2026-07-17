"""Contract and behavioral proof for opt-in extraction advice."""

from __future__ import annotations

import inspect
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
from pathlib import Path

import pytest

from kida import DictLoader, Environment, ErrorCode
from kida._diagnostic_renderers import _sarif_result, diagnostic_to_dict
from kida.analysis import advise_extraction_source, advise_extraction_template
from kida.bytecode_cache import BytecodeCache, hash_source
from kida.diagnostics import (
    DiagnosticConfidence,
    DiagnosticOptions,
    DiagnosticSeverity,
)
from kida.parser import ParseError

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "encapsulation_advisor"
REPORT_SNAPSHOT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "extraction_advice" / "report.json"
)


def _source(case_file: str) -> str:
    return (FIXTURE_ROOT / "templates" / case_file).read_text(encoding="utf-8")


def _offset(source: str, line: int, column: int) -> int:
    lines = source.splitlines(keepends=True)
    return sum(len(value) for value in lines[: line - 1]) + column


def _slice(source: str, diagnostic_index: int = 0) -> str:
    diagnostic = advise_extraction_source(source, name="case.kida").diagnostics[diagnostic_index]
    assert diagnostic.span.start is not None
    assert diagnostic.span.start.column is not None
    assert diagnostic.span.end is not None
    assert diagnostic.span.end.column is not None
    return source[
        _offset(source, diagnostic.span.start.line, diagnostic.span.start.column) : _offset(
            source, diagnostic.span.end.line, diagnostic.span.end.column
        )
    ]


def test_public_contract_is_additive_analysis_only_and_does_not_expand_check_options() -> None:
    import kida
    import kida.analysis as analysis

    expected = {"advise_extraction_source", "advise_extraction_template"}
    assert expected <= set(analysis.__all__)
    assert expected.isdisjoint(kida.__all__)
    assert str(inspect.signature(advise_extraction_source)) == (
        "(source: 'str', *, name: 'str' = '<string>', "
        "environment: 'Environment | None' = None) -> 'DiagnosticReport'"
    )
    assert str(inspect.signature(advise_extraction_template)) == (
        "(template: 'CompiledTemplate') -> 'DiagnosticReport'"
    )
    assert [field.name for field in fields(DiagnosticOptions)] == [
        "strict",
        "validate_calls",
        "a11y",
        "typed",
        "lint_fragile_paths",
    ]


def test_registered_modularity_code_has_stable_category_and_docs_url() -> None:
    code = ErrorCode.MODULARITY_EXTRACTION_CANDIDATE

    assert code.value == "K-MOD-102"
    assert code.category == "modularity"
    assert code.docs_url.endswith("/#k-mod-102")


def test_approved_corpus_emits_only_the_two_extraction_candidates() -> None:
    manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))

    for case in manifest["cases"]:
        report = advise_extraction_source(_source(case["file"]), name=case["file"])
        expected_count = 1 if case["classification"] == "extract-candidate" else 0
        assert len(report.diagnostics) == expected_count, (
            case["id"],
            case["rationale"],
            report.diagnostics,
        )


def test_iterated_candidate_has_exact_span_interface_and_explanation() -> None:
    source = _source("message_row_candidate.kida")
    diagnostic = advise_extraction_source(source, name="messages.kida").diagnostics[0]
    metadata = dict(diagnostic.metadata)

    assert _slice(source).startswith("for message in messages %}")
    assert _slice(source).endswith("endfor %}")
    assert diagnostic.span.is_exact
    assert diagnostic.severity is DiagnosticSeverity.INFO
    assert diagnostic.confidence is DiagnosticConfidence.CONSERVATIVE
    assert diagnostic.safe_edit is None
    assert metadata["candidate_kind"] == "iterated-region"
    assert json.loads(metadata["signals"]) == [
        "interactive-accessibility-structure",
        "iterated-region",
        "narrow-lexical-boundary",
        "repeated-normalized-subtree",
        "substantial-structure",
    ]
    assert json.loads(metadata["tentative_props"]) == ["current_user", "message"]
    assert json.loads(metadata["possible_slots"]) == ["actions"]
    assert json.loads(metadata["loop_local_names"]) == ["message"]
    assert json.loads(metadata["outer_names"]) == ["current_user"]
    assert "interactive elements" in diagnostic.message
    assert "human judgment" in diagnostic.notes[0]


def test_repeated_sibling_candidate_has_exact_related_location_and_varying_inputs() -> None:
    source = _source("repeated_actions_candidate.kida")
    diagnostic = advise_extraction_source(source, name="danger.kida").diagnostics[0]
    metadata = dict(diagnostic.metadata)

    assert _slice(source).startswith('<form method="post"')
    assert _slice(source).endswith("</form>")
    assert len(diagnostic.related_locations) == 1
    assert diagnostic.related_locations[0].span.is_exact
    assert json.loads(metadata["tentative_props"]) == ["account", "workspace"]
    assert json.loads(metadata["occurrence_dependencies"]) == [
        ["account.archive_url", "account.name"],
        ["workspace.delete_url", "workspace.name"],
    ]
    assert metadata["occurrence_count"] == "2"


def test_repeated_candidate_classifies_imported_calls_as_component_dependencies() -> None:
    source = """{% from "ui.kida" import icon %}
<section>
<form action="{{ account.url }}">
  <button aria-label="Archive">{{ icon(name=account.icon) }}</button>
  <p>{{ account.name }}</p>
</form>
<form action="{{ workspace.url }}">
  <button aria-label="Delete">{{ icon(name=workspace.icon) }}</button>
  <p>{{ workspace.name }}</p>
</form>
</section>
"""
    diagnostic = advise_extraction_source(source, name="actions.kida").diagnostics[0]
    metadata = dict(diagnostic.metadata)

    assert json.loads(metadata["component_dependencies"]) == ["icon"]
    assert json.loads(metadata["tentative_props"]) == ["account", "workspace"]
    assert "icon" not in json.loads(metadata["context_dependencies"])


def test_machine_diagnostic_shape_matches_golden_and_sarif_preserves_facts() -> None:
    source = _source("repeated_actions_candidate.kida")
    diagnostic = advise_extraction_source(source, name="danger.kida").diagnostics[0]
    expected_text = REPORT_SNAPSHOT.read_text(encoding="utf-8")
    expected = json.loads(expected_text)

    assert expected_text == json.dumps(expected, indent=2, sort_keys=True) + "\n"
    assert diagnostic_to_dict(diagnostic) == expected
    sarif = _sarif_result(diagnostic)
    assert sarif["ruleId"] == "K-MOD-102"
    assert sarif["level"] == "note"
    assert sarif["properties"]["metadata"] == dict(diagnostic.metadata)
    assert sarif["relatedLocations"][0]["message"]["text"] == ("Equivalent repeated sibling 2")


def test_loops_repetition_and_large_inline_layouts_are_not_sufficient_alone() -> None:
    tiny_loop = "{% for item in items %}<span>{{ item.name }}</span>{% endfor %}"
    repeated_static = (
        "<section><form><button>Save</button></form><form><button>Save</button></form></section>"
    )

    assert advise_extraction_source(tiny_loop).diagnostics == ()
    assert advise_extraction_source(repeated_static).diagnostics == ()
    assert advise_extraction_source(_source("healthy_layout.kida")).diagnostics == ()
    assert advise_extraction_source(_source("monolithic_report.kida")).diagnostics == ()


def test_existing_component_boundary_suppresses_nested_extraction_advice() -> None:
    source = _source("message_row_candidate.kida")
    body = source.split("\n", 1)[1]
    wrapped = (
        f"{{% def message_list(messages: list, current_user: dict) %}}\n{body}{{% enddef %}}\n"
    )

    assert advise_extraction_source(wrapped, name="component.kida").diagnostics == ()


def test_provide_and_consume_dependencies_are_reported_without_becoming_props() -> None:
    source = """{% template items: list, palette: dict %}
{% provide theme = palette %}
{% for item in items %}
<article id="item-{{ item.id }}">
  <header><h2>{{ item.title }}</h2></header>
  <p>{{ item.summary }}</p>
  <a href="{{ item.url }}" aria-describedby="help-{{ item.id }}">Open</a>
  {% if item.editable %}
    <button name="action" value="edit">Edit</button>
    <button name="action" value="delete">Delete</button>
  {% endif %}
  <small id="help-{{ item.id }}">{{ consume("theme") }}</small>
</article>
{% endfor %}
{% endprovide %}
"""
    diagnostic = advise_extraction_source(source, name="provided.kida").diagnostics[0]
    metadata = dict(diagnostic.metadata)

    assert json.loads(metadata["provide_consume_dependencies"]) == ["theme"]
    assert "consume" not in json.loads(metadata["tentative_props"])


def test_compiled_template_matches_fresh_and_bytecode_cache_hits(tmp_path: Path) -> None:
    source = _source("message_row_candidate.kida")
    templates = {"messages.kida": source}
    cache = BytecodeCache(tmp_path / "cache")

    first_env = Environment(loader=DictLoader(templates), bytecode_cache=cache)
    first = advise_extraction_template(first_env.get_template("messages.kida"))
    cached_code, cached_ast, _precomputed = cache.get("messages.kida", hash_source(source))
    assert cached_code is not None
    assert cached_ast is not None

    second_env = Environment(loader=DictLoader(templates), bytecode_cache=cache)
    second = advise_extraction_template(second_env.get_template("messages.kida"))

    assert first == second


def test_compiled_template_works_when_ast_is_not_preserved() -> None:
    template = Environment(preserve_ast=False).from_string(
        _source("message_row_candidate.kida"), name="messages.kida"
    )

    assert len(advise_extraction_template(template).diagnostics) == 1


def test_advice_calls_share_no_mutable_state() -> None:
    source = _source("message_row_candidate.kida")
    expected = advise_extraction_source(source, name="messages.kida")

    with ThreadPoolExecutor(max_workers=8) as executor:
        reports = list(
            executor.map(
                lambda _index: advise_extraction_source(source, name="messages.kida"),
                range(64),
            )
        )

    assert reports == [expected] * 64


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: advise_extraction_source(42), "source must be a string"),
        (lambda: advise_extraction_source("", name=42), "name must be a string"),
        (lambda: advise_extraction_source("", name="  "), "name must not be empty"),
        (
            lambda: advise_extraction_source("", environment=object()),
            "environment must be a kida.Environment",
        ),
        (
            lambda: advise_extraction_template(object()),
            "template must be a kida.Template",
        ),
    ],
)
def test_entry_points_reject_invalid_inputs(call, message: str) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        call()


def test_source_advice_preserves_parser_failures() -> None:
    with pytest.raises(ParseError):
        advise_extraction_source("{% if broken %}", name="broken.kida")
