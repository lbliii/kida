"""Tests for the template introspection example."""


class TestIntrospectionApp:
    """Verify template analysis API returns meaningful metadata."""

    def test_required_context_has_expected_vars(self, example_app) -> None:
        required = example_app.required
        assert "page" in required
        assert "site_name" in required

    def test_block_metadata_returns_known_blocks(self, example_app) -> None:
        blocks = example_app.block_meta
        assert "title" in blocks
        assert "content" in blocks

    def test_validate_context_detects_missing(self, example_app) -> None:
        assert len(example_app.missing_vars) > 0

    def test_validate_context_passes_complete(self, example_app) -> None:
        assert example_app.no_missing == []

    def test_depends_on_returns_paths(self, example_app) -> None:
        deps = example_app.deps
        assert len(deps) > 0
        # Should contain dotted paths like page.title
        assert any("." in d for d in deps)

    def test_template_metadata_shows_extends(self, example_app) -> None:
        meta = example_app.meta
        assert meta is not None
        assert meta.extends == "base.html"

    def test_template_metadata_all_dependencies(self, example_app) -> None:
        meta = example_app.meta
        assert meta is not None
        all_deps = meta.all_dependencies()
        assert len(all_deps) > 0

    def test_output_is_populated(self, example_app) -> None:
        assert "Required context" in example_app.output
        assert "Extends" in example_app.output
