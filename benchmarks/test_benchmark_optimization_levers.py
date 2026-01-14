"""Benchmark optimization levers for large template performance.

This identifies the actual bottlenecks in large template rendering
and tests potential optimizations.

Run with: pytest benchmarks/test_benchmark_optimization_levers.py --benchmark-only -v
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

if TYPE_CHECKING:
    pass


# =============================================================================
# Test Data (same as large_context)
# =============================================================================

ITEMS = [{"id": i, "name": f"Item {i}", "data": {"x": i, "y": i * 2}} for i in range(1000)]


# =============================================================================
# Bottleneck 1: String Building Strategy
# =============================================================================


def render_list_append() -> str:
    """Current Kida approach: buf = [], buf.append(), ''.join(buf)."""
    buf: list[str] = []
    append = buf.append
    for item in ITEMS:
        append('<div id="')
        append(str(item["id"]))
        append('">')
        append(str(item["name"]))
        append(" - ")
        append(str(item["data"]["x"]))
        append("/")
        append(str(item["data"]["y"]))
        append("</div>\n")
    return "".join(buf)


def render_list_extend() -> str:
    """Alternative: extend with tuple instead of multiple appends."""
    buf: list[str] = []
    extend = buf.extend
    for item in ITEMS:
        extend(
            (
                '<div id="',
                str(item["id"]),
                '">',
                str(item["name"]),
                " - ",
                str(item["data"]["x"]),
                "/",
                str(item["data"]["y"]),
                "</div>\n",
            )
        )
    return "".join(buf)


def render_stringio() -> str:
    """Alternative: StringIO for buffering."""
    buf = io.StringIO()
    write = buf.write
    for item in ITEMS:
        write('<div id="')
        write(str(item["id"]))
        write('">')
        write(str(item["name"]))
        write(" - ")
        write(str(item["data"]["x"]))
        write("/")
        write(str(item["data"]["y"]))
        write("</div>\n")
    return buf.getvalue()


def render_fstring() -> str:
    """Alternative: f-string per iteration (creates many intermediate strings)."""
    buf: list[str] = []
    append = buf.append
    for item in ITEMS:
        append(
            f'<div id="{item["id"]}">{item["name"]} - {item["data"]["x"]}/{item["data"]["y"]}</div>\n'
        )
    return "".join(buf)


def render_fstring_direct() -> str:
    """Alternative: Single f-string join (most Pythonic but limited)."""
    return "".join(
        f'<div id="{item["id"]}">{item["name"]} - {item["data"]["x"]}/{item["data"]["y"]}</div>\n'
        for item in ITEMS
    )


@pytest.mark.benchmark(group="lever:string-building")
def test_list_append(benchmark: BenchmarkFixture) -> None:
    """Current: list + append + join."""
    result = benchmark(render_list_append)
    assert len(result) > 0


@pytest.mark.benchmark(group="lever:string-building")
def test_list_extend(benchmark: BenchmarkFixture) -> None:
    """Alternative: list + extend with tuple."""
    result = benchmark(render_list_extend)
    assert len(result) > 0


@pytest.mark.benchmark(group="lever:string-building")
def test_stringio(benchmark: BenchmarkFixture) -> None:
    """Alternative: StringIO."""
    result = benchmark(render_stringio)
    assert len(result) > 0


@pytest.mark.benchmark(group="lever:string-building")
def test_fstring_per_iteration(benchmark: BenchmarkFixture) -> None:
    """Alternative: f-string per iteration."""
    result = benchmark(render_fstring)
    assert len(result) > 0


@pytest.mark.benchmark(group="lever:string-building")
def test_fstring_generator(benchmark: BenchmarkFixture) -> None:
    """Alternative: f-string with generator join."""
    result = benchmark(render_fstring_direct)
    assert len(result) > 0


# =============================================================================
# Bottleneck 2: Escape Overhead
# =============================================================================


def escape_all(value: object) -> str:
    """Current: Always escape (str + translate)."""
    s = str(value)
    return s.translate(
        str.maketrans(
            {
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                '"': "&quot;",
                "'": "&#39;",
            }
        )
    )


_ESCAPE_TABLE = str.maketrans(
    {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
    }
)


def escape_cached_table(value: object) -> str:
    """Optimization: Pre-compiled translate table."""
    return str(value).translate(_ESCAPE_TABLE)


def escape_skip_numbers(value: object) -> str:
    """Optimization: Skip escape for int/float (safe types)."""
    if isinstance(value, (int, float)):
        return str(value)  # Numbers don't need HTML escaping
    return str(value).translate(_ESCAPE_TABLE)


def render_with_escape_all() -> str:
    """Current: Escape everything."""
    buf: list[str] = []
    append = buf.append
    e = escape_all
    for item in ITEMS:
        append('<div id="')
        append(e(item["id"]))
        append('">')
        append(e(item["name"]))
        append(" - ")
        append(e(item["data"]["x"]))
        append("/")
        append(e(item["data"]["y"]))
        append("</div>\n")
    return "".join(buf)


def render_with_escape_cached() -> str:
    """Optimization: Cached translate table."""
    buf: list[str] = []
    append = buf.append
    e = escape_cached_table
    for item in ITEMS:
        append('<div id="')
        append(e(item["id"]))
        append('">')
        append(e(item["name"]))
        append(" - ")
        append(e(item["data"]["x"]))
        append("/")
        append(e(item["data"]["y"]))
        append("</div>\n")
    return "".join(buf)


def render_with_escape_smart() -> str:
    """Optimization: Skip escape for numeric types."""
    buf: list[str] = []
    append = buf.append
    e = escape_skip_numbers
    for item in ITEMS:
        append('<div id="')
        append(e(item["id"]))
        append('">')
        append(e(item["name"]))
        append(" - ")
        append(e(item["data"]["x"]))
        append("/")
        append(e(item["data"]["y"]))
        append("</div>\n")
    return "".join(buf)


@pytest.mark.benchmark(group="lever:escaping")
def test_escape_all(benchmark: BenchmarkFixture) -> None:
    """Current: Escape all values."""
    result = benchmark(render_with_escape_all)
    assert len(result) > 0


@pytest.mark.benchmark(group="lever:escaping")
def test_escape_cached_table(benchmark: BenchmarkFixture) -> None:
    """Optimization: Cached translate table."""
    result = benchmark(render_with_escape_cached)
    assert len(result) > 0


@pytest.mark.benchmark(group="lever:escaping")
def test_escape_smart_numbers(benchmark: BenchmarkFixture) -> None:
    """Optimization: Skip escape for numeric types."""
    result = benchmark(render_with_escape_smart)
    assert len(result) > 0


# =============================================================================
# Bottleneck 3: Loop Context Overhead
# =============================================================================


class FullLoopContext:
    """Current Kida LoopContext with all features."""

    __slots__ = ("_items", "_index", "_length")

    def __init__(self, items: list) -> None:
        self._items = items
        self._length = len(items)
        self._index = 0

    def __iter__(self):
        for i, item in enumerate(self._items):
            self._index = i
            yield item

    @property
    def index(self) -> int:
        return self._index + 1

    @property
    def first(self) -> bool:
        return self._index == 0

    @property
    def last(self) -> bool:
        return self._index == self._length - 1


def render_with_loop_context() -> str:
    """Current: Full LoopContext with all properties."""
    buf: list[str] = []
    append = buf.append
    loop = FullLoopContext(ITEMS)
    for item in loop:
        append('<div id="')
        append(str(item["id"]))
        append('">')
        append(str(item["name"]))
        append("</div>\n")
    return "".join(buf)


def render_direct_iteration() -> str:
    """Optimization: Direct iteration (no LoopContext)."""
    buf: list[str] = []
    append = buf.append
    for item in ITEMS:
        append('<div id="')
        append(str(item["id"]))
        append('">')
        append(str(item["name"]))
        append("</div>\n")
    return "".join(buf)


def render_enumerate() -> str:
    """Optimization: enumerate() when index needed."""
    buf: list[str] = []
    append = buf.append
    for _i, item in enumerate(ITEMS):
        append('<div id="')
        append(str(item["id"]))
        append('">')
        append(str(item["name"]))
        append("</div>\n")
    return "".join(buf)


@pytest.mark.benchmark(group="lever:loop-context")
def test_full_loop_context(benchmark: BenchmarkFixture) -> None:
    """Current: Full LoopContext."""
    result = benchmark(render_with_loop_context)
    assert len(result) > 0


@pytest.mark.benchmark(group="lever:loop-context")
def test_direct_iteration(benchmark: BenchmarkFixture) -> None:
    """Optimization: Direct iteration."""
    result = benchmark(render_direct_iteration)
    assert len(result) > 0


@pytest.mark.benchmark(group="lever:loop-context")
def test_enumerate_iteration(benchmark: BenchmarkFixture) -> None:
    """Optimization: enumerate() for index."""
    result = benchmark(render_enumerate)
    assert len(result) > 0


# =============================================================================
# Bottleneck 4: Attribute Access
# =============================================================================


def render_dict_access() -> str:
    """Current: Dict key access."""
    buf: list[str] = []
    append = buf.append
    for item in ITEMS:
        append(str(item["data"]["x"]))
    return "".join(buf)


def render_local_cache() -> str:
    """Optimization: Cache nested dict in local variable."""
    buf: list[str] = []
    append = buf.append
    for item in ITEMS:
        data = item["data"]
        append(str(data["x"]))
    return "".join(buf)


@pytest.mark.benchmark(group="lever:attribute-access")
def test_nested_dict_access(benchmark: BenchmarkFixture) -> None:
    """Current: Nested dict access."""
    result = benchmark(render_dict_access)
    assert len(result) > 0


@pytest.mark.benchmark(group="lever:attribute-access")
def test_local_cache_access(benchmark: BenchmarkFixture) -> None:
    """Optimization: Cache in local."""
    result = benchmark(render_local_cache)
    assert len(result) > 0


# =============================================================================
# Combined: Best Optimizations Together
# =============================================================================


def render_optimized() -> str:
    """Combined optimizations: f-string + smart escape + direct iteration."""
    buf: list[str] = []
    append = buf.append
    for item in ITEMS:
        # f-string for the whole line (reduces function calls)
        # No escape needed for int fields
        name = str(item["name"]).translate(_ESCAPE_TABLE)  # Only escape strings
        append(f'<div id="{item["id"]}">{name} - {item["data"]["x"]}/{item["data"]["y"]}</div>\n')
    return "".join(buf)


def render_current_kida_style() -> str:
    """Current Kida style: list + append + escape all."""
    buf: list[str] = []
    append = buf.append
    loop = FullLoopContext(ITEMS)
    for item in loop:
        append('<div id="')
        append(str(item["id"]).translate(_ESCAPE_TABLE))
        append('">')
        append(str(item["name"]).translate(_ESCAPE_TABLE))
        append(" - ")
        append(str(item["data"]["x"]).translate(_ESCAPE_TABLE))
        append("/")
        append(str(item["data"]["y"]).translate(_ESCAPE_TABLE))
        append("</div>\n")
    return "".join(buf)


@pytest.mark.benchmark(group="lever:combined")
def test_current_kida_style(benchmark: BenchmarkFixture) -> None:
    """Current Kida rendering style."""
    result = benchmark(render_current_kida_style)
    assert len(result) > 0


@pytest.mark.benchmark(group="lever:combined")
def test_optimized_combined(benchmark: BenchmarkFixture) -> None:
    """Combined optimizations."""
    result = benchmark(render_optimized)
    assert len(result) > 0


# =============================================================================
# Bottleneck 5: F-String Coalescing (RFC: fstring-code-generation)
# =============================================================================


def render_mixed_template_non_coalesced() -> str:
    """Non-coalesced: Multiple appends per output segment."""
    buf: list[str] = []
    append = buf.append
    for item in ITEMS:
        # Non-coalesced (multiple appends)
        append('<div id="')
        append(str(item["id"]).translate(_ESCAPE_TABLE))
        append('" class="item">')
        # Control flow break
        if item["id"] % 2 == 0:
            append('<span class="even">')
        else:
            append('<span class="odd">')
        # More non-coalesced appends
        append(str(item["name"]).translate(_ESCAPE_TABLE))
        append(" - ")
        append(str(item["data"]["x"]).translate(_ESCAPE_TABLE))
        append("</span></div>\n")
    return "".join(buf)


def render_mixed_template_coalesced() -> str:
    """Coalesced: f-strings for consecutive outputs."""
    buf: list[str] = []
    append = buf.append
    for item in ITEMS:
        # Coalesced block 1
        append(f'<div id="{str(item["id"]).translate(_ESCAPE_TABLE)}" class="item">')
        # Control flow break
        if item["id"] % 2 == 0:
            append('<span class="even">')
        else:
            append('<span class="odd">')
        # Coalesced block 2
        append(
            f"{str(item['name']).translate(_ESCAPE_TABLE)} - {str(item['data']['x']).translate(_ESCAPE_TABLE)}</span></div>\n"
        )
    return "".join(buf)


def render_simple_template_non_coalesced() -> str:
    """Simple template (no control flow): non-coalesced."""
    buf: list[str] = []
    append = buf.append
    for item in ITEMS:
        append('<div id="')
        append(str(item["id"]).translate(_ESCAPE_TABLE))
        append('" class="')
        append(str(item["name"]).translate(_ESCAPE_TABLE))
        append('">')
        append(str(item["name"]).translate(_ESCAPE_TABLE))
        append("</div>\n")
    return "".join(buf)


def render_simple_template_coalesced() -> str:
    """Simple template (no control flow): fully coalesced."""
    buf: list[str] = []
    append = buf.append
    e = _ESCAPE_TABLE
    for item in ITEMS:
        # Single f-string for entire output
        append(
            f'<div id="{str(item["id"]).translate(e)}" class="{str(item["name"]).translate(e)}">{str(item["name"]).translate(e)}</div>\n'
        )
    return "".join(buf)


@pytest.mark.benchmark(group="lever:coalescing")
def test_mixed_template_non_coalesced(benchmark: BenchmarkFixture) -> None:
    """Mixed template with control flow: non-coalesced appends."""
    result = benchmark(render_mixed_template_non_coalesced)
    assert len(result) > 0


@pytest.mark.benchmark(group="lever:coalescing")
def test_mixed_template_coalesced(benchmark: BenchmarkFixture) -> None:
    """Mixed template with control flow: f-string coalesced."""
    result = benchmark(render_mixed_template_coalesced)
    assert len(result) > 0


@pytest.mark.benchmark(group="lever:coalescing")
def test_simple_template_non_coalesced(benchmark: BenchmarkFixture) -> None:
    """Simple template (no control flow): non-coalesced appends."""
    result = benchmark(render_simple_template_non_coalesced)
    assert len(result) > 0


@pytest.mark.benchmark(group="lever:coalescing")
def test_simple_template_coalesced(benchmark: BenchmarkFixture) -> None:
    """Simple template (no control flow): fully coalesced."""
    result = benchmark(render_simple_template_coalesced)
    assert len(result) > 0
