"""Block-sensitive proof for advisory Jinja ``set`` migration findings."""

from __future__ import annotations

from kida import Environment
from kida.diagnostics import DiagnosticConfidence, diagnose_source


def _warnings(source: str):
    return Environment().from_string(source, name="scope.kida").warnings


def test_fresh_if_set_read_after_block_recommends_let() -> None:
    source = "{% if enabled %}\n{% set value = 1 %}\n{% end %}\n{{ value }}"

    warning = _warnings(source)[0]
    diagnostic = diagnose_source(source, name="scope.kida").diagnostics[0]

    assert warning.code.value == diagnostic.code == "K-WARN-002"
    assert warning.lineno == diagnostic.span.start.line == 2
    assert (
        warning.suggestion
        == diagnostic.suggestion
        == ("Use {% let value = ... %} to make the value template-wide.")
    )
    assert diagnostic.confidence is DiagnosticConfidence.PROVEN
    assert diagnostic.safe_edit is None


def test_top_level_binding_read_after_if_recommends_export() -> None:
    warnings = _warnings(
        "{% set value = 0 %}\n{% if enabled %}\n{% set value = 1 %}\n{% end %}\n{{ value }}"
    )

    assert len(warnings) == 1
    assert warnings[0].lineno == 3
    assert warnings[0].suggestion == ("Use {% export value = ... %} to write to outer scope.")


def test_nested_if_assignment_is_traced_to_read_after_outer_block() -> None:
    warnings = _warnings(
        "{% if outer %}\n{% if inner %}\n{% set value = 1 %}\n{% end %}\n{% end %}\n{{ value }}"
    )

    assert len(warnings) == 1
    assert warnings[0].lineno == 3


def test_named_block_is_an_independent_jinja_scope_frame() -> None:
    warnings = _warnings(
        "{% block body %}\n{% if enabled %}\n{% set value = 1 %}\n{% end %}\n{{ value }}\n{% end %}"
    )

    assert len(warnings) == 1
    assert warnings[0].lineno == 3


def test_with_target_counts_as_a_post_block_read() -> None:
    warnings = _warnings(
        "{% if enabled %}\n"
        "{% set value = 1 %}\n"
        "{% end %}\n"
        "{% with copy = value %}\n"
        "{{ copy }}\n"
        "{% end %}"
    )

    assert len(warnings) == 1
    assert warnings[0].lineno == 2


def test_intervening_dynamic_binding_keeps_origin_ambiguous() -> None:
    warnings = _warnings(
        "{% if first %}\n"
        "{% set value = 1 %}\n"
        "{% end %}\n"
        "{% if second %}\n"
        "{% export value = 2 %}\n"
        "{% end %}\n"
        "{{ value }}"
    )

    assert warnings == []


def test_kida_only_dynamic_container_is_not_treated_as_jinja_scope() -> None:
    warnings = _warnings(
        "{% while keep_going %}\n"
        "{% if enabled %}\n"
        "{% set value = 1 %}\n"
        "{% end %}\n"
        "{{ value }}\n"
        "{% end %}"
    )

    assert warnings == []


def test_unconditional_rebinding_before_read_is_not_reported() -> None:
    warnings = _warnings(
        "{% if enabled %}\n{% set value = 1 %}\n{% end %}\n{% set value = 2 %}\n{{ value }}"
    )

    assert warnings == []


def test_sequential_write_kills_the_overwritten_origin() -> None:
    warnings = _warnings(
        "{% if enabled %}\n{% set value = 1 %}\n{% set value = 2 %}\n{% end %}\n{{ value }}"
    )

    assert [warning.lineno for warning in warnings] == [3]


def test_alternate_branch_writes_keep_distinct_origins() -> None:
    warnings = _warnings(
        "{% if first %}\n"
        "{% set value = 1 %}\n"
        "{% elif second %}\n"
        "{% set value = 2 %}\n"
        "{% end %}\n"
        "{{ value }}"
    )

    assert [warning.lineno for warning in warnings] == [2, 4]


def test_tuple_assignment_tracks_each_reaching_name() -> None:
    warnings = _warnings(
        "{% if enabled %}\n{% set first, second = pair %}\n{% end %}\n{{ first }} {{ second }}"
    )

    assert len(warnings) == 2
    assert [warning.lineno for warning in warnings] == [2, 2]
    assert {warning.suggestion for warning in warnings} == {
        "Use {% let first = ... %} to make the value template-wide.",
        "Use {% let second = ... %} to make the value template-wide.",
    }


def test_if_assignment_inside_jinja_local_loop_does_not_escape() -> None:
    warnings = _warnings(
        "{% for item in items %}\n"
        "{% if item %}\n"
        "{% set value = item %}\n"
        "{% end %}\n"
        "{% end %}\n"
        "{{ value }}"
    )

    assert warnings == []


def test_if_assignment_to_loop_target_is_reported_with_local_advice() -> None:
    warnings = _warnings(
        "{% for value in values %}\n"
        "{% if value %}\n"
        "{% set value = 2 %}\n"
        "{% end %}\n"
        "{{ value }}\n"
        "{% end %}"
    )

    assert len(warnings) == 1
    assert warnings[0].lineno == 3
    assert warnings[0].suggestion == (
        "Move the read into the same {% if %} branch or restructure the "
        "loop-local state; {% let %} and {% export %} would widen its scope."
    )


def test_nested_loop_assignment_does_not_escape_its_nearest_loop() -> None:
    warnings = _warnings(
        "{% for outer in outers %}\n"
        "{% for inner in inners %}\n"
        "{% if inner %}\n"
        "{% set value = inner %}\n"
        "{% end %}\n"
        "{% end %}\n"
        "{{ value }}\n"
        "{% end %}"
    )

    assert warnings == []


def test_if_assignment_can_flow_within_one_jinja_loop_iteration() -> None:
    warnings = _warnings(
        "{% for item in items %}\n"
        "{% set value = 1 %}\n"
        "{% if item %}\n"
        "{% set value = 2 %}\n"
        "{% end %}\n"
        "{{ value }}\n"
        "{% end %}"
    )

    assert len(warnings) == 1
    assert warnings[0].lineno == 4
    assert warnings[0].suggestion == (
        "Move the read into the same {% if %} branch or restructure the "
        "loop-local state; {% let %} and {% export %} would widen its scope."
    )


def test_existing_let_shadow_warning_remains_advisory_without_later_read() -> None:
    warnings = _warnings("{% let value = 0 %}\n{% if enabled %}\n{% set value = 1 %}\n{% end %}")

    assert len(warnings) == 1
    assert warnings[0].suggestion == ("Use {% export value = ... %} to write to outer scope.")


def test_fresh_read_analysis_respects_disabled_compatibility_policy() -> None:
    template = Environment(jinja2_compat_warnings=False).from_string(
        "{% if enabled %}{% set value = 1 %}{% end %}{{ value }}"
    )

    assert template.warnings == []
