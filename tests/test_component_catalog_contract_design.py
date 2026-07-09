"""Design-only probes for the canonical component catalog contract.

The adapter in this test is intentionally private. It proves that the proposed
v1 record can be derived from and projected back to today's ``ComponentRow``
without changing the public CLI or metadata APIs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from kida._cli.components import ComponentRow, collect_components

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "component_catalog" / "v1-design.json"


def _known(value: object, evidence: str) -> dict[str, object]:
    return {"state": "known", "value": value, "evidence": evidence}


def _unknown(reason: str, evidence: str | None = None) -> dict[str, object]:
    fact: dict[str, object] = {"state": "unknown", "reason": reason}
    if evidence is not None:
        fact["evidence"] = evidence
    return fact


def _default_fact(has_default: bool) -> dict[str, object]:
    if not has_default:
        return {"state": "absent", "evidence": "component-row.params.has_default"}
    return _unknown(
        "default-expression-not-exposed",
        "component-row.params.has_default",
    )


def _declared_type_fact(annotation: str | None) -> dict[str, object]:
    if annotation is None:
        return _unknown("type-not-declared", "component-row.params.annotation")
    return _known(annotation, "component-row.params.annotation")


def _slot_record(name: str) -> dict[str, object]:
    return {
        "fallback": _unknown("slot-fallback-not-exposed"),
        "kind": "default" if name == "default" else "named",
        "name": name,
        "origin": _unknown("slot-versus-yield-origin-not-distinguished"),
        "required": False,
        "scoped_params": _unknown("scoped-slot-params-not-exposed"),
    }


def _component_record(row: ComponentRow) -> dict[str, object]:
    props = [
        {
            "declared_type": _declared_type_fact(param["annotation"]),
            "default": _default_fact(param["has_default"]),
            "inferred_type": _unknown("type-inference-not-available"),
            "name": param["name"],
            "position": position,
            "required": param["required"],
        }
        for position, param in enumerate(row["params"])
    ]
    slot_names = (["default"] if row["has_default_slot"] else []) + sorted(row["slots"])
    component_id = f"{row['template']}#{row['name']}"
    return {
        "component_id": component_id,
        "consumes": _unknown("provide-consume-facts-not-exposed"),
        "context_dependencies": _known(
            sorted(row["depends_on"]),
            "component-row.depends_on",
        ),
        "documentation": {
            "description": _unknown("documentation-provider-not-configured"),
            "examples": _unknown("documentation-provider-not-configured"),
        },
        "extensions": {},
        "imports": _unknown("component-import-edges-not-exposed"),
        "name": row["name"],
        "props": props,
        "provides": _unknown("provide-consume-facts-not-exposed"),
        "slots": [_slot_record(name) for name in slot_names],
        "source": {
            "column": _unknown("source-column-not-exposed"),
            "line": row["lineno"],
            "path": row["template"],
        },
        "variadic": {
            "args": _known(row["vararg"], "component-row.vararg"),
            "kwargs": _known(row["kwarg"], "component-row.kwarg"),
        },
    }


def _catalog(rows: list[ComponentRow]) -> dict[str, object]:
    components = sorted(
        (_component_record(row) for row in rows),
        key=lambda component: str(component["component_id"]),
    )
    return {
        "catalog_identity": _unknown("catalog-namespace-not-provided"),
        "completeness": _unknown("legacy-collector-skips-invalid-templates"),
        "components": components,
        "contract": "kida.component-catalog",
        "contract_version": 1,
        "fixture_status": "design-only",
    }


def _legacy_row(component: dict[str, Any]) -> ComponentRow:
    props = component["props"]
    slots = component["slots"]
    source = component["source"]
    dependencies = component["context_dependencies"]
    variadic = component["variadic"]
    return {
        "name": component["name"],
        "template": source["path"],
        "lineno": source["line"],
        "params": [
            {
                "name": prop["name"],
                "annotation": (
                    prop["declared_type"]["value"]
                    if prop["declared_type"]["state"] == "known"
                    else None
                ),
                "has_default": prop["default"]["state"] != "absent",
                "required": prop["required"],
            }
            for prop in props
        ],
        "slots": [slot["name"] for slot in slots if slot["kind"] == "named"],
        "has_default_slot": any(slot["kind"] == "default" for slot in slots),
        "depends_on": dependencies["value"],
        "vararg": variadic["args"]["value"],
        "kwarg": variadic["kwargs"]["value"],
    }


def _write_templates(root: Path) -> None:
    (root / "button.html").write_text(
        "{% def button(label: str, disabled = false) %}<button>{{ label }}</button>{% end %}",
        encoding="utf-8",
    )
    (root / "card.html").write_text(
        "{% def card(title: str, subtitle = none, *items, **attrs) %}"
        "<article>{{ site.title }}{{ subtitle }}{{ items }}{{ attrs }}"
        "{% slot header let:item=title %}{{ item }}{% end %}"
        "{% slot %}</article>"
        "{% end %}",
        encoding="utf-8",
    )


def test_design_fixture_is_deterministic_and_round_trips_component_rows(tmp_path: Path) -> None:
    _write_templates(tmp_path)
    rows = collect_components(tmp_path, filter_name=None)
    catalog = _catalog(rows)
    fixture_text = FIXTURE.read_text(encoding="utf-8")
    expected = json.loads(fixture_text)

    assert catalog == expected
    assert fixture_text == json.dumps(expected, indent=2, sort_keys=True) + "\n"
    assert _catalog(list(reversed(rows))) == catalog

    components = cast("list[dict[str, Any]]", catalog["components"])
    legacy_rows = [_legacy_row(component) for component in components]
    assert legacy_rows == sorted(
        rows,
        key=lambda row: f"{row['template']}#{row['name']}",
    )


def test_unknown_evidence_is_explicit_and_null_means_known_absence(tmp_path: Path) -> None:
    _write_templates(tmp_path)
    catalog = _catalog(collect_components(tmp_path, filter_name=None))
    components = cast("list[dict[str, Any]]", catalog["components"])
    button = components[0]

    assert button["imports"]["state"] == "unknown"
    assert button["documentation"]["description"]["state"] == "unknown"
    assert button["variadic"]["args"] == {
        "state": "known",
        "value": None,
        "evidence": "component-row.vararg",
    }
