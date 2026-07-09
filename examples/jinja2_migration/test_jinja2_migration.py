"""Tests for the jinja2_migration example."""


def _normalize(html: str) -> str:
    """Normalize whitespace for comparison."""
    return " ".join(html.split())


class TestJinja2MigrationApp:
    """Verify Kida and Jinja2 produce equivalent output."""

    def test_full_context_both_render_active_badge(self, example_app) -> None:
        assert "badge active" in example_app.kida_output_full
        assert "badge active" in example_app.jinja2_output_full
        assert "Alice" in example_app.kida_output_full
        assert "Alice" in example_app.jinja2_output_full

    def test_minimal_context_both_render_pending_badge(self, example_app) -> None:
        assert "badge pending" in example_app.kida_output_minimal
        assert "badge pending" in example_app.jinja2_output_minimal
        assert "Bob" in example_app.kida_output_minimal
        assert "Bob" in example_app.jinja2_output_minimal

    def test_empty_context_both_render_unknown_badge(self, example_app) -> None:
        assert "badge unknown" in example_app.kida_output_empty
        assert "badge unknown" in example_app.jinja2_output_empty

    def test_full_context_structurally_equivalent(self, example_app) -> None:
        kida_norm = _normalize(example_app.kida_output_full)
        jinja2_norm = _normalize(example_app.jinja2_output_full)
        # Same structure: active badge, user name, bio
        assert "Active" in kida_norm
        assert "Active" in jinja2_norm
        assert "Alice" in kida_norm
        assert "Alice" in jinja2_norm
        assert "Developer" in kida_norm
        assert "Developer" in jinja2_norm

    def test_matching_explicit_closers_are_a_migration_noop(self, example_app) -> None:
        source = example_app.SHARED_EXPLICIT_CLOSERS

        assert "{% endif %}" in source
        assert "{% endfor %}" in source
        assert "{% endblock %}" in source
        assert _normalize(example_app.shared_kida_output) == _normalize(
            example_app.shared_jinja2_output
        )
        assert "Visible" in example_app.shared_kida_output
        assert "Hidden" not in example_app.shared_kida_output
