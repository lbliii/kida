"""Auto-detect project metadata from pyproject.toml, filesystem, and git."""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path  # noqa: TC003 — used at runtime
from typing import Any

# Directories to ignore when walking the project tree.
_DEFAULT_IGNORE = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".venv",
        "venv",
        ".env",
        "node_modules",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        ".tox",
        ".nox",
        "dist",
        "build",
        "*.egg-info",
        ".eggs",
        ".context",
        ".cursor",
        ".dori",
        ".claude",
        ".vscode",
        ".idea",
    }
)


def walk_tree(
    root: Path,
    *,
    depth: int = 2,
    ignore: set[str] | None = None,
) -> dict[str, Any]:
    """Walk a directory into a nested dict suitable for tree rendering.

    Returns a dict where keys are directory/file names and values are either
    nested dicts (for directories) or ``None`` (for files).
    """
    ignored = _DEFAULT_IGNORE if ignore is None else frozenset(ignore)

    def _walk(path: Path, current_depth: int) -> dict[str, Any]:
        if current_depth <= 0:
            return {}
        entries: dict[str, Any] = {}
        try:
            children = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
        except PermissionError:
            return {}
        for child in children:
            name = child.name
            if name.startswith("."):
                continue
            if name in ignored:
                continue
            # Handle glob-style ignores like *.egg-info
            if any(name.endswith(pat.lstrip("*")) for pat in ignored if pat.startswith("*")):
                continue
            if child.is_dir():
                entries[name] = _walk(child, current_depth - 1)
            else:
                entries[name] = None
        return entries

    return _walk(root, depth)


def _render_tree(tree: dict[str, Any], prefix: str = "") -> str:
    """Render a nested dict as an ASCII tree string."""
    lines: list[str] = []
    entries = list(tree.items())
    for i, (name, children) in enumerate(entries):
        is_last = i == len(entries) - 1
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{name}")
        if isinstance(children, dict) and children:
            extension = "    " if is_last else "│   "
            lines.append(_render_tree(children, prefix + extension))
    return "\n".join(lines)


def _detect_build_tool(root: Path, pyproject: dict[str, Any]) -> tuple[str, str]:
    """Detect build tool and return (tool_name, install_command)."""
    if (root / "uv.lock").exists():
        return "uv", "uv sync --group dev"
    if (root / "poetry.lock").exists():
        return "poetry", "poetry install"
    if (root / "Pipfile.lock").exists():
        return "pipenv", "pipenv install --dev"
    if "hatch" in pyproject.get("tool", {}):
        return "hatch", "hatch env create"
    if (root / "setup.py").exists() or (root / "setup.cfg").exists():
        return "pip", "pip install -e '.[dev]'"
    return "pip", "pip install -e '.[dev]'"


def _detect_test_command(root: Path, pyproject: dict[str, Any]) -> str:
    """Detect test framework and return the run command."""
    tool = pyproject.get("tool", {})
    build_tool = _detect_build_tool(root, pyproject)[0]
    prefix = "uv run " if build_tool == "uv" else ""

    if "pytest" in tool or (root / "pytest.ini").exists():
        return f"{prefix}pytest"
    if (root / "tests").is_dir() or (root / "test").is_dir():
        return f"{prefix}pytest"
    return f"{prefix}python -m unittest"


def _detect_repo_url(pyproject: dict[str, Any], root: Path) -> str | None:
    """Detect repository URL from pyproject or git remote."""
    urls = pyproject.get("project", {}).get("urls", {})
    for key in ("Repository", "repository", "Source", "source", "GitHub", "github"):
        if key in urls:
            return urls[key]

    # Fall back to git remote
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            cwd=root,
            timeout=5,
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            # Convert SSH URLs to HTTPS
            if url.startswith("git@"):
                url = url.replace(":", "/", 1).replace("git@", "https://")
            url = url.removesuffix(".git")
            return url
    except FileNotFoundError, subprocess.TimeoutExpired:
        pass
    return None


def _detect_author(pyproject: dict[str, Any], root: Path) -> str | None:
    """Detect author from pyproject or git config."""
    authors = pyproject.get("project", {}).get("authors", [])
    if authors:
        first = authors[0]
        if isinstance(first, dict):
            return first.get("name") or first.get("email")
        return str(first)

    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            cwd=root,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
    except FileNotFoundError, subprocess.TimeoutExpired:
        pass
    return None


def detect_project(root: Path, *, depth: int = 2) -> dict[str, Any]:
    """Auto-detect project metadata from a directory.

    Reads ``pyproject.toml``, inspects the filesystem for build tools, test
    frameworks, and directory structure, and falls back to git for repo URL
    and author information.

    Args:
        root: Project root directory.
        depth: How many levels deep to walk the directory tree (default 2).

    Returns:
        A dict of template context variables.
    """
    root = root.resolve()
    pyproject: dict[str, Any] = {}
    pyproject_path = root / "pyproject.toml"
    if pyproject_path.exists():
        with pyproject_path.open("rb") as f:
            pyproject = tomllib.load(f)

    project = pyproject.get("project", {})

    # Build tool
    build_tool, install_command = _detect_build_tool(root, pyproject)

    # CLI entrypoints
    scripts = project.get("scripts", {})
    has_cli = bool(scripts)
    cli_name = next(iter(scripts), None) if scripts else None

    # Dev dependencies from multiple sources
    dev_deps: dict[str, list[str]] = {}
    # [dependency-groups]
    for group, deps in pyproject.get("dependency-groups", {}).items():
        dev_deps[group] = [str(d) for d in deps if isinstance(d, str)]
    # [project.optional-dependencies]
    for group, deps in project.get("optional-dependencies", {}).items():
        if group not in dev_deps:
            dev_deps[group] = [str(d) for d in deps]

    # Tree
    tree = walk_tree(root, depth=depth)
    tree_str = _render_tree(tree)

    return {
        "name": project.get("name", root.name),
        "version": project.get("version", ""),
        "description": project.get("description", ""),
        "license": project.get("license", ""),
        "python_requires": project.get("requires-python", ""),
        "dependencies": project.get("dependencies", []),
        "dev_dependencies": dev_deps,
        "has_cli": has_cli,
        "cli_name": cli_name,
        "scripts": scripts,
        "tree": tree,
        "tree_str": tree_str,
        "has_tests": (root / "tests").is_dir() or (root / "test").is_dir(),
        "has_docs": (root / "docs").is_dir() or (root / "site").is_dir(),
        "has_ci": (root / ".github" / "workflows").is_dir(),
        "test_command": _detect_test_command(root, pyproject),
        "build_tool": build_tool,
        "install_command": install_command,
        "repo_url": _detect_repo_url(pyproject, root),
        "author": _detect_author(pyproject, root),
    }
