"""Contract and behavioral proof for multi-root encapsulation advice."""

from __future__ import annotations

import inspect
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from kida import Environment, ErrorCode, FileSystemLoader, PrefixLoader
from kida._diagnostic_renderers import _sarif_result, diagnostic_to_dict
from kida.analysis import AdviceContext, profile_source
from kida.bytecode_cache import BytecodeCache
from kida.diagnostics import (
    DiagnosticConfidence,
    DiagnosticOptions,
    DiagnosticSeverity,
    SourceSpan,
)
from kida.inspection import (
    TemplateRoot,
    advise_encapsulation_roots,
    diagnose_roots,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "flattening_advice"
REPORT_SNAPSHOT = FIXTURE_ROOT / "report.json"
EXTRACTION_ROOT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "encapsulation_advisor" / "templates"
)


def _roots(*, reversed_order: bool = False) -> tuple[TemplateRoot, ...]:
    roots = (
        TemplateRoot("app", FIXTURE_ROOT / "app"),
        TemplateRoot("adapter", FIXTURE_ROOT / "adapter"),
    )
    return tuple(reversed(roots)) if reversed_order else roots


def _flatten_diagnostics():
    return tuple(
        diagnostic
        for diagnostic in advise_encapsulation_roots(_roots()).diagnostics
        if diagnostic.code == "K-MOD-103"
    )


def test_public_contract_is_opt_in_multi_root_and_does_not_expand_check_options() -> None:
    import kida
    import kida.inspection as inspection_module

    assert "advise_encapsulation_roots" in inspection_module.__all__
    assert "advise_encapsulation_roots" not in kida.__all__
    assert str(inspect.signature(advise_encapsulation_roots)) == (
        "(roots: 'Iterable[TemplateRoot]', *, environment: 'Environment | None' = None, "
        "context: 'Iterable[AdviceContext]' = ()) -> 'DiagnosticReport'"
    )
    assert list(DiagnosticOptions.__dataclass_fields__) == [
        "strict",
        "validate_calls",
        "a11y",
        "typed",
        "lint_fragile_paths",
    ]


def test_registered_pass_through_code_has_stable_contract() -> None:
    code = ErrorCode.MODULARITY_PASS_THROUGH_COMPONENT

    assert code.value == "K-MOD-103"
    assert code.category == "modularity"
    assert code.docs_url.endswith("/#k-mod-103")


def test_exact_pass_through_props_and_slot_wrappers_are_the_only_candidates() -> None:
    diagnostics = _flatten_diagnostics()

    assert [dict(diagnostic.metadata)["component_name"] for diagnostic in diagnostics] == [
        "app_button",
        "app_panel",
    ]
    assert all(diagnostic.span.is_exact for diagnostic in diagnostics)
    assert all(diagnostic.severity is DiagnosticSeverity.INFO for diagnostic in diagnostics)
    assert all(
        diagnostic.confidence is DiagnosticConfidence.CONSERVATIVE for diagnostic in diagnostics
    )
    assert all(diagnostic.safe_edit is None for diagnostic in diagnostics)


def test_prop_wrapper_reports_reproducible_evidence_and_action() -> None:
    diagnostic = _flatten_diagnostics()[0]
    metadata = dict(diagnostic.metadata)

    assert diagnostic.span.path == "app/components.kida"
    assert diagnostic.title == "Pass-through component"
    assert diagnostic.kind == "flatten-candidate"
    assert "one same-owner caller" in diagnostic.message
    assert "calling 'button' directly" in diagnostic.suggestion
    assert [location.label for location in diagnostic.related_locations] == [
        "Only same-owner caller",
        "Forwarded component",
    ]
    assert metadata["candidate_kind"] == "pass-through-component"
    assert metadata["downstream_component"] == "button"
    assert json.loads(metadata["forwarded_props"]) == ["disabled", "label"]
    assert json.loads(metadata["forwarded_slots"]) == []
    assert json.loads(metadata["signals"]) == [
        "exact-interface-forwarding",
        "no-owned-markup-or-behavior",
        "same-owner-downstream",
        "single-downstream-component",
        "single-same-owner-caller",
    ]
    assert metadata["interface_match"] == "exact"
    assert metadata["owner"] == "app"


