"""Public warning-category hierarchy and filtering contracts."""

from __future__ import annotations

import warnings

import pytest

import kida
from kida import ComponentWarning, Environment, KidaWarning

INVALID_COMPONENT_CALL = (
    "{% def card(title) %}{{ title }}{% end %}{{ card(titl='wrong argument name') }}"
)


def _compile_invalid_component_call() -> None:
    Environment(validate_calls=True).from_string(INVALID_COMPONENT_CALL, name="page.html")


def test_warning_categories_are_root_exports_with_documented_hierarchy() -> None:
    assert kida.KidaWarning is KidaWarning
    assert kida.ComponentWarning is ComponentWarning
    assert issubclass(ComponentWarning, KidaWarning)


def test_component_warning_filter_can_promote_component_findings() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", KidaWarning)
        warnings.simplefilter("error", ComponentWarning)

        with pytest.raises(ComponentWarning, match="K-CMP-001"):
            _compile_invalid_component_call()


def test_kida_warning_filter_catches_component_subclass() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error", KidaWarning)

        with pytest.raises(KidaWarning, match="K-CMP-001") as exc_info:
            _compile_invalid_component_call()

    assert isinstance(exc_info.value, ComponentWarning)
