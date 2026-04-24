"""Snapshot tests for Kida's documented public contract."""

from __future__ import annotations

import inspect
import re

import pytest

import kida
from kida import Environment, ErrorCode, Template
from kida.analysis.metadata import (
    BlockMetadata,
    DefMetadata,
    DefParamInfo,
    TemplateMetadata,
    TemplateStructureManifest,
)
from kida.cli import main

EXPECTED_PUBLIC_API = {
    "module_all": [
        "AnalysisConfig",
        "AsyncLoopContext",
        "BlockMetadata",
        "ChoiceLoader",
        "CoercionWarning",
        "ComponentWarning",
        "CoverageCollector",
        "CoverageResult",
        "DefMetadata",
        "DefParamInfo",
        "DictLoader",
        "Environment",
        "ErrorCode",
        "Extension",
        "FileSystemLoader",
        "Fragment",
        "FreezeCache",
        "FreezeCacheStats",
        "FunctionLoader",
        "KidaWarning",
        "LoopContext",
        "ManifestDiff",
        "Markup",
        "MigrationWarning",
        "PackageLoader",
        "PrecedenceWarning",
        "PrefixLoader",
        "RenderAccumulator",
        "RenderCapture",
        "RenderContext",
        "RenderManifest",
        "RenderedTemplate",
        "SandboxPolicy",
        "SandboxedEnvironment",
        "SearchEntry",
        "SearchManifestBuilder",
        "SecurityError",
        "SourceSnippet",
        "Template",
        "TemplateError",
        "TemplateMetadata",
        "TemplateNotFoundError",
        "TemplateRuntimeError",
        "TemplateStructureManifest",
        "TemplateSyntaxError",
        "TemplateWarning",
        "Token",
        "TokenType",
        "UndefinedError",
        "WorkerEnvironment",
        "WorkloadProfile",
        "WorkloadType",
        "__version__",
        "async_render_context",
        "build_source_snippet",
        "captured_render",
        "default_field_extractor",
        "get_accumulator",
        "get_capture",
        "get_optimal_workers",
        "get_profile",
        "get_render_context",
        "get_render_context_required",
        "html_escape",
        "is_free_threading_enabled",
        "k",
        "plain",
        "profiled_render",
        "pure",
        "render_context",
        "should_parallelize",
        "strip_colors",
        "timed_block",
    ],
    "error_codes": {
        "UNCLOSED_TAG": "K-LEX-001",
        "UNCLOSED_COMMENT": "K-LEX-002",
        "UNCLOSED_VARIABLE": "K-LEX-003",
        "TOKEN_LIMIT": "K-LEX-004",
        "UNEXPECTED_TOKEN": "K-PAR-001",
        "UNCLOSED_BLOCK": "K-PAR-002",
        "INVALID_EXPRESSION": "K-PAR-003",
        "INVALID_FILTER": "K-PAR-004",
        "INVALID_TEST": "K-PAR-005",
        "INVALID_IDENTIFIER": "K-PAR-006",
        "UNSUPPORTED_SYNTAX": "K-PAR-007",
        "UNDEFINED_VARIABLE": "K-RUN-001",
        "FILTER_ERROR": "K-RUN-002",
        "TEST_ERROR": "K-RUN-003",
        "REQUIRED_VALUE": "K-RUN-004",
        "NONE_COMPARISON": "K-RUN-005",
        "INCLUDE_DEPTH": "K-RUN-006",
        "RUNTIME_ERROR": "K-RUN-007",
        "MACRO_NOT_FOUND": "K-RUN-008",
        "KEY_ERROR": "K-RUN-009",
        "ATTRIBUTE_ERROR": "K-RUN-010",
        "ZERO_DIVISION": "K-RUN-011",
        "TYPE_ERROR": "K-RUN-012",
        "MACRO_ITERATION": "K-RUN-013",
        "ENV_GARBAGE_COLLECTED": "K-RUN-014",
        "NOT_COMPILED": "K-RUN-015",
        "NO_LOADER": "K-RUN-016",
        "NOT_IN_RENDER_CONTEXT": "K-RUN-017",
        "TEMPLATE_NOT_FOUND": "K-TPL-001",
        "SYNTAX_ERROR": "K-TPL-002",
        "CIRCULAR_IMPORT": "K-TPL-003",
        "DEFINITION_NOT_TOPLEVEL": "K-TPL-004",
        "BLOCKED_ATTRIBUTE": "K-SEC-001",
        "BLOCKED_TYPE": "K-SEC-002",
        "RANGE_LIMIT": "K-SEC-003",
        "BLOCKED_CALLABLE": "K-SEC-004",
        "OUTPUT_LIMIT": "K-SEC-005",
        "COMPONENT_CALL_SIGNATURE": "K-CMP-001",
        "COMPONENT_TYPE_MISMATCH": "K-CMP-002",
        "FILTER_PRECEDENCE": "K-WARN-001",
        "JINJA2_SET_SCOPING": "K-WARN-002",
    },
    "environment_init": (
        "(loader: 'Loader | None' = None, "
        "autoescape: 'bool | str | Callable[[str | None], bool]' = True, "
        "auto_reload: 'bool' = True, strict_none: 'bool' = False, "
        "strict_undefined: 'bool' = True, jinja2_compat_warnings: 'bool' = True, "
        "preserve_ast: 'bool' = True, cache_size: 'int' = 400, "
        "fragment_cache_size: 'int' = 1000, fragment_ttl: 'float' = 300.0, "
        "bytecode_cache: 'BytecodeCache | bool | None' = None, "
        "template_aliases: 'dict[str, str] | None' = None, "
        "static_context: 'dict[str, Any] | None' = None, block_start: 'str' = '{%', "
        "block_end: 'str' = '%}', variable_start: 'str' = '{{', "
        "variable_end: 'str' = '}}', comment_start: 'str' = '{#', "
        "comment_end: 'str' = '#}', trim_blocks: 'bool' = False, "
        "lstrip_blocks: 'bool' = False, max_extends_depth: 'int' = 50, "
        "max_include_depth: 'int' = 50, validate_calls: 'bool' = False, "
        "enable_profiling: 'bool' = False, enable_capture: 'bool' = False, "
        "fstring_coalescing: 'bool' = True, pure_filters: 'set[str]' = <factory>, "
        "inline_components: 'bool' = False, optimize_translations: 'bool' = False, "
        "enable_htmx_helpers: 'bool' = True, extensions: 'list[type]' = <factory>, "
        "terminal_color: 'str | None' = None, terminal_width: 'int | None' = None, "
        "terminal_unicode: 'bool | None' = None, ambiguous_width: 'int | None' = None, "
        "globals: 'dict[str, Any]' = <factory>, "
        "_filters: 'dict[str, Callable[..., Any]]' = <factory>, "
        "_tests: 'dict[str, Callable[..., bool]]' = <factory>) -> None"
    ),
    "template_methods": {
        "render": "(self, *args: 'Any', **kwargs: 'Any') -> 'str'",
        "render_async": "(self, *args: 'Any', **kwargs: 'Any') -> 'str'",
        "render_stream": "(self, *args: 'Any', **kwargs: 'Any') -> 'Iterator[str]'",
        "render_stream_async": "(self, *args: 'Any', **kwargs: 'Any') -> 'AsyncIterator[str]'",
        "render_block": "(self, block_name: 'str', *args: 'Any', **kwargs: 'Any') -> 'str'",
        "render_with_blocks": (
            "(self, block_overrides: 'dict[str, str]', *args: 'Any', **kwargs: 'Any') -> 'str'"
        ),
        "render_block_stream_async": (
            "(self, block_name: 'str', *args: 'Any', **kwargs: 'Any') -> 'AsyncIterator[str]'"
        ),
        "list_blocks": "(self) -> 'list[str]'",
        "list_defs": "(self) -> 'list[str]'",
        "def_metadata": "(self) -> 'dict[str, DefMetadata]'",
        "block_metadata": "(self) -> 'dict[str, BlockMetadata]'",
        "template_metadata": "(self) -> 'TemplateMetadata | None'",
    },
    "metadata_fields": {
        "BlockMetadata": [
            "name",
            "emits_html",
            "emits_landmarks",
            "inferred_role",
            "depends_on",
            "is_pure",
            "cache_scope",
            "block_hash",
            "is_region",
            "region_params",
        ],
        "DefParamInfo": ["name", "annotation", "has_default", "is_required"],
        "DefMetadata": [
            "name",
            "template_name",
            "lineno",
            "params",
            "slots",
            "has_default_slot",
            "depends_on",
        ],
        "TemplateMetadata": ["name", "extends", "blocks", "top_level_depends_on"],
        "TemplateStructureManifest": [
            "name",
            "extends",
            "block_names",
            "block_hashes",
            "dependencies",
        ],
    },
}