def test_slot_wrapper_reports_the_forwarded_default_slot() -> None:
    diagnostic = _flatten_diagnostics()[1]
    metadata = dict(diagnostic.metadata)

    assert metadata["component_name"] == "app_panel"
    assert metadata["downstream_component"] == "panel"
    assert json.loads(metadata["forwarded_props"]) == ["title"]
    assert json.loads(metadata["forwarded_slots"]) == ["default"]
    assert "single-slot-forwarding" in json.loads(metadata["signals"])


def test_guardrail_fixtures_suppress_reuse_policy_public_and_adapter_boundaries() -> None:
    names = {dict(diagnostic.metadata)["component_name"] for diagnostic in _flatten_diagnostics()}

    assert names.isdisjoint(
        {
            "adapter_shell",
            "app_adapter_shell",
            "labeled_field",
            "project_summary",
            "public_button",
            "shared_button",
        }
    )


def test_root_order_and_concurrent_calls_are_deterministic() -> None:
    expected = advise_encapsulation_roots(_roots())

    assert advise_encapsulation_roots(_roots(reversed_order=True)) == expected
    with ThreadPoolExecutor(max_workers=8) as executor:
        reports = list(executor.map(lambda _index: advise_encapsulation_roots(_roots()), range(32)))

    assert reports == [expected] * 32


def test_fresh_and_bytecode_cache_hit_reports_match(tmp_path: Path) -> None:
    cache = BytecodeCache(tmp_path / "cache")
    loaders = {
        "app": FileSystemLoader(FIXTURE_ROOT / "app"),
        "adapter": FileSystemLoader(FIXTURE_ROOT / "adapter"),
    }
    first_environment = Environment(
        loader=PrefixLoader(loaders),
        bytecode_cache=cache,
    )
    first = advise_encapsulation_roots(_roots(), environment=first_environment)
    second_environment = Environment(
        loader=PrefixLoader(loaders),
        bytecode_cache=cache,
    )
    second = advise_encapsulation_roots(_roots(), environment=second_environment)

    assert first == second


def test_default_check_remains_non_failing_and_advice_is_separate() -> None:
    check = diagnose_roots(_roots(), options=DiagnosticOptions(validate_calls=True))
    advice = advise_encapsulation_roots(_roots())

    assert check.diagnostics == ()
    assert check.partial is False
    assert len(_flatten_diagnostics()) == 2
    assert advice.partial is False


def test_multi_root_report_preserves_existing_extraction_advice() -> None:
    report = advise_encapsulation_roots((TemplateRoot("app", EXTRACTION_ROOT),))

    assert [diagnostic.code for diagnostic in report.diagnostics] == [
        "K-MOD-102",
        "K-MOD-102",
    ]


def test_loader_cannot_silently_change_advice_ownership(tmp_path: Path) -> None:
    expected = tmp_path / "expected"
    other = tmp_path / "other"
    expected.mkdir()
    other.mkdir()
    (expected / "component.kida").write_text(
        "{% def expected() %}expected{% end %}",
        encoding="utf-8",
    )
    (other / "component.kida").write_text(
        "{% def other() %}other{% end %}",
        encoding="utf-8",
    )
    environment = Environment(
        loader=PrefixLoader({"app": FileSystemLoader(other)}),
        bytecode_cache=False,
    )

    report = advise_encapsulation_roots(
        (TemplateRoot("app", expected),),
        environment=environment,
    )

    assert report.partial is True
    assert [diagnostic.code for diagnostic in report.diagnostics] == ["K-TPL-005"]
    assert dict(report.diagnostics[0].metadata)["owner"] == "app"


