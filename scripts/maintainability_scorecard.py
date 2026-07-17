#!/usr/bin/env python3
"""Report maintainability baselines without enforcing a CI gate."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, cast

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src" / "kida"
TEST_ROOT = ROOT / "tests"

Direction = Literal["max", "min"]


@dataclass(frozen=True, slots=True)
class Budget:
    """A report-only target with a checked-in regression ratchet."""

    name: str
    current: int | float | None
    ratchet: int | float
    target: int | float
    direction: Direction
    unit: str

    @property
    def status(self) -> str:
        if self.current is None:
            return "unavailable"
        if self.direction == "max":
            if self.current <= self.target:
                return "target"
            if self.current <= self.ratchet:
                return "ratchet"
            return "regressed"
        if self.current >= self.target:
            return "target"
        if self.current >= self.ratchet:
            return "ratchet"
        return "regressed"


@dataclass(frozen=True, slots=True)
class DefinitionMetric:
    """Span and complexity data for one Python definition."""

    path: str
    qualified_name: str
    kind: Literal["class", "function"]
    start_line: int
    end_line: int
    lines: int
    complexity: int | None


class _ComplexityVisitor(ast.NodeVisitor):
    """Compute a small, documented McCabe-style decision count."""

    def __init__(self, root: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.root = root
        self.score = 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node is self.root:
            self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node is self.root:
            self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_If(self, node: ast.If) -> None:
        self.score += 1
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self.score += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.score += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.score += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.score += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.score += max(0, len(node.values) - 1)
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:
        self.score += len(node.handlers) + bool(node.orelse)
        self.generic_visit(node)

    def visit_TryStar(self, node: ast.TryStar) -> None:
        self.score += len(node.handlers) + bool(node.orelse)
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        self.score += len(node.cases)
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.score += 1 + len(node.ifs)
        self.generic_visit(node)


class _DefinitionVisitor(ast.NodeVisitor):
    """Collect qualified definition spans without conflating nested scopes."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.scope: list[str] = []
        self.definitions: list[DefinitionMetric] = []

    def _record(
        self,
        node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
        kind: Literal["class", "function"],
    ) -> None:
        end_line = node.end_lineno or node.lineno
        complexity: int | None = None
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            visitor = _ComplexityVisitor(node)
            visitor.visit(node)
            complexity = visitor.score
        self.definitions.append(
            DefinitionMetric(
                path=self.path,
                qualified_name=".".join([*self.scope, node.name]),
                kind=kind,
                start_line=node.lineno,
                end_line=end_line,
                lines=end_line - node.lineno + 1,
                complexity=complexity,
            )
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._record(node, "class")
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._record(node, "function")
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._record(node, "function")
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def _physical_lines(paths: list[Path]) -> int:
    return sum(len(path.read_text(encoding="utf-8").splitlines()) for path in paths)


def _definitions(source_files: list[Path]) -> list[DefinitionMetric]:
    definitions: list[DefinitionMetric] = []
    for path in source_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        visitor = _DefinitionVisitor(_relative(path))
        visitor.visit(tree)
        definitions.extend(visitor.definitions)
    return definitions


def _public_exports() -> list[str]:
    init_path = SOURCE_ROOT / "__init__.py"
    tree = ast.parse(init_path.read_text(encoding="utf-8"), filename=str(init_path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
            value = ast.literal_eval(node.value)
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise TypeError("kida.__all__ must be a literal list of strings")
            return sorted(value)
    raise RuntimeError("kida.__all__ was not found")


def _documented_exports(exports: list[str]) -> tuple[list[str], list[str]]:
    docs = [ROOT / "README.md"]
    docs.extend((ROOT / "site" / "content" / "docs").rglob("*.md"))
    docs.extend((ROOT / "examples").rglob("*.py"))
    corpus = "\n".join(path.read_text(encoding="utf-8") for path in docs if path.is_file())
    documented = [name for name in exports if re.search(rf"\b{re.escape(name)}\b", corpus)]
    undocumented = sorted(set(exports) - set(documented))
    return documented, undocumented


def _import_closure() -> tuple[list[str], str | None]:
    probe = """
import json
import pathlib
import sys
import kida
root = pathlib.Path(kida.__file__).resolve().parent
assert kida.Environment().from_string("Hello").render() == "Hello"
modules = []
for name, module in sys.modules.items():
    filename = getattr(module, "__file__", None)
    if not filename:
        continue
    path = pathlib.Path(filename).resolve()
    if path == root or root in path.parents:
        modules.append(name)
print(json.dumps(sorted(modules)))
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return [], result.stderr.strip() or f"probe exited {result.returncode}"
    return json.loads(result.stdout), None


def _imported_kida_modules(test_files: list[Path]) -> set[str]:
    imported: set[str] = set()
    for path in test_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names if alias.name.startswith("kida"))
            elif (
                isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("kida")
            ):
                imported.add(node.module)
    return imported


def _module_name(path: Path) -> str:
    relative = path.relative_to(ROOT / "src").with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _source_test_ownership(
    source_files: list[Path], test_files: list[Path]
) -> tuple[list[str], list[str]]:
    imported = _imported_kida_modules(test_files)
    test_names = {path.stem.removeprefix("test_") for path in test_files}
    owned: list[str] = []
    unowned: list[str] = []
    for path in source_files:
        module = _module_name(path)
        direct_import = module in imported or any(
            name.startswith(f"{module}.") for name in imported
        )
        filename_match = path.stem != "__init__" and path.stem in test_names
        target = owned if direct_import or filename_match else unowned
        target.append(_relative(path))
    return owned, unowned


CRITICAL_COVERAGE_PATHS = (
    "src/kida/analysis/type_checker.py",
    "src/kida/bytecode_cache.py",
    "src/kida/environment/exceptions.py",
    "src/kida/environment/loaders.py",
    "src/kida/sandbox.py",
    "src/kida/utils/html.py",
    "src/kida/utils/lru_cache.py",
    "src/kida/utils/markdown_escape.py",
    "src/kida/utils/template_keys.py",
    "src/kida/utils/terminal_escape.py",
)


def _critical_coverage(path: Path | None) -> tuple[float | None, list[str]]:
    candidates = (
        [path] if path is not None else [ROOT / "coverage.json", ROOT / "reports/coverage.json"]
    )
    coverage_path = next(
        (candidate for candidate in candidates if candidate and candidate.is_file()), None
    )
    if coverage_path is None:
        return None, list(CRITICAL_COVERAGE_PATHS)
    payload = json.loads(coverage_path.read_text(encoding="utf-8"))
    files = payload.get("files", {})
    found = [files[name]["summary"] for name in CRITICAL_COVERAGE_PATHS if name in files]
    missing = [name for name in CRITICAL_COVERAGE_PATHS if name not in files]
    if missing or not found:
        return None, missing
    covered = sum(summary["covered_lines"] for summary in found)
    statements = sum(summary["num_statements"] for summary in found)
    return round(covered / statements * 100, 1) if statements else 100.0, missing


# These report-only ratchets capture the July 2026 audit baseline. They make
# regressions visible without turning the scorecard into a CI failure gate.
RATCHETS = {
    "functions_over_200_lines": 12,
    "classes_over_1000_lines": 4,
    "complexity_over_25": 11,
    "public_exports": 73,
    "undocumented_exports": 2,
    "basic_render_import_modules": 93,
    "source_test_ownership_percent": 63.4,
    "critical_coverage_percent": 84.5,
}


def build_scorecard(*, coverage_json: Path | None = None) -> dict[str, object]:
    """Collect the scorecard as a deterministic JSON-compatible mapping."""
    source_files = _python_files(SOURCE_ROOT)
    test_files = _python_files(TEST_ROOT)
    definitions = _definitions(source_files)
    functions = [item for item in definitions if item.kind == "function"]
    classes = [item for item in definitions if item.kind == "class"]
    long_functions = [item for item in functions if item.lines > 200]
    large_classes = [item for item in classes if item.lines > 1000]
    complex_functions = [item for item in functions if (item.complexity or 0) > 25]

    exports = _public_exports()
    documented, undocumented = _documented_exports(exports)
    closure, closure_error = _import_closure()
    owned, unowned = _source_test_ownership(source_files, test_files)
    ownership_percent = round(len(owned) / len(source_files) * 100, 1) if source_files else 100.0
    coverage_percent, missing_coverage = _critical_coverage(coverage_json)

    budgets = [
        Budget(
            "functions_over_200_lines",
            len(long_functions),
            RATCHETS["functions_over_200_lines"],
            0,
            "max",
            "definitions",
        ),
        Budget(
            "classes_over_1000_lines",
            len(large_classes),
            RATCHETS["classes_over_1000_lines"],
            0,
            "max",
            "definitions",
        ),
        Budget(
            "complexity_over_25",
            len(complex_functions),
            RATCHETS["complexity_over_25"],
            RATCHETS["complexity_over_25"],
            "max",
            "definitions",
        ),
        Budget(
            "public_exports",
            len(exports),
            RATCHETS["public_exports"],
            RATCHETS["public_exports"],
            "max",
            "exports",
        ),
        Budget(
            "undocumented_exports",
            len(undocumented),
            RATCHETS["undocumented_exports"],
            0,
            "max",
            "exports",
        ),
        Budget(
            "basic_render_import_modules",
            len(closure) if not closure_error else None,
            RATCHETS["basic_render_import_modules"],
            RATCHETS["basic_render_import_modules"],
            "max",
            "modules",
        ),
        Budget(
            "source_test_ownership_percent",
            ownership_percent,
            RATCHETS["source_test_ownership_percent"],
            100.0,
            "min",
            "percent",
        ),
        Budget(
            "critical_coverage_percent",
            coverage_percent,
            RATCHETS["critical_coverage_percent"],
            95.0,
            "min",
            "percent",
        ),
    ]

    return {
        "schema_version": 1,
        "scope": {
            "source_files": len(source_files),
            "source_lines": _physical_lines(source_files),
            "test_files": len(test_files),
            "test_lines": _physical_lines(test_files),
        },
        "budgets": [{**asdict(item), "status": item.status} for item in budgets],
        "outliers": {
            "functions_over_200_lines": [asdict(item) for item in long_functions],
            "classes_over_1000_lines": [asdict(item) for item in large_classes],
            "complexity_over_25": [asdict(item) for item in complex_functions],
        },
        "public_api": {
            "exports": exports,
            "documented": documented,
            "undocumented": undocumented,
        },
        "import_closure": {"modules": closure, "error": closure_error},
        "source_test_ownership": {"owned": owned, "unowned": unowned},
        "critical_coverage": {
            "paths": list(CRITICAL_COVERAGE_PATHS),
            "missing": missing_coverage,
        },
    }


def _render_text(scorecard: dict[str, object]) -> str:
    scope = cast("dict[str, object]", scorecard["scope"])
    lines = [
        "Kida maintainability scorecard (report only)",
        f"source: {scope['source_files']} files / {scope['source_lines']} lines",
        f"tests:  {scope['test_files']} files / {scope['test_lines']} lines",
        "",
        "metric                              current   ratchet   target   status",
    ]
    budgets = cast("list[dict[str, object]]", scorecard["budgets"])
    for budget in budgets:
        current = "n/a" if budget["current"] is None else str(budget["current"])
        name = str(budget["name"])
        ratchet = str(budget["ratchet"])
        target = str(budget["target"])
        status = str(budget["status"])
        lines.append(f"{name:<35} {current:>7} {ratchet:>9} {target:>8}   {status}")
    lines.append("")
    lines.append("Report-only: a 'regressed' status does not change the process exit code.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the full JSON scorecard")
    parser.add_argument("--coverage-json", type=Path, help="coverage.py JSON report to ingest")
    args = parser.parse_args(argv)
    scorecard = build_scorecard(coverage_json=args.coverage_json)
    if args.json:
        print(json.dumps(scorecard, indent=2, sort_keys=True))
    else:
        print(_render_text(scorecard))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
