"""Source/cache parity for compiler and component warning contracts."""

from __future__ import annotations

import asyncio
import inspect
import struct
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from kida import (
    ComponentWarning,
    DictLoader,
    Environment,
    ErrorCode,
    MigrationWarning,
    PrecedenceWarning,
    Template,
)
from kida.bytecode_cache import _FRAMED_MAGIC_V4, BytecodeCache, hash_source
from kida.environment.core import _hash_compile_context

COMPILER_WARNING_SOURCE = """{% let value = 1 %}
{% if true %}{% set value = 2 %}{% end %}
{{ item ?? fallback | upper }}
"""


def _compile_once(
    cache: BytecodeCache,
    source: str,
    *,
    preserve_ast: bool = True,
    jinja2_compat_warnings: bool = True,
) -> tuple[Template, list[warnings.WarningMessage]]:
    environment = Environment(
        bytecode_cache=cache,
        preserve_ast=preserve_ast,
        jinja2_compat_warnings=jinja2_compat_warnings,
    )
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        template = environment.from_string(source, name="warning.html")
    return template, emitted


def _warning_facts(template: Template) -> list[tuple[object, ...]]:
    return [
        (
            warning.code,
            warning.message,
            warning.template_name,
            warning.lineno,
            warning.suggestion,
        )
        for warning in template.warnings
    ]


@pytest.mark.parametrize("preserve_ast", [False, True])
def test_compiler_warning_fields_order_and_python_emission_match_cache_hits(
    tmp_path: Path,
    preserve_ast: bool,
) -> None:
    cache = BytecodeCache(tmp_path / "cache")

    source_template, source_emitted = _compile_once(
        cache, COMPILER_WARNING_SOURCE, preserve_ast=preserve_ast
    )
    cached_template, cached_emitted = _compile_once(
        cache, COMPILER_WARNING_SOURCE, preserve_ast=preserve_ast
    )

    assert _warning_facts(cached_template) == _warning_facts(source_template)
    assert [fact[0] for fact in _warning_facts(cached_template)] == [
        ErrorCode.JINJA2_SET_SCOPING,
        ErrorCode.FILTER_PRECEDENCE,
    ]
    assert [item.category for item in cached_emitted] == [
        MigrationWarning,
        PrecedenceWarning,
    ]
    assert [str(item.message) for item in cached_emitted] == [
        str(item.message) for item in source_emitted
    ]
    assert cached_template.render(item=None, fallback="ok") == source_template.render(
        item=None, fallback="ok"
    )
    assert "".join(cached_template.render_stream(item=None, fallback="ok")) == "".join(
        source_template.render_stream(item=None, fallback="ok")
    )
    assert asyncio.run(cached_template.render_async(item=None, fallback="ok")) == asyncio.run(
        source_template.render_async(item=None, fallback="ok")
    )


@pytest.mark.parametrize("preserve_ast", [False, True])
def test_local_component_validation_warning_matches_cache_hits(
    tmp_path: Path,
    preserve_ast: bool,
) -> None:
    source = "{% def card(title) %}{{ title }}{% end %}{{ card(titl='wrong argument name') }}"
    cache = BytecodeCache(tmp_path / "cache")

    def compile_once() -> tuple[Template, list[warnings.WarningMessage]]:
        environment = Environment(
            bytecode_cache=cache,
            preserve_ast=preserve_ast,
            validate_calls=True,
        )
        with warnings.catch_warnings(record=True) as emitted:
            warnings.simplefilter("always")
            template = environment.from_string(source, name="component.html")
        return template, emitted

    source_template, source_emitted = compile_once()
    cached_template, cached_emitted = compile_once()

    assert _warning_facts(cached_template) == _warning_facts(source_template)
    assert [warning.code for warning in cached_template.warnings] == [
        ErrorCode.COMPONENT_CALL_SIGNATURE
    ]
    assert [item.category for item in source_emitted] == [ComponentWarning]
    assert [item.category for item in cached_emitted] == [ComponentWarning]