def test_relative_module_imports_resolve_into_the_owned_call_graph(tmp_path: Path) -> None:
    root = tmp_path / "app"
    root.mkdir()
    (root / "base.kida").write_text(
        '{% def button(label: str) %}<button type="button">{{ label }}</button>{% end %}',
        encoding="utf-8",
    )
    (root / "wrapper.kida").write_text(
        '{% import "./base.kida" as ui %}'
        "{% def app_button(label: str) %}{{ ui.button(label=label) }}{% end %}",
        encoding="utf-8",
    )
    (root / "page.kida").write_text(
        '{% from "./wrapper.kida" import app_button %}{{ app_button(label="Save") }}',
        encoding="utf-8",
    )

    report = advise_encapsulation_roots((TemplateRoot("app", root),))

    assert [diagnostic.code for diagnostic in report.diagnostics] == ["K-MOD-103"]
    assert dict(report.diagnostics[0].metadata)["downstream_component"] == "button"


def test_json_and_sarif_preserve_flattening_facts() -> None:
    diagnostic = _flatten_diagnostics()[0]
    payload = diagnostic_to_dict(diagnostic)
    payload["metadata"]["source_path"] = "<fixture>/app/components.kida"
    expected_text = REPORT_SNAPSHOT.read_text(encoding="utf-8")
    expected = json.loads(expected_text)
    sarif = _sarif_result(diagnostic)

    assert expected_text == json.dumps(expected, indent=2, sort_keys=True) + "\n"
    assert payload == expected
    assert sarif["ruleId"] == "K-MOD-103"
    assert sarif["level"] == "note"
    assert sarif["properties"]["metadata"] == dict(diagnostic.metadata)
    assert [location["message"]["text"] for location in sarif["relatedLocations"]] == [
        "Only same-owner caller",
        "Forwarded component",
    ]


@pytest.mark.parametrize(
    ("roots", "message"),
    [
        (object(), "roots must be an iterable"),
        ((object(),), "roots must contain only TemplateRoot"),
    ],
)
def test_entry_point_rejects_invalid_roots(roots, message: str) -> None:
    with pytest.raises(TypeError, match=message):
        advise_encapsulation_roots(roots)


def test_entry_point_rejects_invalid_environment() -> None:
    with pytest.raises(TypeError, match=r"environment must be a kida\.Environment"):
        advise_encapsulation_roots(_roots(), environment=object())


def test_adapter_context_preserves_response_block_and_exposes_nested_candidate(
    tmp_path: Path,
) -> None:
    candidate = (EXTRACTION_ROOT / "message_row_candidate.kida").read_text(encoding="utf-8")
    body = candidate.split("\n", 1)[1]
    source = f'{{% block updates transport="oob" %}}\n{body}{{% endblock %}}\n'
    root = tmp_path / "app"
    root.mkdir()
    (root / "page.kida").write_text(source, encoding="utf-8")
    profile = profile_source(source, name="app/page.kida")
    block = next(item for item in profile.profiles if item.kind == "block")
    context = AdviceContext(
        block.span,
        (
            ("consumer_context", "iterated"),
            ("preserve_boundary", True),
            ("response_boundary", True),
            ("role", "oob-response"),
        ),
    )

    without_adapter = advise_encapsulation_roots((TemplateRoot("app", root),))
    with_adapter = advise_encapsulation_roots(
        (TemplateRoot("app", root),),
        context=(context,),
    )

    assert without_adapter.diagnostics == ()
    assert [diagnostic.code for diagnostic in with_adapter.diagnostics] == ["K-MOD-102"]
    diagnostic = with_adapter.diagnostics[0]
    assert diagnostic.span.path == "app/page.kida"
    assert diagnostic.span != block.span
    assert "preserves the outer boundary" in diagnostic.notes[-1]
    payload = json.loads(dict(diagnostic.metadata)["advice_context"])
    assert payload[0]["facts"] == {
        "consumer_context": "iterated",
        "preserve_boundary": True,
        "response_boundary": True,
        "role": "oob-response",
    }


