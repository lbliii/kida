"""Tests for the modern-syntax example."""


class TestModernSyntaxApp:
    """Verify match, pipeline, null coalescing, and optional chaining."""

    # Pipeline operator
    def test_pipeline_upper(self, example_app) -> None:
        assert "ALICE" in example_app.complete_output
        assert "BOB" in example_app.minimal_output

    # Optional chaining + null coalescing
    def test_avatar_with_value(self, example_app) -> None:
        assert 'src="alice.png"' in example_app.complete_output

    def test_avatar_fallback(self, example_app) -> None:
        # user.profile is None, so ?. short-circuits and ?? provides default
        assert 'src="default.png"' in example_app.minimal_output

    # Pattern matching
    def test_match_active(self, example_app) -> None:
        assert "badge active" in example_app.complete_output
        assert "Active" in example_app.complete_output

    def test_match_pending(self, example_app) -> None:
        assert "badge pending" in example_app.minimal_output
        assert "Pending Verification" in example_app.minimal_output

    def test_match_wildcard(self, example_app) -> None:
        assert "badge other" in example_app.unknown_output
        assert "Archived" in example_app.unknown_output

    # Role matching
    def test_admin_role(self, example_app) -> None:
        assert "Full access" in example_app.complete_output

    def test_viewer_role(self, example_app) -> None:
        assert "Read-only" in example_app.minimal_output

    def test_editor_role(self, example_app) -> None:
        assert "Can edit content" in example_app.unknown_output