def test_imported_component_warnings_are_recomputed_from_current_signatures(
    tmp_path: Path,
) -> None:
    cache_dir = tmp_path / "cache"
    cache = BytecodeCache(cache_dir)
    page = '{% from "components.html" import card %}{{ card(titl="value") }}'

    def compile_with(component_source: str) -> Template:
        environment = Environment(
            loader=DictLoader(
                {
                    "components.html": component_source,
                    "page.html": page,
                }
            ),
            bytecode_cache=cache,
            preserve_ast=True,
            validate_calls=True,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return environment.get_template("page.html")

    invalid = compile_with("{% def card(title) %}{{ title }}{% end %}")
    page_artifact = next(cache_dir.glob("*page.html*"))
    artifact_before = page_artifact.read_bytes()

    valid = compile_with("{% def card(titl) %}{{ titl }}{% end %}")

    assert [warning.code for warning in invalid.warnings] == [ErrorCode.COMPONENT_CALL_SIGNATURE]
    assert valid.warnings == []
    assert page_artifact.read_bytes() == artifact_before


def test_warning_configuration_participates_in_the_cache_key(tmp_path: Path) -> None:
    cache = BytecodeCache(tmp_path / "cache")
    source = "{% let value = 1 %}{% if true %}{% set value = 2 %}{% end %}"

    enabled, _enabled_emitted = _compile_once(cache, source, jinja2_compat_warnings=True)
    disabled, disabled_emitted = _compile_once(cache, source, jinja2_compat_warnings=False)

    assert [warning.code for warning in enabled.warnings] == [ErrorCode.JINJA2_SET_SCOPING]
    assert disabled.warnings == []
    assert disabled_emitted == []
    assert cache.stats()["file_count"] == 2


def test_corrupt_warning_metadata_is_a_miss_and_is_replaced(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache = BytecodeCache(cache_dir)
    source_template, _emitted = _compile_once(cache, COMPILER_WARNING_SOURCE)
    artifact_path = next(cache_dir.glob("*.pyc"))
    data = bytearray(artifact_path.read_bytes())
    assert data.startswith(_FRAMED_MAGIC_V4)

    offset = len(_FRAMED_MAGIC_V4)
    (code_len,) = struct.unpack_from("<I", data, offset)
    offset += 4 + code_len
    (precomputed_len,) = struct.unpack_from("<I", data, offset)
    offset += 4 + precomputed_len
    (warning_len,) = struct.unpack_from("<I", data, offset)
    offset += 4
    data[offset : offset + warning_len] = b"!" * warning_len
    artifact_path.write_bytes(data)
    corrupted = artifact_path.read_bytes()

    repaired_template, repaired_emitted = _compile_once(cache, COMPILER_WARNING_SOURCE)

    assert _warning_facts(repaired_template) == _warning_facts(source_template)
    assert [item.category for item in repaired_emitted] == [
        MigrationWarning,
        PrecedenceWarning,
    ]
    assert artifact_path.read_bytes() != corrupted
    repaired_artifact = cache._get_artifact(
        "warning.html",
        hash_source(COMPILER_WARNING_SOURCE),
        context_hash=_hash_compile_context(None, jinja2_compat_warnings=True),
    )
    assert repaired_artifact is not None
    assert list(repaired_artifact.compiler_warnings or ()) == repaired_template.warnings


def test_public_cache_signatures_and_three_value_result_remain_unchanged(
    tmp_path: Path,
) -> None:
    cache = BytecodeCache(tmp_path / "cache")
    code = compile("value = 1", "<cache>", "exec")
    source_hash = hash_source("value = 1")

    assert str(inspect.signature(BytecodeCache.get)) == (
        "(self, name: 'str', source_hash: 'str', *, context_hash: 'str | None' = None) "
        "-> 'tuple[CodeType, Node | None, list | None] | tuple[None, None, None]'"
    )
    assert str(inspect.signature(BytecodeCache.set)) == (
        "(self, name: 'str', source_hash: 'str', code: 'CodeType', *, "
        "context_hash: 'str | None' = None, ast: 'Node | None' = None, "
        "precomputed: 'list | None' = None) -> 'None'"
    )

    cache.set("direct.html", source_hash, code)
    result = cache.get("direct.html", source_hash)
    assert len(result) == 3
    assert result[0] is not None


def test_concurrent_cache_hits_return_complete_warning_records(tmp_path: Path) -> None:
    cache = BytecodeCache(tmp_path / "cache")
    expected, _emitted = _compile_once(cache, COMPILER_WARNING_SOURCE)
    expected_facts = _warning_facts(expected)

    def load(_index: int) -> list[tuple[object, ...]]:
        environment = Environment(bytecode_cache=cache)
        template = environment.from_string(
            COMPILER_WARNING_SOURCE,
            name="warning.html",
        )
        return _warning_facts(template)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with ThreadPoolExecutor(max_workers=16) as executor:
            results = list(executor.map(load, range(128)))

    assert results == [expected_facts] * 128
