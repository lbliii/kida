"""Tests for the kida readme feature — detection, rendering, and CLI."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from kida.readme import render_readme
from kida.readme.detect import (
    _detect_build_tool,
    _render_tree,
    detect_project,
    walk_tree,
)

# ── Tree walker ──────────────────────────────────────────────────────────


class TestWalkTree:
    def test_walks_simple_directory(self, tmp_path: Path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").touch()
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_main.py").touch()
        (tmp_path / "README.md").touch()

        tree = walk_tree(tmp_path, depth=2)
        assert "src" in tree
        assert "main.py" in tree["src"]
        assert "tests" in tree
        assert "README.md" in tree

    def test_respects_depth_limit(self, tmp_path: Path):
        (tmp_path / "a" / "b" / "c").mkdir(parents=True)
        (tmp_path / "a" / "b" / "c" / "deep.txt").touch()

        tree = walk_tree(tmp_path, depth=1)
        # depth=1 shows 'a' but its contents should be empty
        assert "a" in tree
        assert tree["a"] == {}

    def test_ignores_default_patterns(self, tmp_path: Path):
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / ".git").mkdir()
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "src").mkdir()

        tree = walk_tree(tmp_path, depth=1)
        assert "__pycache__" not in tree
        assert ".git" not in tree
        assert "node_modules" not in tree
        assert "src" in tree

    def test_ignores_egg_info_glob(self, tmp_path: Path):
        (tmp_path / "my_pkg.egg-info").mkdir()
        (tmp_path / "src").mkdir()

        tree = walk_tree(tmp_path, depth=1)
        assert "my_pkg.egg-info" not in tree
        assert "src" in tree

    def test_custom_ignore(self, tmp_path: Path):
        (tmp_path / "keep").mkdir()
        (tmp_path / "skip").mkdir()

        tree = walk_tree(tmp_path, depth=1, ignore={"skip"})
        assert "keep" in tree
        assert "skip" not in tree

    def test_directories_before_files(self, tmp_path: Path):
        (tmp_path / "zebra.txt").touch()
        (tmp_path / "alpha").mkdir()

        tree = walk_tree(tmp_path, depth=1)
        keys = list(tree.keys())
        # Directories sorted first
        assert keys[0] == "alpha"


# ── Render tree ──────────────────────────────────────────────────────────


class TestRenderTree:
    def test_simple_tree(self):
        data = {"src": {"main.py": None}, "README.md": None}
        result = _render_tree(data)
        assert "├── src" in result
        assert "│   └── main.py" in result
        assert "└── README.md" in result

    def test_empty_dict(self):
        assert _render_tree({}) == ""


# ── Build tool detection ─────────────────────────────────────────────────


class TestDetectBuildTool:
    def test_uv_lock(self, tmp_path: Path):
        (tmp_path / "uv.lock").touch()
        tool, cmd = _detect_build_tool(tmp_path, {})
        assert tool == "uv"
        assert "uv" in cmd

    def test_poetry_lock(self, tmp_path: Path):
        (tmp_path / "poetry.lock").touch()
        tool, _ = _detect_build_tool(tmp_path, {})
        assert tool == "poetry"

    def test_pipfile_lock(self, tmp_path: Path):
        (tmp_path / "Pipfile.lock").touch()
        tool, _ = _detect_build_tool(tmp_path, {})
        assert tool == "pipenv"

    def test_hatch_config(self, tmp_path: Path):
        tool, _ = _detect_build_tool(tmp_path, {"tool": {"hatch": {}}})
        assert tool == "hatch"

    def test_setup_py(self, tmp_path: Path):
        (tmp_path / "setup.py").touch()
        tool, _ = _detect_build_tool(tmp_path, {})
        assert tool == "pip"

    def test_fallback(self, tmp_path: Path):
        tool, _ = _detect_build_tool(tmp_path, {})
        assert tool == "pip"


# ── Full detection ───────────────────────────────────────────────────────


class TestDetectProject:
    def test_minimal_pyproject(self, tmp_path: Path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            textwrap.dedent("""\
            [project]
            name = "test-pkg"
            version = "1.0.0"
            description = "A test package"
        """)
        )

        ctx = detect_project(tmp_path)
        assert ctx["name"] == "test-pkg"
        assert ctx["version"] == "1.0.0"
        assert ctx["description"] == "A test package"
        assert ctx["has_cli"] is False
        assert ctx["cli_name"] is None

    def test_with_scripts(self, tmp_path: Path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            textwrap.dedent("""\
            [project]
            name = "my-cli"
            version = "0.1.0"

            [project.scripts]
            mycli = "my_cli.main:run"
        """)
        )

        ctx = detect_project(tmp_path)
        assert ctx["has_cli"] is True
        assert ctx["cli_name"] == "mycli"
        assert ctx["scripts"] == {"mycli": "my_cli.main:run"}

    def test_with_urls(self, tmp_path: Path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            textwrap.dedent("""\
            [project]
            name = "test-pkg"
            version = "1.0.0"

            [project.urls]
            Repository = "https://github.com/user/repo"
        """)
        )

        ctx = detect_project(tmp_path)
        assert ctx["repo_url"] == "https://github.com/user/repo"

    def test_no_pyproject(self, tmp_path: Path):
        ctx = detect_project(tmp_path)
        # Falls back to directory name
        assert ctx["name"] == tmp_path.name
        assert ctx["version"] == ""

    def test_has_tests_directory(self, tmp_path: Path):
        (tmp_path / "tests").mkdir()
        ctx = detect_project(tmp_path)
        assert ctx["has_tests"] is True

    def test_tree_str_populated(self, tmp_path: Path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").touch()
        ctx = detect_project(tmp_path, depth=2)
        assert "src" in ctx["tree_str"]
        assert "main.py" in ctx["tree_str"]

    def test_dev_dependencies_from_groups(self, tmp_path: Path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            textwrap.dedent("""\
            [project]
            name = "test-pkg"
            version = "1.0.0"

            [dependency-groups]
            dev = ["pytest>=8.0", "ruff"]
        """)
        )

        ctx = detect_project(tmp_path)
        assert "dev" in ctx["dev_dependencies"]
        assert "pytest>=8.0" in ctx["dev_dependencies"]["dev"]


# ── Rendering ────────────────────────────────────────────────────────────


class TestRenderReadme:
    def test_default_preset(self, tmp_path: Path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            textwrap.dedent("""\
            [project]
            name = "test-pkg"
            version = "1.0.0"
            description = "A test"
            license = "MIT"
        """)
        )

        md = render_readme(tmp_path)
        assert "# test-pkg" in md
        assert "A test" in md
        assert "pip install test-pkg" in md
        assert "MIT" in md

    def test_minimal_preset(self, tmp_path: Path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            textwrap.dedent("""\
            [project]
            name = "tiny"
            version = "0.1.0"
            description = "Small"
            license = "MIT"
        """)
        )

        md = render_readme(tmp_path, preset="minimal")
        assert "# tiny" in md
        assert "Project Structure" not in md  # minimal has no tree section

    def test_context_overrides(self, tmp_path: Path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            textwrap.dedent("""\
            [project]
            name = "original"
            version = "1.0.0"
        """)
        )

        md = render_readme(tmp_path, context={"name": "overridden"})
        assert "# overridden" in md
        assert "# original" not in md

    def test_cli_preset_with_scripts(self, tmp_path: Path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            textwrap.dedent("""\
            [project]
            name = "my-tool"
            version = "1.0.0"

            [project.scripts]
            mytool = "my_tool.cli:main"
        """)
        )

        md = render_readme(tmp_path, preset="cli")
        assert "mytool --help" in md
        assert "mytool" in md

    def test_library_preset(self, tmp_path: Path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            textwrap.dedent("""\
            [project]
            name = "my-lib"
            version = "2.0.0"
            description = "A library"
            license = "Apache-2.0"

            [project.urls]
            Repository = "https://github.com/user/my-lib"
        """)
        )

        md = render_readme(tmp_path, preset="library")
        assert "# my-lib" in md
        assert "import my_lib" in md
        assert "Contributing" in md


# ── CLI ──────────────────────────────────────────────────────────────────


class TestCLI:
    def test_readme_help(self):
        from kida.cli import main

        with pytest.raises(SystemExit) as exc_info:
            main(["readme", "--help"])
        assert exc_info.value.code == 0

    def test_readme_json(self, tmp_path: Path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            textwrap.dedent("""\
            [project]
            name = "json-test"
            version = "1.0.0"
        """)
        )

        import io
        import sys

        from kida.cli import main

        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            rc = main(["readme", "--json", str(tmp_path)])
        finally:
            sys.stdout = old_stdout

        assert rc == 0
        data = json.loads(captured.getvalue())
        assert data["name"] == "json-test"

    def test_readme_output_file(self, tmp_path: Path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            textwrap.dedent("""\
            [project]
            name = "file-test"
            version = "1.0.0"
        """)
        )
        output = tmp_path / "README.md"

        from kida.cli import main

        rc = main(["readme", "-o", str(output), str(tmp_path)])
        assert rc == 0
        assert output.exists()
        content = output.read_text()
        assert "# file-test" in content

    def test_readme_set_override(self, tmp_path: Path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            textwrap.dedent("""\
            [project]
            name = "original"
            version = "1.0.0"
        """)
        )

        import io
        import sys

        from kida.cli import main

        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            rc = main(["readme", "--set", "name=Custom Name", "--preset", "minimal", str(tmp_path)])
        finally:
            sys.stdout = old_stdout

        assert rc == 0
        assert "# Custom Name" in captured.getvalue()
