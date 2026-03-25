"""Tests for kida.analysis.a11y accessibility linting."""

from __future__ import annotations

from kida import Environment
from kida.analysis.a11y import check_a11y


def _get_issues(source: str):
    """Parse a template and run a11y checks on its AST."""
    env = Environment()
    tpl = env.from_string(source)
    return check_a11y(tpl._optimized_ast)


# ---------------------------------------------------------------------------
# img-alt
# ---------------------------------------------------------------------------


class TestImgAlt:
    def test_img_missing_alt(self):
        issues = _get_issues('<img src="photo.jpg">')
        assert len(issues) == 1
        assert issues[0].rule == "img-alt"
        assert issues[0].severity == "error"

    def test_img_with_alt(self):
        issues = _get_issues('<img src="photo.jpg" alt="A photo">')
        assert not any(i.rule == "img-alt" for i in issues)

    def test_img_with_empty_alt_passes(self):
        """Empty alt is valid (decorative image with explicit alt="")."""
        issues = _get_issues('<img src="spacer.gif" alt="">')
        assert not any(i.rule == "img-alt" for i in issues)

    def test_img_decorative_role_presentation(self):
        """role="presentation" suppresses img-alt."""
        issues = _get_issues('<img src="bg.jpg" role="presentation">')
        assert not any(i.rule == "img-alt" for i in issues)

    def test_img_decorative_role_none(self):
        """role="none" suppresses img-alt."""
        issues = _get_issues('<img src="bg.jpg" role="none">')
        assert not any(i.rule == "img-alt" for i in issues)

    def test_multiple_imgs_one_missing(self):
        issues = _get_issues('<img src="a.jpg" alt="A"><img src="b.jpg">')
        alt_issues = [i for i in issues if i.rule == "img-alt"]
        assert len(alt_issues) == 1

    def test_self_closing_img(self):
        issues = _get_issues('<img src="photo.jpg" />')
        assert len(issues) == 1
        assert issues[0].rule == "img-alt"


# ---------------------------------------------------------------------------
# heading-order
# ---------------------------------------------------------------------------


class TestHeadingOrder:
    def test_sequential_headings_ok(self):
        issues = _get_issues("<h1>Title</h1><h2>Sub</h2><h3>Detail</h3>")
        assert not any(i.rule == "heading-order" for i in issues)

    def test_skip_h1_to_h3(self):
        issues = _get_issues("<h1>Title</h1><h3>Oops</h3>")
        heading_issues = [i for i in issues if i.rule == "heading-order"]
        assert len(heading_issues) == 1
        assert "<h3>" in heading_issues[0].message
        assert "<h1>" in heading_issues[0].message

    def test_skip_h2_to_h5(self):
        issues = _get_issues("<h1>A</h1><h2>B</h2><h5>C</h5>")
        heading_issues = [i for i in issues if i.rule == "heading-order"]
        assert len(heading_issues) == 1

    def test_descending_headings_ok(self):
        """Going from h3 back to h1 is fine (only skipping forward matters)."""
        issues = _get_issues("<h1>A</h1><h2>B</h2><h3>C</h3><h1>D</h1>")
        assert not any(i.rule == "heading-order" for i in issues)


# ---------------------------------------------------------------------------
# html-lang
# ---------------------------------------------------------------------------


class TestHtmlLang:
    def test_html_missing_lang(self):
        issues = _get_issues("<html><head></head></html>")
        lang_issues = [i for i in issues if i.rule == "html-lang"]
        assert len(lang_issues) == 1

    def test_html_with_lang(self):
        issues = _get_issues('<html lang="en"><head></head></html>')
        assert not any(i.rule == "html-lang" for i in issues)

    def test_no_html_tag(self):
        """Templates without <html> should not trigger html-lang."""
        issues = _get_issues("<div>Hello</div>")
        assert not any(i.rule == "html-lang" for i in issues)


# ---------------------------------------------------------------------------
# input-label
# ---------------------------------------------------------------------------


class TestInputLabel:
    def test_input_without_label(self):
        issues = _get_issues('<input type="text" id="name">')
        label_issues = [i for i in issues if i.rule == "input-label"]
        assert len(label_issues) == 1

    def test_input_with_matching_label(self):
        issues = _get_issues('<label for="name">Name</label><input type="text" id="name">')
        assert not any(i.rule == "input-label" for i in issues)

    def test_input_with_aria_label(self):
        issues = _get_issues('<input type="text" aria-label="Search">')
        assert not any(i.rule == "input-label" for i in issues)

    def test_input_with_aria_labelledby(self):
        issues = _get_issues('<input type="text" aria-labelledby="heading1">')
        assert not any(i.rule == "input-label" for i in issues)

    def test_hidden_input_skipped(self):
        issues = _get_issues('<input type="hidden" name="csrf">')
        assert not any(i.rule == "input-label" for i in issues)

    def test_input_with_title(self):
        issues = _get_issues('<input type="text" title="Enter name">')
        assert not any(i.rule == "input-label" for i in issues)

    def test_select_without_label(self):
        issues = _get_issues('<select id="color"><option>Red</option></select>')
        label_issues = [i for i in issues if i.rule == "input-label"]
        assert len(label_issues) == 1

    def test_textarea_without_label(self):
        issues = _get_issues('<textarea id="bio"></textarea>')
        label_issues = [i for i in issues if i.rule == "input-label"]
        assert len(label_issues) == 1

    def test_input_no_id_no_aria(self):
        """Input with no id and no aria-label should flag."""
        issues = _get_issues('<input type="text">')
        label_issues = [i for i in issues if i.rule == "input-label"]
        assert len(label_issues) == 1


# ---------------------------------------------------------------------------
# Clean markup
# ---------------------------------------------------------------------------


class TestCleanMarkup:
    def test_fully_accessible_page(self):
        source = (
            '<html lang="en">'
            "<head><title>Test</title></head>"
            "<body>"
            "<h1>Main Title</h1>"
            '<img src="photo.jpg" alt="A nice photo">'
            "<h2>Section</h2>"
            '<label for="email">Email</label>'
            '<input type="text" id="email">'
            "</body></html>"
        )
        issues = _get_issues(source)
        assert issues == []

    def test_empty_template(self):
        issues = _get_issues("")
        assert issues == []

    def test_template_with_only_expressions(self):
        """Dynamic content ({{ }}) should not produce a11y issues."""
        issues = _get_issues("{{ title }}{{ body }}")
        assert issues == []
