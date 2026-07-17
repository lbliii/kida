"""Explicit multi-root template inspection for tools and adapters.

The root inventory is filesystem-backed and namespaced by construction. Runtime
loader precedence remains a separate concern: inspection never infers ownership
from an unprefixed ``ChoiceLoader``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast, final

from kida.diagnostics import (
    Diagnostic,
    DiagnosticConfidence,
    DiagnosticOptions,
    DiagnosticReport,
    DiagnosticSeverity,
    SourceSpan,
)
from kida.exceptions import ErrorCode

if TYPE_CHECKING:
    from kida.analysis import DefMetadata
    from kida.environment import Environment
    from kida.environment.loaders import (
        ChoiceLoader,
        DictLoader,
        FileSystemLoader,
        FunctionLoader,
        PackageLoader,
        PrefixLoader,
    )

_NAMESPACE_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_TEMPLATE_GLOBS = ("*.html", "*.kida")
_DEFAULT_OPTIONS = DiagnosticOptions()


@final
@dataclass(frozen=True, slots=True)
class TemplateRoot:
    """One explicitly owned filesystem root for directory-wide inspection."""

    namespace: str
    path: Path

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str):
            raise TypeError("template root namespace must be a string")
        if not _NAMESPACE_RE.fullmatch(self.namespace) or self.namespace in {".", ".."}:
            raise ValueError(
                "template root namespace must be one non-empty path segment "
                "containing only letters, digits, '_' or '-'"
            )
        if not isinstance(self.path, Path):
            object.__setattr__(self, "path", Path(self.path))


@final
@dataclass(frozen=True, slots=True)
class ComponentRecord:
    """One component definition with stable root ownership and source facts."""

    owner: str
    template: str
    source_path: str
    metadata: DefMetadata


@final
@dataclass(frozen=True, slots=True)
class ComponentInspection:
    """Policy-neutral result of inspecting components across explicit roots."""

    components: tuple[ComponentRecord, ...]
    diagnostics: tuple[Diagnostic, ...] = ()
    partial: bool = False


@final
@dataclass(frozen=True, slots=True)
class _TemplateEntry:
    owner: str
    name: str
    source_path: Path


@final
@dataclass(frozen=True, slots=True)
class _RootInventory:
    roots: tuple[TemplateRoot, ...]
    entries: tuple[_TemplateEntry, ...]
    diagnostics: tuple[Diagnostic, ...]

    @property
    def partial(self) -> bool:
        return bool(self.diagnostics)


def _configuration_diagnostic(
    message: str,
    *,
    namespace: str | None = None,
    source_path: str | None = None,
    suggestion: str,
) -> Diagnostic:
    code = ErrorCode.TEMPLATE_ROOT_CONFIGURATION
    metadata = tuple(
        (key, value)
        for key, value in (("owner", namespace), ("source_path", source_path))
        if value is not None
    )
    return Diagnostic(
        code=code.value,
        category=code.category,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        span=SourceSpan(path=source_path),
        title="Invalid template root",
        kind="template-root-configuration",
        suggestion=suggestion,
        confidence=DiagnosticConfidence.PROVEN,
        documentation_url=code.docs_url,
        metadata=metadata,
    )


def _build_inventory(roots: Iterable[TemplateRoot]) -> _RootInventory:
    if not isinstance(roots, Iterable):
        raise TypeError("roots must be an iterable of TemplateRoot records")
    root_records = tuple(roots)
    if not root_records:
        return _RootInventory(
            roots=(),
            entries=(),
            diagnostics=(
                _configuration_diagnostic(
                    "no template roots were provided",
                    suggestion="Provide at least one explicitly namespaced template root.",
                ),
            ),
        )
    if any(not isinstance(root, TemplateRoot) for root in root_records):
        raise TypeError("roots must contain only TemplateRoot records")

    diagnostics: list[Diagnostic] = []
    seen_namespaces: set[str] = set()
    seen_names: dict[str, str] = {}
    entries: list[_TemplateEntry] = []
    for root in root_records:
        resolved = root.path.resolve()
        if root.namespace in seen_namespaces:
            diagnostics.append(
                _configuration_diagnostic(
                    f"duplicate template root namespace '{root.namespace}'",
                    namespace=root.namespace,
                    source_path=str(resolved),
                    suggestion="Give every root a unique namespace.",
                )
            )
            continue
        seen_namespaces.add(root.namespace)
        if not resolved.is_dir():
            diagnostics.append(
                _configuration_diagnostic(
                    f"template root '{root.namespace}' is not a directory: {resolved}",
                    namespace=root.namespace,
                    source_path=str(resolved),
                    suggestion="Create the directory or pass the correct root path.",
                )
            )
            continue

        paths: set[Path] = set()
        for glob in _TEMPLATE_GLOBS:
            paths.update(resolved.rglob(glob))
        for source_path in sorted(paths):
            relative = source_path.relative_to(resolved).as_posix()
            name = f"{root.namespace}/{relative}"
            previous = seen_names.get(name)
            if previous is not None:
                diagnostics.append(
                    _configuration_diagnostic(
                        f"duplicate logical template identifier '{name}'",
                        namespace=root.namespace,
                        source_path=str(source_path),
                        suggestion=f"Rename one template; the identifier is already owned by {previous}.",
                    )
                )
                continue
            seen_names[name] = str(source_path)
            entries.append(
                _TemplateEntry(
                    owner=root.namespace,
                    name=name,
                    source_path=source_path,
                )
            )

    return _RootInventory(
        roots=root_records,
        entries=tuple(sorted(entries, key=lambda entry: (entry.name, str(entry.source_path)))),
        diagnostics=tuple(diagnostics),
    )


def _default_environment(inventory: _RootInventory) -> Environment:
    from kida.environment import Environment, FileSystemLoader, PrefixLoader

    valid_roots: dict[str, FileSystemLoader] = {}
    for root in inventory.roots:
        resolved = root.path.resolve()
        if resolved.is_dir() and root.namespace not in valid_roots:
            valid_roots[root.namespace] = FileSystemLoader(resolved)
    loader_mapping = cast(
        "dict[str, FileSystemLoader | DictLoader | ChoiceLoader | PrefixLoader | PackageLoader | FunctionLoader]",
        valid_roots,
    )
    return Environment(
        loader=PrefixLoader(loader_mapping),
        validate_calls=False,
        bytecode_cache=False,
    )


def diagnose_roots(
    roots: Iterable[TemplateRoot],
    *,
    environment: Environment | None = None,
    options: DiagnosticOptions = _DEFAULT_OPTIONS,
) -> DiagnosticReport:
    """Diagnose explicitly namespaced roots with one deterministic inventory."""
    result = _collect_root_check_result(
        roots,
        environment=environment,
        options=options,
    )
    return DiagnosticReport(diagnostics=result.diagnostics, partial=result.partial)


def _collect_root_check_result(
    roots: Iterable[TemplateRoot],
    *,
    environment: Environment | None,
    options: DiagnosticOptions,
):
    """Return the private event-rich result used by CLI renderers."""
    from kida.environment import Environment

    if environment is not None and not isinstance(environment, Environment):
        raise TypeError("environment must be a kida.Environment")
    if not isinstance(options, DiagnosticOptions):
        raise TypeError("options must be a DiagnosticOptions record")
    inventory = _build_inventory(roots)
    env = environment or _default_environment(inventory)

    from kida._check import collect_inventory_diagnostics

    result = collect_inventory_diagnostics(
        inventory,
        environment=env,
        strict=options.strict,
        validate_calls=options.validate_calls,
        a11y=options.a11y,
        typed=options.typed,
        lint_fragile_paths=options.lint_fragile_paths,
    )
    return result


def inspect_components(
    roots: Iterable[TemplateRoot],
    *,
    environment: Environment | None = None,
    filter_name: str | None = None,
) -> ComponentInspection:
    """Collect component metadata across explicitly namespaced roots."""
    from kida.environment import Environment

    if environment is not None and not isinstance(environment, Environment):
        raise TypeError("environment must be a kida.Environment")
    if filter_name is not None and not isinstance(filter_name, str):
        raise TypeError("filter_name must be a string or None")
    inventory = _build_inventory(roots)
    env = environment or _default_environment(inventory)
    diagnostics = list(inventory.diagnostics)
    records: list[ComponentRecord] = []
    partial = inventory.partial
    source_names = {str(entry.source_path.resolve()): entry.name for entry in inventory.entries}

    from kida._check import (
        _exception_diagnostic,
        _exception_template_path,
        _loader_ownership_diagnostic,
        _with_inventory_metadata,
    )

    for entry in inventory.entries:
        try:
            template = env.get_template(entry.name)
        except Exception as exc:
            error_path = _exception_template_path(exc, entry.name, source_names)
            diagnostic = _exception_diagnostic(exc, error_path)
            metadata_entry = next(
                (candidate for candidate in inventory.entries if candidate.name == error_path),
                entry,
            )
            diagnostics.append(
                _with_inventory_metadata(
                    diagnostic,
                    owner=metadata_entry.owner,
                    source_path=str(metadata_entry.source_path),
                )
            )
            partial = True
            continue
        actual_path = template._filename
        if actual_path is None or Path(actual_path).resolve() != entry.source_path.resolve():
            diagnostics.append(
                _with_inventory_metadata(
                    _loader_ownership_diagnostic(
                        name=entry.name,
                        expected_path=entry.source_path,
                        actual_path=actual_path,
                    ),
                    owner=entry.owner,
                    source_path=str(entry.source_path),
                )
            )
            partial = True
            continue
        for metadata in template.def_metadata().values():
            if filter_name and filter_name.lower() not in metadata.name.lower():
                continue
            records.append(
                ComponentRecord(
                    owner=entry.owner,
                    template=entry.name,
                    source_path=str(entry.source_path),
                    metadata=metadata,
                )
            )
    records.sort(key=lambda record: (record.template, record.metadata.lineno, record.metadata.name))
    diagnostics.sort(
        key=lambda diagnostic: (
            diagnostic.span.path or "",
            diagnostic.span.start.line if diagnostic.span.start else -1,
            diagnostic.code,
            diagnostic.message,
        )
    )
    return ComponentInspection(
        components=tuple(records),
        diagnostics=tuple(diagnostics),
        partial=partial,
    )


def advise_encapsulation_roots(
    roots: Iterable[TemplateRoot],
    *,
    environment: Environment | None = None,
) -> DiagnosticReport:
    """Return opt-in extraction and flattening advice across owned roots."""
    from kida.environment import Environment

    if environment is not None and not isinstance(environment, Environment):
        raise TypeError("environment must be a kida.Environment")
    inventory = _build_inventory(roots)
    env = environment or _default_environment(inventory)
    diagnostics = list(inventory.diagnostics)
    partial = inventory.partial
    source_names = {str(entry.source_path.resolve()): entry.name for entry in inventory.entries}

    from kida._check import (
        _exception_diagnostic,
        _exception_template_path,
        _loader_ownership_diagnostic,
        _with_inventory_metadata,
    )
    from kida.analysis.encapsulation_advice import _advise_flattening, _OwnedTemplate
    from kida.analysis.extraction_advice import _parse, advise_extraction_source

    templates: list[_OwnedTemplate] = []
    for entry in inventory.entries:
        try:
            template = env.get_template(entry.name)
        except Exception as exc:
            error_path = _exception_template_path(exc, entry.name, source_names)
            diagnostic = _exception_diagnostic(exc, error_path)
            metadata_entry = next(
                (candidate for candidate in inventory.entries if candidate.name == error_path),
                entry,
            )
            diagnostics.append(
                _with_inventory_metadata(
                    diagnostic,
                    owner=metadata_entry.owner,
                    source_path=str(metadata_entry.source_path),
                )
            )
            partial = True
            continue
        actual_path = template._filename
        if actual_path is None or Path(actual_path).resolve() != entry.source_path.resolve():
            diagnostics.append(
                _with_inventory_metadata(
                    _loader_ownership_diagnostic(
                        name=entry.name,
                        expected_path=entry.source_path,
                        actual_path=actual_path,
                    ),
                    owner=entry.owner,
                    source_path=str(entry.source_path),
                )
            )
            partial = True
            continue

        source = template._source
        if source is None:
            source = entry.source_path.read_text(encoding="utf-8")
        ast, profile_spans = _parse(source, name=entry.name, environment=env)
        templates.append(
            _OwnedTemplate(
                owner=entry.owner,
                name=entry.name,
                source_path=str(entry.source_path),
                ast=ast,
                profile_spans=profile_spans,
            )
        )
        extraction = advise_extraction_source(source, name=entry.name, environment=env)
        diagnostics.extend(
            _with_inventory_metadata(
                diagnostic,
                owner=entry.owner,
                source_path=str(entry.source_path),
            )
            for diagnostic in extraction.diagnostics
        )
        partial = partial or extraction.partial

    diagnostics.extend(_advise_flattening(tuple(templates)))
    diagnostics.sort(
        key=lambda diagnostic: (
            diagnostic.span.path or "",
            diagnostic.span.start.line if diagnostic.span.start else -1,
            diagnostic.span.start.column if diagnostic.span.start else -1,
            diagnostic.code,
            diagnostic.message,
        )
    )
    return DiagnosticReport(diagnostics=tuple(diagnostics), partial=partial)


__all__ = [
    "ComponentInspection",
    "ComponentRecord",
    "TemplateRoot",
    "advise_encapsulation_roots",
    "diagnose_roots",
    "inspect_components",
]
