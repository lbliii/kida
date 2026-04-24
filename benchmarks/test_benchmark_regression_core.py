"""Stable Kida-only hot-path benchmarks for regression gating.

These benchmarks batch small operations so CI compares meaningful work rather
than sub-microsecond call noise. They are deliberately narrow: the broader
benchmark suite tells the product story, while this file guards the runtime and
compile hot paths that tend to regress during internal refactors.

Run with:
    pytest benchmarks/test_benchmark_regression_core.py --benchmark-only -v
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from kida import Environment, Markup, SandboxedEnvironment, SandboxPolicy, captured_render
from kida.template.helpers import safe_getattr, strict_getattr
from kida.utils.html import html_escape

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


RENDER_CALLS_PER_ROUND = 4096
HELPER_CALLS_PER_ROUND = 131_072
COMPILE_CALLS_PER_ROUND = 32

COMPILE_TEMPLATE = """\
{% for item in items %}
  {% if item.active %}
    <a href="{{ item.url }}">{{ item.title | upper }}</a>
  {% else %}
    <span>{{ item.title }}</span>
  {% end %}
{% end %}
"""


class AttrObject:
    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name


def _render_empty_batch(template: Any, iterations: int) -> int:
    total = 0
    for _ in range(iterations):
        total += len(template.render())
    return total


def _render_kwargs_batch(template: Any, iterations: int) -> int:
    total = 0
    for _ in range(iterations):
        total += len(template.render(name="Ada"))
    return total


def _render_positional_dict_batch(template: Any, iterations: int) -> int:
    total = 0
    context = {"name": "Ada"}
    for _ in range(iterations):
        total += len(template.render(context))
    return total


def _render_cached_block_batch(template: Any, iterations: int) -> int:
    total = 0
    context = {"_cached_blocks": {"content": "cached-content"}}
    for _ in range(iterations):
        total += len(template.render(context))
    return total


def _render_capture_context_batch(template: Any, iterations: int) -> int:
    total = 0
    capture_keys = frozenset({"name"})
    for _ in range(iterations):
        with captured_render(capture_context=capture_keys) as capture:
            total += len(template.render(name="Ada"))
            total += len(capture.context_keys)
    return total


def _strict_dict_hit_batch(payload: dict[str, object], iterations: int) -> int:
    total = 0
    for _ in range(iterations):
        value = strict_getattr(payload, "name")
        total += len(value) if isinstance(value, str) else 0
    return total


def _safe_dict_hit_batch(payload: dict[str, object], iterations: int) -> int:
    total = 0
    for _ in range(iterations):
        value = safe_getattr(payload, "name")
        total += len(value) if isinstance(value, str) else 0
    return total


def _strict_object_attr_hit_batch(payload: AttrObject, iterations: int) -> int:
    total = 0
    for _ in range(iterations):
        value = strict_getattr(payload, "name")
        total += len(value) if isinstance(value, str) else 0
    return total


def _html_escape_batch(value: object, iterations: int) -> int:
    total = 0
    for _ in range(iterations):
        total += len(html_escape(value))
    return total


def _compile_small_batch(iterations: int) -> int:
    env = Environment(auto_reload=False, preserve_ast=False)
    compiled = 0
    for i in range(iterations):
        template = env.from_string(COMPILE_TEMPLATE, name=f"regression-core-{i}")
        compiled += template.name is not None
    return compiled


@pytest.mark.benchmark(group="regression-core:render-call")
def test_render_empty_template_batch(benchmark: BenchmarkFixture) -> None:
    env = Environment(auto_reload=False, preserve_ast=False)
    template = env.from_string("ok", name="regression_empty")
    total = benchmark(_render_empty_batch, template, RENDER_CALLS_PER_ROUND)
    assert total == len("ok") * RENDER_CALLS_PER_ROUND


@pytest.mark.benchmark(group="regression-core:render-call")
def test_render_single_variable_kwargs_batch(benchmark: BenchmarkFixture) -> None:
    env = Environment(auto_reload=False, preserve_ast=False)
    template = env.from_string("Hello {{ name }}", name="regression_kwargs")
    total = benchmark(_render_kwargs_batch, template, RENDER_CALLS_PER_ROUND)
    assert total == len("Hello Ada") * RENDER_CALLS_PER_ROUND


@pytest.mark.benchmark(group="regression-core:render-call")
def test_render_single_variable_positional_dict_batch(benchmark: BenchmarkFixture) -> None:
    env = Environment(auto_reload=False, preserve_ast=False)
    template = env.from_string("Hello {{ name }}", name="regression_positional")
    total = benchmark(_render_positional_dict_batch, template, RENDER_CALLS_PER_ROUND)
    assert total == len("Hello Ada") * RENDER_CALLS_PER_ROUND


@pytest.mark.benchmark(group="regression-core:render-call")
def test_render_cached_block_batch(benchmark: BenchmarkFixture) -> None:
    env = Environment(auto_reload=False, preserve_ast=False)
    template = env.from_string(
        "{% block content %}default-content{% endblock %}",
        name="regression_cached_block",
    )
    total = benchmark(_render_cached_block_batch, template, RENDER_CALLS_PER_ROUND)
    assert total == len("cached-content") * RENDER_CALLS_PER_ROUND


@pytest.mark.benchmark(group="regression-core:render-call")
def test_render_capture_context_batch(benchmark: BenchmarkFixture) -> None:
    env = Environment(auto_reload=False, enable_capture=True, preserve_ast=False)
    template = env.from_string("Hello {{ name }}", name="regression_capture")
    total = benchmark(_render_capture_context_batch, template, RENDER_CALLS_PER_ROUND)
    assert total == (len("Hello Ada") + 1) * RENDER_CALLS_PER_ROUND


@pytest.mark.benchmark(group="regression-core:sandbox")
def test_sandbox_output_limit_check_batch(benchmark: BenchmarkFixture) -> None:
    env = SandboxedEnvironment(
        auto_reload=False,
        preserve_ast=False,
        sandbox_policy=SandboxPolicy(max_output_size=1024),
    )
    template = env.from_string("ok", name="regression_sandbox_limit")
    total = benchmark(_render_empty_batch, template, RENDER_CALLS_PER_ROUND)
    assert total == len("ok") * RENDER_CALLS_PER_ROUND


@pytest.mark.benchmark(group="regression-core:helpers")
def test_strict_getattr_exact_dict_hit_batch(benchmark: BenchmarkFixture) -> None:
    payload: dict[str, object] = {"name": "Ada"}
    total = benchmark(_strict_dict_hit_batch, payload, HELPER_CALLS_PER_ROUND)
    assert total == len("Ada") * HELPER_CALLS_PER_ROUND


@pytest.mark.benchmark(group="regression-core:helpers")
def test_safe_getattr_exact_dict_hit_batch(benchmark: BenchmarkFixture) -> None:
    payload: dict[str, object] = {"name": "Ada"}
    total = benchmark(_safe_dict_hit_batch, payload, HELPER_CALLS_PER_ROUND)
    assert total == len("Ada") * HELPER_CALLS_PER_ROUND


@pytest.mark.benchmark(group="regression-core:helpers")
def test_strict_getattr_object_attr_hit_batch(benchmark: BenchmarkFixture) -> None:
    payload = AttrObject("Ada")
    total = benchmark(_strict_object_attr_hit_batch, payload, HELPER_CALLS_PER_ROUND)
    assert total == len("Ada") * HELPER_CALLS_PER_ROUND


@pytest.mark.benchmark(group="regression-core:escape")
def test_html_escape_plain_string_batch(benchmark: BenchmarkFixture) -> None:
    value = "Hello World no special chars"
    total = benchmark(_html_escape_batch, value, HELPER_CALLS_PER_ROUND)
    assert total == len(value) * HELPER_CALLS_PER_ROUND


@pytest.mark.benchmark(group="regression-core:escape")
def test_html_escape_special_string_batch(benchmark: BenchmarkFixture) -> None:
    value = "<script>alert('x')</script>"
    escaped = "&lt;script&gt;alert(&#39;x&#39;)&lt;/script&gt;"
    total = benchmark(_html_escape_batch, value, HELPER_CALLS_PER_ROUND)
    assert total == len(escaped) * HELPER_CALLS_PER_ROUND


@pytest.mark.benchmark(group="regression-core:escape")
def test_html_escape_int_batch(benchmark: BenchmarkFixture) -> None:
    total = benchmark(_html_escape_batch, 12345, HELPER_CALLS_PER_ROUND)
    assert total == len("12345") * HELPER_CALLS_PER_ROUND


@pytest.mark.benchmark(group="regression-core:escape")
def test_html_escape_markup_batch(benchmark: BenchmarkFixture) -> None:
    value = Markup("<strong>safe</strong>")
    total = benchmark(_html_escape_batch, value, HELPER_CALLS_PER_ROUND)
    assert total == len(str(value)) * HELPER_CALLS_PER_ROUND


@pytest.mark.benchmark(group="regression-core:compile")
def test_compile_small_template_batch(benchmark: BenchmarkFixture) -> None:
    total = benchmark(_compile_small_batch, COMPILE_CALLS_PER_ROUND)
    assert total == COMPILE_CALLS_PER_ROUND