def test_unknown_context_facts_degrade_to_no_adapter_result(tmp_path: Path) -> None:
    root = tmp_path / "app"
    root.mkdir()
    source = "{% def card() %}<article>Card</article>{% end %}"
    (root / "page.kida").write_text(source, encoding="utf-8")
    span = profile_source(source, name="app/page.kida").profiles[0].span
    unknown = AdviceContext(span, (("chirp.swap_mode", "oob"),))

    assert advise_encapsulation_roots(
        (TemplateRoot("app", root),),
        context=(unknown,),
    ) == advise_encapsulation_roots((TemplateRoot("app", root),))

    unrecognized_value = AdviceContext(span, (("consumer_context", "streamed"),))
    assert advise_encapsulation_roots(
        (TemplateRoot("app", root),),
        context=(unrecognized_value,),
    ) == advise_encapsulation_roots((TemplateRoot("app", root),))


def test_visibility_context_suppresses_exact_flatten_candidate() -> None:
    source = (FIXTURE_ROOT / "app" / "components.kida").read_text(encoding="utf-8")
    profile = profile_source(source, name="app/components.kida")
    app_button = next(
        item for item in profile.profiles if item.kind == "definition" and item.name == "app_button"
    )
    context = AdviceContext(app_button.span, (("visibility", "public"),))

    report = advise_encapsulation_roots(_roots(), context=(context,))

    assert [
        dict(diagnostic.metadata)["component_name"]
        for diagnostic in report.diagnostics
        if diagnostic.code == "K-MOD-103"
    ] == ["app_panel"]


def test_advice_context_is_canonical_immutable_and_rejects_bad_facts() -> None:
    span = profile_source("<p>x</p>", name="app/page.kida").profiles[0].span
    context = AdviceContext(span, (("role", "page"), ("preserve_boundary", True)))

    assert context.facts == (("preserve_boundary", True), ("role", "page"))
    with pytest.raises(TypeError, match="span must be a SourceSpan"):
        AdviceContext(object(), ())
    with pytest.raises(ValueError, match="exact SourceSpan"):
        AdviceContext(SourceSpan(path="app/page.kida"), ())
    with pytest.raises(TypeError, match="tuple of pairs"):
        AdviceContext(span, [])
    with pytest.raises(TypeError, match=r"\(name, scalar\) pairs"):
        AdviceContext(span, ("role", "page"))
    with pytest.raises(ValueError, match="non-empty strings"):
        AdviceContext(span, (("", "page"),))
    with pytest.raises(ValueError, match="duplicate advice context fact"):
        AdviceContext(span, (("role", "page"), ("role", "route")))
    with pytest.raises(TypeError, match="literal scalars"):
        AdviceContext(span, (("role", []),))
    with pytest.raises(ValueError, match="finite"):
        AdviceContext(span, (("weight", float("nan")),))


@pytest.mark.parametrize("context", [object(), (object(),)])
def test_entry_point_rejects_invalid_adapter_context(context: object) -> None:
    with pytest.raises(TypeError, match=r"iterable of AdviceContext|only AdviceContext"):
        advise_encapsulation_roots(_roots(), context=context)


def test_adapter_context_order_is_deterministic() -> None:
    source = (FIXTURE_ROOT / "app" / "components.kida").read_text(encoding="utf-8")
    profile = profile_source(source, name="app/components.kida")
    definitions = tuple(item for item in profile.profiles if item.kind == "definition")
    contexts = tuple(AdviceContext(item.span, (("role", item.name),)) for item in definitions)

    assert advise_encapsulation_roots(_roots(), context=contexts) == advise_encapsulation_roots(
        _roots(),
        context=reversed(contexts),
    )
