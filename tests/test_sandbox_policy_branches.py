"""Behavioral proof for consequence-ranked sandbox policy branches."""

from __future__ import annotations

from collections import UserDict

import pytest

from kida import ErrorCode
from kida.sandbox import (
    DEFAULT_POLICY,
    SandboxedEnvironment,
    SandboxPolicy,
    SecurityError,
    _make_sandboxed_call,
    _make_sandboxed_getattr,
    _make_sandboxed_getattr_none,
    patch_template_namespace,
)
from kida.template.helpers import UNDEFINED


class DictSubclass(dict[str, object]):
    """Mapping subclass with an attribute fallback distinct from its keys."""

    fallback = "attribute-value"


def test_security_error_formats_optional_fields_independently() -> None:
    """Diagnostics omit absent hints and docs instead of rendering placeholders."""
    plain = SecurityError("plain")
    with_hint = SecurityError("hinted", suggestion="take action")
    with_code = SecurityError("coded", code=ErrorCode.BLOCKED_TYPE)

    assert str(plain) == "plain"
    assert str(with_hint) == "hinted\n  Hint: take action"
    assert str(with_code) == f"coded\n  Docs: {ErrorCode.BLOCKED_TYPE.docs_url}"


def test_mutating_method_policy_denies_by_default_and_allows_opt_in() -> None:
    """Mutation requires the explicit policy flag and changes caller state only then."""
    source = "{{ items.append('new') }}"
    denied_items = ["existing"]
    denied_template = SandboxedEnvironment().from_string(source)

    with pytest.raises(SecurityError) as captured:
        denied_template.render(items=denied_items)
    assert captured.value.code is ErrorCode.BLOCKED_ATTRIBUTE
    assert denied_items == ["existing"]

    allowed_items = ["existing"]
    allowed_env = SandboxedEnvironment(sandbox_policy=SandboxPolicy(allow_mutating_methods=True))
    assert allowed_env.from_string(source).render(items=allowed_items) == "None"
    assert allowed_items == ["existing", "new"]


def test_exact_dict_lookup_covers_key_attribute_and_missing_fallbacks() -> None:
    """Exact dicts preserve Kida's key-first resolution without leaking sentinels."""
    lookup = _make_sandboxed_getattr(DEFAULT_POLICY)
    optional_lookup = _make_sandboxed_getattr_none(DEFAULT_POLICY)
    value = {"present": None}

    assert lookup(None, "anything") is UNDEFINED
    assert lookup(value, "present") == ""
    assert callable(lookup(value, "items"))
    assert lookup(value, "missing") is UNDEFINED
    assert optional_lookup(value, "present") is None
    assert callable(optional_lookup(value, "items"))
    assert optional_lookup(value, "missing") is None


def test_dict_subclass_lookup_covers_key_attribute_and_missing_fallbacks() -> None:
    """Dict subclasses use ``__getitem__`` before safe attribute fallback."""
    lookup = _make_sandboxed_getattr(DEFAULT_POLICY)
    optional_lookup = _make_sandboxed_getattr_none(DEFAULT_POLICY)
    value = DictSubclass(present=None)

    assert lookup(value, "present") == ""
    assert lookup(value, "fallback") == "attribute-value"
    assert lookup(value, "missing") is UNDEFINED
    assert optional_lookup(value, "present") is None
    assert optional_lookup(value, "fallback") == "attribute-value"
    assert optional_lookup(value, "missing") is None


def test_mapping_protocol_lookup_preserves_none_and_missing_behavior() -> None:
    """Non-dict mappings follow attribute-first then mapping-key resolution."""
    lookup = _make_sandboxed_getattr(DEFAULT_POLICY)
    optional_lookup = _make_sandboxed_getattr_none(DEFAULT_POLICY)
    value: UserDict[str, object] = UserDict({"present": None})

    assert lookup(value, "data") == {"present": None}
    assert lookup(value, "present") == ""
    assert lookup(value, "missing") is UNDEFINED
    assert optional_lookup(value, "data") == {"present": None}
    assert optional_lookup(value, "present") is None
    assert optional_lookup(value, "missing") is None


def test_optional_lookup_enforces_blocked_attributes_and_types() -> None:
    """Optional access short-circuits absence, not explicit policy denials."""
    lookup = _make_sandboxed_getattr_none(DEFAULT_POLICY)

    with pytest.raises(SecurityError) as attr_error:
        lookup({}, "__class__")
    assert attr_error.value.code is ErrorCode.BLOCKED_ATTRIBUTE

    with pytest.raises(SecurityError) as type_error:
        lookup(lambda: None, "safe_name")
    assert type_error.value.code is ErrorCode.BLOCKED_TYPE


def test_allow_import_controls_the_compiled_namespace_builtins() -> None:
    """The import flag exposes only ``__import__`` and still removes direct env access."""
    denied_namespace: dict[str, object] = {"_env": object()}
    patch_template_namespace(denied_namespace, DEFAULT_POLICY)
    assert denied_namespace["__builtins__"] == {}
    assert "_env" not in denied_namespace

    allowed_namespace: dict[str, object] = {"_env": object()}
    patch_template_namespace(
        allowed_namespace,
        SandboxPolicy(allow_import=True),
    )
    assert allowed_namespace["__builtins__"] == {"__import__": __import__}
    assert "_env" not in allowed_namespace


def test_direct_call_helper_defaults_to_no_registered_trust() -> None:
    """Direct helper construction blocks Python functions without a trust provider."""
    sandboxed_call = _make_sandboxed_call(DEFAULT_POLICY)

    with pytest.raises(SecurityError) as captured:
        sandboxed_call(lambda: "unsafe")
    assert captured.value.code is ErrorCode.BLOCKED_CALLABLE
