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
    annotate_tree,
    collapse_tree,
    detect_preset,
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


# ── Annotated tree ───────────────────────────────────────────────────────


class TestAnnotateTree:
    def test_annotates_python_package(self, tmp_path: Path):
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""My cool package."""\n')

        tree = walk_tree(tmp_path, depth=2)
        annotate_tree(tmp_path, tree)
        assert tree["mypkg"]["__annotation__"] == "My cool package"

    def test_annotates_python_file(self, tmp_path: Path):
        (tmp_path / "helper.py").write_text('"""Utility functions."""\n')

        tree = walk_tree(tmp_path, depth=1)
        annotate_tree(tmp_path, tree)
        # File annotations stored as string values
        assert tree["helper.py"] == "Utility functions"

    def test_no_docstring_no_annotation(self, tmp_path: Path):
        (tmp_path / "empty.py").write_text("x = 1\n")

        tree = walk_tree(tmp_path, depth=1)
        annotate_tree(tmp_path, tree)
        assert tree["empty.py"] is None

    def test_non_python_files_not_annotated(self, tmp_path: Path):
        (tmp_path / "data.json").write_text("{}\n")

        tree = walk_tree(tmp_path, depth=1)
        annotate_tree(tmp_path, tree)
        assert tree["data.json"] is None

    def test_recurses_into_subdirectories(self, tmp_path: Path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "__init__.py").write_text('"""Sub package."""\n')
        inner = sub / "inner"
        inner.mkdir()
        (inner / "__init__.py").write_text('"""Inner package."""\n')

        tree = walk_tree(tmp_path, depth=3)
        annotate_tree(tmp_path, tree)
        assert tree["sub"]["__annotation__"] == "Sub package"
        assert tree["sub"]["inner"]["__annotation__"] == "Inner package"


# ── Collapse tree ────────────────────────────────────────────────────────


class TestCollapseTree:
    def test_collapses_large_directory(self):
        children = {f"file{i}.py": None for i in range(20)}
        children["subdir"] = {"a.py": None}
        tree = {"big": children}

        result = collapse_tree(tree)
        keys = list(result["big"].keys())
        assert "subdir" in keys
        assert any("... and" in k for k in keys)

    def test_preserves_small_directory(self):
        tree = {"small": {"a.py": None, "b.py": None}}
        result = collapse_tree(tree)
        assert "a.py" in result["small"]
        assert "b.py" in result["small"]

    def test_preserves_annotations_through_collapse(self):
        children = {f"file{i}.py": None for i in range(20)}
        children["__annotation__"] = "Big dir"
        tree = {"big": children}

        result = collapse_tree(tree)
        assert result["big"]["__annotation__"] == "Big dir"


# ── Auto-preset detection ────────────────────────────────────────────────


class TestDetectPreset:
    def test_cli_when_has_scripts(self):
        assert detect_preset({"has_cli": True, "dependencies": []}) == "cli"

    def test_library_when_has_deps(self):
        assert detect_preset({"has_cli": False, "dependencies": ["requests"]}) == "library"

    def test_default_otherwise(self):
        assert detect_preset({"has_cli": False, "dependencies": []}) == "default"

    def test_cli_takes_priority_over_deps(self):
        assert detect_preset({"has_cli": True, "dependencies": ["click"]}) == "cli"


# ── Enriched context ─────────────────────────────────────────────────────


class TestEnrichedContext:
    def test_has_zero_deps(self, tmp_path: Path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            textwrap.dedent("""\
            [project]
            name = "pure"
            version = "1.0.0"
            dependencies = []
        """)
        )

        ctx = detect_project(tmp_path)
        assert ctx["has_zero_deps"] is True

    def test_has_extras(self, tmp_path: Path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            textwrap.dedent("""\
            [project]
            name = "extras-pkg"
            version = "1.0.0"

            [project.optional-dependencies]
            perf = ["markupsafe"]
            docs = ["sphinx"]
        """)
        )

        ctx = detect_project(tmp_path)
        assert "perf" in ctx["extras"]
        assert ctx["extras"]["perf"] == ["markupsafe"]

    def test_suggested_preset_in_context(self, tmp_path: Path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            textwrap.dedent("""\
            [project]
            name = "my-cli"
            version = "1.0.0"

            [project.scripts]
            mycli = "my_cli:main"
        """)
        )

        ctx = detect_project(tmp_path)
        assert ctx["suggested_preset"] == "cli"

    def test_keywords_in_context(self, tmp_path: Path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            textwrap.dedent("""\
            [project]
            name = "kw-pkg"
            version = "1.0.0"
            keywords = ["fast", "template"]
        """)
        )

        ctx = detect_project(tmp_path)
        assert ctx["keywords"] == ["fast", "template"]


# ── Render tree with annotations ─────────────────────────────────────────


class TestRenderTreeAnnotated:
    def test_file_annotation_in_output(self):
        tree = {"helper.py": "Utility functions", "main.py": None}
        result = _render_tree(tree)
        assert "helper.py  # Utility functions" in result
        assert "main.py" in result
        assert "main.py  #" not in result

    def test_directory_annotation_in_output(self):
        tree = {"pkg": {"__annotation__": "My package", "mod.py": None}}
        result = _render_tree(tree)
        assert "pkg/  # My package" in result
        assert "mod.py" in result

    def test_no_trailing_slash_on_files(self):
        tree = {"file.txt": None, "annotated.py": "A module"}
        result = _render_tree(tree)
        assert "file.txt" in result
        assert "file.txt/" not in result
        assert "annotated.py/" not in result
