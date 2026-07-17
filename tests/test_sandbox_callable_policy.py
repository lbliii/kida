"""Regression proof for sandbox callable-policy enforcement."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from kida import DictLoader, Environment, ErrorCode
from kida.sandbox import SandboxedEnvironment, SandboxPolicy, SecurityError


class CallableValue:
    """Benign callable object used to exercise the explicit type allowlist."""

    def __call__(self, value: str = "called") -> str:
        return value


def context_function() -> str:
    """Represent an application function supplied only through render context."""
    return "context-function-ran"


async def context_async_function() -> str:
    """Represent an async application function supplied through render context."""
    return "context-async-function-ran"


async def async_text(value: str) -> str:
    """Return a value through Kida's native async render path."""
    return value


def _assert_blocked_call(invoke: Callable[[], Any]) -> SecurityError:
    with pytest.raises(SecurityError) as captured:
        invoke()

    error = captured.value
    assert error.code is ErrorCode.BLOCKED_CALLABLE
    assert error.suggestion is not None
    assert ErrorCode.BLOCKED_CALLABLE.docs_url in str(error)
    return error


def _assert_output_limited(invoke: Callable[[], Any]) -> SecurityError:
    with pytest.raises(SecurityError) as captured:
        invoke()

    error = captured.value
    assert error.code is ErrorCode.OUTPUT_LIMIT
    assert error.suggestion is not None
    assert "Reduce template output" in error.suggestion
    assert ErrorCode.OUTPUT_LIMIT.docs_url in str(error)
    return error


def test_context_function_differs_between_default_and_sandboxed_environments() -> None:
    """The ordinary environment stays permissive while the sandbox blocks functions."""
    source = "{{ callback() }}"

    assert Environment().from_string(source).render(callback=context_function) == (
        "context-function-ran"
    )

    template = SandboxedEnvironment().from_string(source)
    error = _assert_blocked_call(lambda: template.render(callback=context_function))
    assert "type 'function'" in error.message
    assert error.suggestion is not None
    assert "avoid passing callables" in error.suggestion


def test_callable_object_obeys_default_and_explicit_calling_policies() -> None:
    """Callable objects remain permitted by default and obey explicit allowlists."""
    source = "{{ callback('ok') }}"
    callback = CallableValue()

    assert SandboxedEnvironment().from_string(source).render(callback=callback) == "ok"

    deny_env = SandboxedEnvironment(sandbox_policy=SandboxPolicy(allow_calling=frozenset()))
    error = _assert_blocked_call(lambda: deny_env.from_string(source).render(callback=callback))
    assert "not permitted" in error.message
    assert error.suggestion is not None
    assert "'CallableValue'" in error.suggestion

    allow_env = SandboxedEnvironment(
        sandbox_policy=SandboxPolicy(allow_calling=frozenset({"CallableValue"}))
    )
    assert allow_env.from_string(source).render(callback=callback) == "ok"


def test_registered_global_function_is_trusted_but_context_override_is_not() -> None:
    """Trust attaches to the registered object identity, not to its context key."""

    def registered() -> str:
        return "registered"

    env = SandboxedEnvironment()
    env.add_global("callback", registered)
    template = env.from_string("{{ callback() }}")

    assert template.render() == "registered"
    _assert_blocked_call(lambda: template.render(callback=context_function))


def test_registered_global_trust_tracks_copy_on_write_updates() -> None:
    """Templates consult the current globals snapshot instead of stale identities."""

    def first() -> str:
        return "first"

    def second() -> str:
        return "second"

    env = SandboxedEnvironment()
    env.add_global("callback", first)
    template = env.from_string("{{ callback() }}")
    assert template.render() == "first"

    env.add_global("callback", second)
    assert template.render() == "second"
    _assert_blocked_call(lambda: template.render(callback=first))


def test_sandbox_builtins_and_safe_methods_remain_callable() -> None:
    """The default trusted surface keeps its documented callable behavior."""
    template = SandboxedEnvironment().from_string(
        "{{ int('7') }}:{{ name.upper() }}:{% for value in range(3) %}{{ value }}{% end %}"
    )

    assert template.render(name="kida") == "7:KIDA:012"


