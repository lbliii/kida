"""Contract tests for AMP-backed report fixtures."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from .report_contracts import REPORT_CONTRACTS, ROOT_DIR

SCHEMAS_DIR = ROOT_DIR / "schemas" / "amp" / "v1"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _type_matches(value: object, expected: str) -> bool:
    match expected:
        case "array":
            return isinstance(value, list)
        case "boolean":
            return isinstance(value, bool)
        case "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        case "number":
            return isinstance(value, int | float) and not isinstance(value, bool)
        case "object":
            return isinstance(value, dict)
        case "string":
            return isinstance(value, str)
        case _:
            raise AssertionError(f"unsupported schema type: {expected}")


def _resolve_ref(schema: Mapping[str, Any], ref: str) -> Mapping[str, Any]:
    prefix = "#/$defs/"
    if not ref.startswith(prefix):
        raise AssertionError(f"unsupported schema ref: {ref}")
    name = ref.removeprefix(prefix)
    return schema["$defs"][name]


def _validate(
    value: Any,
    node: Mapping[str, Any],
    root_schema: Mapping[str, Any],
    path: str,
) -> list[str]:
    if "$ref" in node:
        return _validate(value, _resolve_ref(root_schema, node["$ref"]), root_schema, path)

    if "oneOf" in node:
        branch_errors = [
            _validate(value, branch, root_schema, path)
            for branch in node["oneOf"]
            if isinstance(branch, Mapping)
        ]
        matches = sum(not errors for errors in branch_errors)
        if matches == 1:
            return []
        if matches == 0:
            return [f"{path}: did not match any oneOf branch"]
        return [f"{path}: matched multiple oneOf branches"]

    errors: list[str] = []

    if "const" in node and value != node["const"]:
        errors.append(f"{path}: expected const {node['const']!r}, got {value!r}")

    if "enum" in node and value not in node["enum"]:
        errors.append(f"{path}: expected one of {node['enum']!r}, got {value!r}")

    expected_type = node.get("type")
    if isinstance(expected_type, str) and not _type_matches(value, expected_type):
        return [f"{path}: expected {expected_type}, got {type(value).__name__}"]

    if isinstance(value, dict):
        errors.extend(
            f"{path}: missing required property {key!r}"
            for key in node.get("required", [])
            if key not in value
        )

        properties = node.get("properties", {})
        if isinstance(properties, Mapping):
            for key, child_schema in properties.items():
                if key in value and isinstance(child_schema, Mapping):
                    errors.extend(_validate(value[key], child_schema, root_schema, f"{path}.{key}"))

    if isinstance(value, list) and isinstance(node.get("items"), Mapping):
        item_schema = node["items"]
        for index, item in enumerate(value):
            errors.extend(_validate(item, item_schema, root_schema, f"{path}[{index}]"))

    if "minimum" in node and isinstance(value, int | float) and value < node["minimum"]:
        errors.append(f"{path}: expected >= {node['minimum']}, got {value!r}")

    if "maximum" in node and isinstance(value, int | float) and value > node["maximum"]:
        errors.append(f"{path}: expected <= {node['maximum']}, got {value!r}")

    return errors


AMP_REPORT_CONTRACTS = [
    contract
    for contract in REPORT_CONTRACTS
    if contract.amp_schema is not None and contract.name == contract.fixture_name
]


@pytest.mark.parametrize("contract", AMP_REPORT_CONTRACTS, ids=lambda contract: contract.name)
def test_amp_report_fixture_matches_schema(contract):
    """AMP-backed report fixtures match their declared v1 schemas."""
    schema_path = SCHEMAS_DIR / f"{contract.amp_schema}.schema.json"
    schema = _load_json(schema_path)
    fixture = _load_json(contract.fixture_path)

    errors = _validate(fixture, schema, schema, "$")
    assert errors == []
