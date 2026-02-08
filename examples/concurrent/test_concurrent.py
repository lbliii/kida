"""Tests for the concurrent rendering example."""


class TestConcurrentApp:
    """Verify 8 threads render correctly without cross-contamination."""

    def test_all_pages_rendered(self, example_app) -> None:
        assert len(example_app.results) == 8

    def test_each_page_has_correct_id(self, example_app) -> None:
        for i, html in enumerate(example_app.results):
            assert f'id="page-{i}"' in html

    def test_each_page_has_correct_title(self, example_app) -> None:
        for i, html in enumerate(example_app.results):
            assert f"Page {i}" in html

    def test_no_cross_contamination(self, example_app) -> None:
        """Each page should only contain its own tags, not another page's."""
        for i, html in enumerate(example_app.results):
            assert f"tag-{i}-a" in html
            assert f"tag-{i}-b" in html
            # Verify no tags from other pages leaked in
            for j in range(8):
                if j != i:
                    assert f"tag-{j}-a" not in html

    def test_results_are_distinct(self, example_app) -> None:
        unique = set(example_app.results)
        assert len(unique) == 8

    def test_output_contains_all_pages(self, example_app) -> None:
        for i in range(8):
            assert f"Page {i}" in example_app.output