def test_optional_call_short_circuits_and_enforces_policy_when_present() -> None:
    """Optional calls skip absent values but route present callees through policy."""
    template = SandboxedEnvironment(strict_undefined=False).from_string("{{ target?.callback() }}")

    assert template.render(target=None) == ""
    assert template.render(target={}) == ""
    _assert_blocked_call(lambda: template.render(target={"callback": context_function}))


def test_kida_def_import_and_call_block_remain_trusted() -> None:
    """Kida-compiled callables retain parity across local and imported components."""
    env = SandboxedEnvironment(
        loader=DictLoader(
            {
                "components": ("{% def wrap(value) %}<b>{{ value }}:{% slot %}</b>{% end %}"),
                "page": (
                    '{% from "components" import wrap %}'
                    "{% def label(value) %}[{{ value }}]{% end %}"
                    "{% block content %}"
                    "{{ label('local') }}"
                    "{% call wrap('imported') %}slot{% end %}"
                    "{% endblock %}"
                ),
            }
        )
    )
    template = env.get_template("page")
    expected = "[local]<b>imported:slot</b>"

    assert template.render() == expected
    assert template.render_block("content") == expected
    assert template.render_with_blocks({}) == expected


def test_kida_compiled_function_trust_is_scoped_to_its_environment() -> None:
    """A compiled function cannot carry trust into an unrelated sandbox policy."""
    source_env = SandboxedEnvironment()
    source_template = source_env.from_string("{% def label() %}compiled{% end %}")
    context = dict(source_env.globals)
    globals_setup = source_template._namespace["_globals_setup"]
    assert callable(globals_setup)
    globals_setup(context)
    compiled_label = context["label"]
    assert callable(compiled_label)

    same_env_template = source_env.from_string("{{ callback() }}")
    assert same_env_template.render(callback=compiled_label) == "compiled"

    unrelated_template = SandboxedEnvironment().from_string("{{ callback() }}")
    _assert_blocked_call(lambda: unrelated_template.render(callback=compiled_label))


@pytest.mark.asyncio
async def test_kida_compiled_callables_are_trusted_on_async_stream_surfaces() -> None:
    """Async wrappers keep trusted Kida defs on full and fragment surfaces."""
    template = SandboxedEnvironment().from_string(
        "{% def label(value) %}[{{ value }}]{% end %}"
        "{% block content %}{{ label('trusted') }}{% endblock %}"
    )

    full = "".join([chunk async for chunk in template.render_stream_async()])
    block = "".join([chunk async for chunk in template.render_block_stream_async("content")])
    assert full == "[trusted]"
    assert block == "[trusted]"


def test_empty_call_allowlist_also_blocks_trusted_template_calls() -> None:
    """An explicit empty policy means no calls, including Kida defs and globals."""
    env = SandboxedEnvironment(sandbox_policy=SandboxPolicy(allow_calling=frozenset()))
    template = env.from_string("{% def label() %}label{% end %}{{ label() }}")

    error = _assert_blocked_call(template.render)
    assert "not permitted" in error.message


def test_context_function_is_blocked_on_every_sync_render_surface() -> None:
    """Full, fragment, override, and streaming paths share the same policy."""
    template = SandboxedEnvironment().from_string(
        "{% block content %}{{ callback() }}{% endblock %}"
    )

    invocations = (
        lambda: template.render(callback=context_function),
        lambda: template.render_block("content", callback=context_function),
        lambda: template.render_with_blocks({}, callback=context_function),
        lambda: "".join(template.render_stream(callback=context_function)),
    )

    for invoke in invocations:
        _assert_blocked_call(invoke)


@pytest.mark.asyncio
async def test_context_function_is_blocked_on_every_async_render_surface() -> None:
    """Thread-wrapped and async-stream surfaces preserve the public exception."""
    template = SandboxedEnvironment().from_string(
        "{% block content %}{{ callback() }}{% endblock %}"
    )

    with pytest.raises(SecurityError) as render_error:
        await template.render_async(callback=context_function)
    assert render_error.value.code is ErrorCode.BLOCKED_CALLABLE

    with pytest.raises(SecurityError) as stream_error:
        _ = [chunk async for chunk in template.render_stream_async(callback=context_function)]
    assert stream_error.value.code is ErrorCode.BLOCKED_CALLABLE

    with pytest.raises(SecurityError) as block_error:
        _ = [
            chunk
            async for chunk in template.render_block_stream_async(
                "content", callback=context_function
            )
        ]
    assert block_error.value.code is ErrorCode.BLOCKED_CALLABLE


