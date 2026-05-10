"""Route-agnostic context contract checks for compiled templates."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol, cast, final


class SupportsContextAnalysis(Protocol):
    """Minimal template protocol needed by context contract checks."""

    name: str | None

    def depends_on(self) -> frozenset[str]: ...

    def list_defs(self) -> list[str]: ...

    def list_blocks(self) -> list[str]: ...


@final
@dataclass(frozen=True, slots=True)
class ContextContractIssue:
    """Machine-readable context contract finding."""

    code: Literal["K-CTX-001", "K-CTX-002"]
    severity: Literal["error", "warning"]
    path: str
    message: str
    template_name: str | None = None
    lineno: int | None = None
    col_offset: int | None = None
    suggestion: str | None = None


def _flatten_mapping(mapping: Mapping[str, Any], prefix: str = "") -> set[str]:
    """Return dotted paths available from a nested mapping contract."""
    paths: set[str] = set()
    for key, value in mapping.items():
        if not isinstance(key, str):
            continue
        path = f"{prefix}.{key}" if prefix else key
        paths.add(path)
        if isinstance(value, Mapping):
            paths.update(_flatten_mapping(value, path))
    return paths


def _normalize_paths(paths_or_mapping: Iterable[str] | Mapping[str, Any] | None) -> set[str]:
    """Normalize context contract input into dotted paths."""
    if paths_or_mapping is None:
        return set()
    if isinstance(paths_or_mapping, Mapping):
        return _flatten_mapping(cast("Mapping[str, Any]", paths_or_mapping))
    return {path for path in paths_or_mapping if path}


def check_context_contract(
    template: SupportsContextAnalysis,
    provided: Iterable[str] | Mapping[str, Any],
    *,
    optional: Iterable[str] | Mapping[str, Any] | None = None,
    globals: Iterable[str] | Mapping[str, Any] | None = None,
    check_extra: bool = False,
) -> list[ContextContractIssue]:
    """Compare template dependencies against a provided context contract.

    ``provided`` is route/framework data. ``globals`` are values guaranteed by
    the environment or adapter. Both accept dotted-path iterables or nested
    mappings. Top-level keys do not satisfy dotted paths unless the exact dotted
    path is present; use ``template.validate_context()`` for legacy top-level
    checks.
    """
    local_names = set(template.list_defs()) | set(template.list_blocks())
    required = set(template.depends_on()) - local_names
    provided_paths = _normalize_paths(provided)
    optional_paths = _normalize_paths(optional)
    global_paths = _normalize_paths(globals)
    available = provided_paths | optional_paths | global_paths

    issues: list[ContextContractIssue] = []
    for path in sorted(required - available):
        root = path.split(".", 1)[0]
        if root in global_paths:
            continue
        issues.append(
            ContextContractIssue(
                code="K-CTX-001",
                severity="error",
                path=path,
                template_name=template.name,
                message=f"Template reads context path '{path}' but the contract does not provide it.",
                suggestion=f"Add '{path}' to the route context contract or mark it optional.",
            )
        )

    if check_extra:
        for path in sorted(provided_paths - required):
            # Keep parent paths quiet when a child path is used. A nested
            # mapping that provides page.title should not warn about page.
            if any(required_path.startswith(f"{path}.") for required_path in required):
                continue
            issues.append(
                ContextContractIssue(
                    code="K-CTX-002",
                    severity="warning",
                    path=path,
                    template_name=template.name,
                    message=f"Context contract provides '{path}', but the template does not read it.",
                    suggestion="Remove unused context data or leave check_extra disabled for broad framework contexts.",
                )
            )

    return issues
