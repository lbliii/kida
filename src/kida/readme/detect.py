"""Auto-detect project metadata from pyproject.toml, filesystem, and git."""

from __future__ import annotations

import ast
import subprocess
import tomllib
from pathlib import Path  # noqa: TC003 — used at runtime
from typing import Any, TypedDict


class ProjectContext(TypedDict):
    """Template context returned by :func:`detect_project`."""

    name: str
    version: str
    description: str
    license: str
    python_requires: str
    dependencies: list[str]
    has_zero_deps: bool
    extras: dict[str, Any]
    dev_dependencies: dict[str, list[str]]
    has_cli: bool
    cli_name: str | None
    scripts: dict[str, str]
    tree: dict[str, Any]
    tree_str: str
    has_tests: bool
    has_docs: bool
    has_ci: bool
    test_command: str
    build_tool: str
    install_command: str
    repo_url: str
    author: str
    keywords: list[str]
    suggested_preset: str


# Maximum number of child entries before collapsing files in a directory.
_COLLAPSE_THRESHOLD = 15

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


def _extract_docstring(path: Path) -> str | None:
    """Extract the first line of a Python file's module docstring."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        doc = ast.get_docstring(tree)
        if doc:
            return doc.split("\n")[0].strip().rstrip(".")
    except SyntaxError, UnicodeDecodeError, OSError:
        pass
    return None


def annotate_tree(root: Path, tree: dict[str, Any]) -> dict[str, Any]:
    """Add first-line docstrings as annotations to Python packages and modules.

    Modifies *tree* in place, adding ``__annotation__`` keys to entries
    that have extractable docstrings. Recurses into subdirectories.
    """
    for name, children in list(tree.items()):
        path = root / name
        if path.is_dir() and isinstance(children, dict):
            # Recurse into subdirectories
            annotate_tree(path, children)
            if (path / "__init__.py").exists():
                doc = _extract_docstring(path / "__init__.py")
                if doc:
                    children["__annotation__"] = doc
        elif path.suffix == ".py" and path.is_file():
            doc = _extract_docstring(path)
            if doc:
                # Store annotation as a string value (not dict) so files
                # aren't confused with directories.
                tree[name] = doc
    return tree


def collapse_tree(tree: dict[str, Any]) -> dict[str, Any]:
    """Collapse directories with too many children for readability.

    When a directory has more than :data:`_COLLAPSE_THRESHOLD` entries,
    files are replaced with a single ``... and N files`` summary while
    subdirectories are preserved.
    """
    result: dict[str, Any] = {}
    for name, children in tree.items():
        if not isinstance(children, dict) or not children:
            result[name] = children
            continue
        # Recurse first
        collapsed = collapse_tree(children)
        # Remove internal __annotation__ from count
        annotation = collapsed.pop("__annotation__", None)
        dirs = {k: v for k, v in collapsed.items() if isinstance(v, dict)}
        files = {k: v for k, v in collapsed.items() if not isinstance(v, dict)}

        if len(dirs) + len(files) > _COLLAPSE_THRESHOLD and files:
            new_children: dict[str, Any] = {}
            if annotation:
                new_children["__annotation__"] = annotation
            new_children.update(dirs)
            new_children[f"... and {len(files)} files"] = None
            result[name] = new_children
        else:
            if annotation:
                collapsed["__annotation__"] = annotation
            result[name] = collapsed
    return result


def _render_tree(tree: dict[str, Any], prefix: str = "") -> str:
    """Render a nested dict as an ASCII tree string.

    Entries with an ``__annotation__`` key get a ``# comment`` suffix.
    """
    lines: list[str] = []
    # Filter out __annotation__ from iteration
    visible = [(k, v) for k, v in tree.items() if k != "__annotation__"]
    for i, (name, children) in enumerate(visible):
        is_last = i == len(visible) - 1
        connector = "└── " if is_last else "├── "
        is_dir = isinstance(children, dict)
        # Annotation: directory annotation is in __annotation__ key,
        # file annotation is stored as a string value directly.
        entry_annotation = None
        if is_dir and "__annotation__" in children:
            entry_annotation = children["__annotation__"]
        elif isinstance(children, str):
            entry_annotation = children
        suffix = f"  # {entry_annotation}" if entry_annotation else ""
        display = f"{name}/" if is_dir else name
        lines.append(f"{prefix}{connector}{display}{suffix}")
        # Recurse into directories that have visible (non-annotation) children
        if is_dir and any(k != "__annotation__" for k in children):
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


def detect_preset(ctx: dict[str, Any]) -> str:
    """Auto-detect the best README preset based on project metadata.

    Priority:
        1. Has CLI entrypoints → ``"cli"``
        2. Has runtime dependencies → ``"library"``
        3. Otherwise → ``"default"``
    """
    if ctx.get("has_cli"):
        return "cli"
    if ctx.get("dependencies"):
        return "library"
    return "default"


def detect_project(root: Path, *, depth: int = 2) -> ProjectContext:
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

    # Tree — walk, annotate, collapse, render
    tree = walk_tree(root, depth=depth)
    annotate_tree(root, tree)
    tree = collapse_tree(tree)
    tree_str = _render_tree(tree)

    # Optional extras (separate from dev dependencies)
    extras = dict(project.get("optional-dependencies", {}))

    # Runtime dependencies
    dependencies = project.get("dependencies", [])

    base: dict[str, Any] = {
        "name": project.get("name", root.name),
        "version": project.get("version", ""),
        "description": project.get("description", ""),
        "license": project.get("license", ""),
        "python_requires": project.get("requires-python", ""),
        "dependencies": dependencies,
        "has_zero_deps": len(dependencies) == 0,
        "extras": extras,
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
        "keywords": project.get("keywords", []),
    }
    base["suggested_preset"] = detect_preset(base)
    return base  # type: ignore[return-value]