@pytest.mark.asyncio
async def test_native_async_call_uses_the_same_policy_and_trust_boundary() -> None:
    """Native ``await`` calls block context functions and allow registered globals."""
    source = "{{ await callback() }}"
    blocked_template = SandboxedEnvironment().from_string(source)
    assert blocked_template.is_async is True

    with pytest.raises(SecurityError) as blocked_error:
        _ = [
            chunk
            async for chunk in blocked_template.render_stream_async(callback=context_async_function)
        ]
    assert blocked_error.value.code is ErrorCode.BLOCKED_CALLABLE

    trusted_env = SandboxedEnvironment()
    trusted_env.add_global("callback", context_async_function)
    trusted_template = trusted_env.from_string(source)
    chunks = [chunk async for chunk in trusted_template.render_stream_async()]
    assert "".join(chunks) == "context-async-function-ran"


def test_only_sandboxed_codegen_routes_calls_through_policy() -> None:
    """Ordinary Environment render code keeps direct-call code generation."""
    source = "{{ callback() }}"
    default_template = Environment().from_string(source)
    sandboxed_template = SandboxedEnvironment().from_string(source)

    assert default_template._render_func is not None
    assert sandboxed_template._render_func is not None
    assert "_sandboxed_call" not in default_template._render_func.__code__.co_names
    assert "_sandboxed_call" in sandboxed_template._render_func.__code__.co_names


def test_output_limit_is_cumulative_across_sync_render_surfaces() -> None:
    """Full, fragment, override, and streamed output share one size contract."""
    env = SandboxedEnvironment(sandbox_policy=SandboxPolicy(max_output_size=5))
    template = env.from_string("{% block content %}ab{{ value }}cd{% endblock %}")

    invocations = (
        lambda: template.render(value="XY"),
        lambda: template.render_block("content", value="XY"),
        lambda: template.render_with_blocks({}, value="XY"),
        lambda: "".join(template.render_stream(value="XY")),
    )
    for invoke in invocations:
        error = _assert_output_limited(invoke)
        assert "exceeds sandbox limit of 5" in error.message


@pytest.mark.asyncio
async def test_output_limit_is_cumulative_across_async_stream_surfaces() -> None:
    """Sync fallback and native async streams enforce the same cumulative cap."""
    env = SandboxedEnvironment(sandbox_policy=SandboxPolicy(max_output_size=5))
    sync_template = env.from_string("{% block content %}ab{{ value }}cd{% endblock %}")

    with pytest.raises(SecurityError) as sync_error:
        _ = [chunk async for chunk in sync_template.render_stream_async(value="XY")]
    assert sync_error.value.code is ErrorCode.OUTPUT_LIMIT

    native_template = env.from_string("{% block content %}ab{{ await value }}cd{% endblock %}")
    with pytest.raises(SecurityError) as native_error:
        _ = [chunk async for chunk in native_template.render_stream_async(value=async_text("XY"))]
    assert native_error.value.code is ErrorCode.OUTPUT_LIMIT

    with pytest.raises(SecurityError) as block_error:
        _ = [
            chunk
            async for chunk in native_template.render_block_stream_async(
                "content", value=async_text("XY")
            )
        ]
    assert block_error.value.code is ErrorCode.OUTPUT_LIMIT


def test_stream_output_at_limit_is_allowed() -> None:
    """The resource limit is inclusive on full and streamed surfaces."""
    env = SandboxedEnvironment(sandbox_policy=SandboxPolicy(max_output_size=6))
    template = env.from_string("ab{{ value }}cd")

    assert template.render(value="XY") == "abXYcd"
    assert "".join(template.render_stream(value="XY")) == "abXYcd"