EXPECTED_CLI_CONTRACT = {
    "subcommands": [
        "check",
        "components",
        "diff",
        "extract",
        "fmt",
        "manifest",
        "readme",
        "render",
    ],
    "flags": {
        "check": [
            "--a11y",
            "--help",
            "--lint-fragile-paths",
            "--strict",
            "--typed",
            "--validate-calls",
            "-h",
        ],
        "components": ["--filter", "--help", "--json", "-h"],
        "diff": ["--help", "-h"],
        "extract": ["--ext", "--help", "--output", "-h", "-o"],
        "fmt": ["--check", "--help", "--indent", "-h"],
        "manifest": ["--data", "--help", "--output", "--search", "-h", "-o"],
        "readme": [
            "--depth",
            "--help",
            "--json",
            "--output",
            "--preset",
            "--set",
            "--template",
            "-h",
            "-o",
        ],
        "render": [
            "--color",
            "--data",
            "--data-format",
            "--data-str",
            "--explain",
            "--help",
            "--mode",
            "--set",
            "--stream",
            "--stream-delay",
            "--width",
            "-h",
        ],
    },
}


def _public_api_snapshot() -> dict[str, object]:
    metadata_classes = [
        BlockMetadata,
        DefParamInfo,
        DefMetadata,
        TemplateMetadata,
        TemplateStructureManifest,
    ]
    template_methods = [
        "render",
        "render_async",
        "render_stream",
        "render_stream_async",
        "render_block",
        "render_with_blocks",
        "render_block_stream_async",
        "list_blocks",
        "list_defs",
        "def_metadata",
        "block_metadata",
        "template_metadata",
    ]
    return {
        "module_all": sorted(kida.__all__),
        "error_codes": {code.name: code.value for code in ErrorCode},
        "environment_init": str(inspect.signature(Environment)),
        "template_methods": {
            name: str(inspect.signature(getattr(Template, name))) for name in template_methods
        },
        "metadata_fields": {
            cls.__name__: list(cls.__dataclass_fields__) for cls in metadata_classes
        },
    }


def _help_text(capsys: pytest.CaptureFixture[str], *args: str) -> str:
    with pytest.raises(SystemExit) as exc_info:
        main([*args, "--help"])
    assert exc_info.value.code == 0
    return capsys.readouterr().out


def _cli_contract(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    root_help = _help_text(capsys)
    subcommands_match = re.search(r"\{([^}]+)\}", root_help)
    assert subcommands_match is not None
    subcommands = sorted(subcommands_match.group(1).split(","))

    flag_pattern = re.compile(r"(?<!\w)(-{1,2}[A-Za-z][A-Za-z0-9-]*)")
    return {
        "subcommands": subcommands,
        "flags": {
            command: sorted(set(flag_pattern.findall(_help_text(capsys, command))))
            for command in subcommands
        },
    }


def test_public_api_snapshot() -> None:
    assert _public_api_snapshot() == EXPECTED_PUBLIC_API


def test_cli_subcommands_and_flags_snapshot(capsys: pytest.CaptureFixture[str]) -> None:
    assert _cli_contract(capsys) == EXPECTED_CLI_CONTRACT
