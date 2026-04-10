"""Tests for i18n message extraction, analysis integration, and CLI tooling."""

import io
from pathlib import Path

import pytest

from kida import Environment
from kida.analysis.dependencies import DependencyWalker
from kida.analysis.i18n import ExtractedMessage, ExtractMessagesVisitor
from kida.analysis.purity import PurityAnalyzer
from kida.lexer import tokenize
from kida.parser import Parser


def _parse(source: str, name: str = "<test>") -> object:
    """Parse a template string and return the AST."""
    tokens = tokenize(source)
    return Parser(tokens, name, None, source).parse()


class TestExtractTransBlocks:
    """Extract messages from {% trans %} blocks."""

    def test_simple_trans(self) -> None:
        ast = _parse("{% trans %}Hello{% endtrans %}")
        msgs = ExtractMessagesVisitor("index.html").extract(ast)
        assert len(msgs) == 1
        assert msgs[0] == ExtractedMessage(
            filename="index.html",
            lineno=1,
            function="gettext",
            message="Hello",
        )

    def test_trans_with_variables(self) -> None:
        ast = _parse("{% trans name=user %}Hello, {{ name }}!{% endtrans %}")
        msgs = ExtractMessagesVisitor("index.html").extract(ast)
        assert len(msgs) == 1
        assert msgs[0].function == "gettext"
        assert msgs[0].message == "Hello, %(name)s!"

    def test_plural(self) -> None:
        ast = _parse("{% trans count=n %}One item.{% plural %}{{ count }} items.{% endtrans %}")
        msgs = ExtractMessagesVisitor("test.html").extract(ast)
        assert len(msgs) == 1
        assert msgs[0].function == "ngettext"
        assert msgs[0].message == ("One item.", "%(count)s items.")

    def test_whitespace_normalized(self) -> None:
        ast = _parse("{% trans %}\n  Hello,\n  world!\n{% endtrans %}")
        msgs = ExtractMessagesVisitor().extract(ast)
        assert msgs[0].message == "Hello, world!"

    def test_correct_lineno(self) -> None:
        ast = _parse("line one\n{% trans %}Hello{% endtrans %}")
        msgs = ExtractMessagesVisitor().extract(ast)
        assert msgs[0].lineno == 2

    def test_multiple_trans_blocks(self) -> None:
        ast = _parse("{% trans %}Hello{% endtrans %} {% trans %}Goodbye{% endtrans %}")
        msgs = ExtractMessagesVisitor().extract(ast)
        assert len(msgs) == 2
        assert msgs[0].message == "Hello"
        assert msgs[1].message == "Goodbye"


class TestExtractShorthand:
    """Extract messages from _() and _n() function calls."""

    def test_gettext_shorthand(self) -> None:
        ast = _parse('{{ _("Hello, world!") }}')
        msgs = ExtractMessagesVisitor("t.html").extract(ast)
        assert len(msgs) == 1
        assert msgs[0].function == "gettext"
        assert msgs[0].message == "Hello, world!"

    def test_ngettext_shorthand(self) -> None:
        ast = _parse('{{ _n("item", "items", n) }}')
        msgs = ExtractMessagesVisitor().extract(ast)
        assert len(msgs) == 1
        assert msgs[0].function == "ngettext"
        assert msgs[0].message == ("item", "items")

    def test_non_constant_argument_skipped(self) -> None:
        """_(variable) cannot be extracted — silently skipped."""
        ast = _parse("{{ _(msg) }}")
        msgs = ExtractMessagesVisitor().extract(ast)
        assert len(msgs) == 0

    def test_non_string_constant_skipped(self) -> None:
        """_(42) is not a valid message — skipped."""
        ast = _parse("{{ _(42) }}")
        msgs = ExtractMessagesVisitor().extract(ast)
        assert len(msgs) == 0

    def test_ngettext_non_constant_skipped(self) -> None:
        """_n(var1, var2, n) cannot be extracted — skipped."""
        ast = _parse("{{ _n(s, p, n) }}")
        msgs = ExtractMessagesVisitor().extract(ast)
        assert len(msgs) == 0


class TestExtractMixed:
    """Extract messages from templates with both trans blocks and shorthands."""

    def test_mixed_extraction(self) -> None:
        ast = _parse('{% trans %}Welcome{% endtrans %} {{ _("Login") }}')
        msgs = ExtractMessagesVisitor("page.html").extract(ast)
        assert len(msgs) == 2
        assert msgs[0].message == "Welcome"
        assert msgs[1].message == "Login"

    def test_trans_inside_for_loop(self) -> None:
        ast = _parse(
            "{% for x in items %}{% trans name=x %}Hello, {{ name }}!{% endtrans %}{% end %}"
        )
        msgs = ExtractMessagesVisitor().extract(ast)
        assert len(msgs) == 1
        assert msgs[0].message == "Hello, %(name)s!"

    def test_default_filename(self) -> None:
        ast = _parse("{% trans %}Hi{% endtrans %}")
        msgs = ExtractMessagesVisitor().extract(ast)
        assert msgs[0].filename == "<template>"

    def test_custom_filename(self) -> None:
        ast = _parse("{% trans %}Hi{% endtrans %}")
        msgs = ExtractMessagesVisitor("templates/base.html").extract(ast)
        assert msgs[0].filename == "templates/base.html"

    def test_empty_template(self) -> None:
        ast = _parse("Hello, no translations here.")
        msgs = ExtractMessagesVisitor().extract(ast)
        assert len(msgs) == 0

    def test_reuse_visitor(self) -> None:
        """Calling extract() resets state — no message leakage between calls."""
        visitor = ExtractMessagesVisitor()
        ast1 = _parse("{% trans %}First{% endtrans %}")
        ast2 = _parse("{% trans %}Second{% endtrans %}")
        msgs1 = visitor.extract(ast1)
        msgs2 = visitor.extract(ast2)
        assert len(msgs1) == 1
        assert msgs1[0].message == "First"
        assert len(msgs2) == 1
        assert msgs2[0].message == "Second"


class TestNestedTransRejection:
    """Parser rejects nested {% trans %} blocks."""

    def test_nested_trans_raises(self) -> None:
        with pytest.raises(Exception, match="Unexpected block tag"):
            _parse("{% trans %}{% trans %}Hello{% end %}{% end %}")

    def test_trans_inside_trans_with_endtrans(self) -> None:
        with pytest.raises(Exception, match="Unexpected block tag"):
            _parse("{% trans %}{% trans %}Hello{% endtrans %}{% endtrans %}")


class TestCLIExtract:
    """Tests for the ``kida extract`` CLI subcommand."""

    def test_extract_to_stdout(self, tmp_path: Path) -> None:
        (tmp_path / "page.html").write_text("{% trans %}Welcome{% endtrans %}", encoding="utf-8")
        import io
        import sys

        from kida.cli import main

        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            rc = main(["extract", str(tmp_path)])
        finally:
            sys.stdout = old_stdout

        assert rc == 0
        pot = captured.getvalue()
        assert 'msgid "Welcome"' in pot
        assert 'msgstr ""' in pot

    def test_extract_to_file(self, tmp_path: Path) -> None:
        (tmp_path / "page.html").write_text(
            '{% trans %}Hello{% endtrans %} {{ _("World") }}', encoding="utf-8"
        )
        out_file = tmp_path / "messages.pot"
        from kida.cli import main

        rc = main(["extract", str(tmp_path), "-o", str(out_file)])
        assert rc == 0
        assert out_file.exists()
        pot = out_file.read_text(encoding="utf-8")
        assert 'msgid "Hello"' in pot
        assert 'msgid "World"' in pot

    def test_extract_plural(self, tmp_path: Path) -> None:
        (tmp_path / "page.html").write_text(
            "{% trans count=n %}One.{% plural %}{{ count }} items.{% endtrans %}",
            encoding="utf-8",
        )
        import io
        import sys

        from kida.cli import main

        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            rc = main(["extract", str(tmp_path)])
        finally:
            sys.stdout = old_stdout

        assert rc == 0
        pot = captured.getvalue()
        assert 'msgid "One."' in pot
        assert 'msgid_plural "%(count)s items."' in pot
        assert 'msgstr[0] ""' in pot
        assert 'msgstr[1] ""' in pot

    def test_extract_empty_dir(self, tmp_path: Path) -> None:
        import io
        import sys

        from kida.cli import main

        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            rc = main(["extract", str(tmp_path)])
        finally:
            sys.stdout = old_stdout

        assert rc == 0
        pot = captured.getvalue()
        # Header present but no messages
        assert "msgid" in pot
        assert pot.count("\nmsgid ") == 1  # only the empty header msgid

    def test_extract_not_a_directory(self, tmp_path: Path) -> None:
        from kida.cli import main

        rc = main(["extract", str(tmp_path / "nonexistent")])
        assert rc == 2

    def test_extract_custom_extension(self, tmp_path: Path) -> None:
        (tmp_path / "email.txt").write_text("{% trans %}Greetings{% endtrans %}", encoding="utf-8")
        import io
        import sys

        from kida.cli import main

        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            rc = main(["extract", str(tmp_path), "--ext", ".txt"])
        finally:
            sys.stdout = old_stdout

        assert rc == 0
        assert 'msgid "Greetings"' in captured.getvalue()

    def test_extract_ext_without_dot(self, tmp_path: Path) -> None:
        """--ext txt (no dot) should be normalized to .txt."""
        (tmp_path / "email.txt").write_text("{% trans %}Hi{% endtrans %}", encoding="utf-8")
        import io
        import sys

        from kida.cli import main

        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            rc = main(["extract", str(tmp_path), "--ext", "txt"])
        finally:
            sys.stdout = old_stdout

        assert rc == 0
        assert 'msgid "Hi"' in captured.getvalue()


class TestBabelExtractor:
    """Tests for the Babel extractor plugin."""

    def test_extract_simple(self) -> None:
        from kida.babel import extract

        source = b"{% trans %}Hello{% endtrans %}"
        fileobj = io.BytesIO(source)
        fileobj.name = "test.html"  # type: ignore[attr-defined]
        results = list(extract(fileobj, [], [], {}))
        assert len(results) == 1
        lineno, func, message, comments = results[0]
        assert lineno == 1
        assert func == "gettext"
        assert message == "Hello"
        assert comments == []

    def test_extract_plural(self) -> None:
        from kida.babel import extract

        source = b"{% trans count=n %}One.{% plural %}{{ count }} many.{% endtrans %}"
        fileobj = io.BytesIO(source)
        fileobj.name = "test.html"  # type: ignore[attr-defined]
        results = list(extract(fileobj, [], [], {}))
        assert len(results) == 1
        assert results[0][1] == "ngettext"
        assert results[0][2] == ("One.", "%(count)s many.")

    def test_extract_shorthand(self) -> None:
        from kida.babel import extract

        source = b'{{ _("Login") }}'
        fileobj = io.BytesIO(source)
        fileobj.name = "test.html"  # type: ignore[attr-defined]
        results = list(extract(fileobj, [], [], {}))
        assert len(results) == 1
        assert results[0][2] == "Login"

    def test_extract_encoding(self) -> None:
        from kida.babel import extract

        source = "{% trans %}Héllo{% endtrans %}".encode("latin-1")
        fileobj = io.BytesIO(source)
        fileobj.name = "test.html"  # type: ignore[attr-defined]
        results = list(extract(fileobj, [], [], {"encoding": "latin-1"}))
        assert len(results) == 1
        assert results[0][2] == "Héllo"

    def test_extract_multiple(self) -> None:
        from kida.babel import extract

        source = b'{% trans %}A{% endtrans %} {% trans %}B{% endtrans %} {{ _("C") }}'
        fileobj = io.BytesIO(source)
        fileobj.name = "test.html"  # type: ignore[attr-defined]
        results = list(extract(fileobj, [], [], {}))
        assert len(results) == 3
        assert [r[2] for r in results] == ["A", "B", "C"]


class TestDependencyAnalysis:
    """DependencyWalker finds variables inside trans blocks."""

    def test_trans_with_variables(self) -> None:
        ast = _parse("{% trans name=user.display_name %}Hello, {{ name }}!{% endtrans %}")
        deps = DependencyWalker().analyze(ast)
        assert "user.display_name" in deps

    def test_trans_count_expr(self) -> None:
        ast = _parse(
            "{% trans count=items|length %}One.{% plural %}{{ count }} items.{% endtrans %}"
        )
        deps = DependencyWalker().analyze(ast)
        assert "items" in deps

    def test_trans_multiple_vars(self) -> None:
        ast = _parse(
            "{% trans name=user, count=total %}Hello, {{ name }}! {{ count }} items.{% endtrans %}"
        )
        deps = DependencyWalker().analyze(ast)
        assert "user" in deps
        assert "total" in deps

    def test_simple_trans_no_deps(self) -> None:
        ast = _parse("{% trans %}Hello{% endtrans %}")
        deps = DependencyWalker().analyze(ast)
        assert len(deps) == 0


class TestPurityAnalysis:
    """PurityAnalyzer marks trans blocks as impure."""

    def test_trans_is_impure(self) -> None:
        ast = _parse("{% trans %}Hello{% endtrans %}")
        purity = PurityAnalyzer().analyze(ast)
        assert purity == "impure"

    def test_trans_with_variables_is_impure(self) -> None:
        ast = _parse("{% trans name=user %}Hello, {{ name }}!{% endtrans %}")
        purity = PurityAnalyzer().analyze(ast)
        assert purity == "impure"

    def test_trans_plural_is_impure(self) -> None:
        ast = _parse("{% trans count=n %}One.{% plural %}{{ count }} many.{% endtrans %}")
        purity = PurityAnalyzer().analyze(ast)
        assert purity == "impure"


class TestOptimizeTranslations:
    """optimize_translations compiles constant trans to direct appends."""

    def test_optimized_simple_trans(self) -> None:
        env = Environment(optimize_translations=True)
        tmpl = env.from_string("{% trans %}Hello{% endtrans %}")
        assert tmpl.render() == "Hello"

    def test_optimized_ignores_late_translations(self) -> None:
        """Optimized trans blocks bypass gettext — late translations don't apply."""
        env = Environment(optimize_translations=True)
        tmpl = env.from_string("{% trans %}Hello{% endtrans %}")
        env.install_gettext_callables(
            gettext=lambda s: "Bonjour" if s == "Hello" else s,
            ngettext=lambda s, p, n: s if n == 1 else p,
        )
        # Optimization compiled to direct append — gettext is never called
        assert tmpl.render() == "Hello"

    def test_optimized_does_not_affect_variables(self) -> None:
        """Trans blocks with variables still use gettext (not optimized)."""
        env = Environment(optimize_translations=True)
        env.install_gettext_callables(
            gettext=lambda s: "Bonjour, %(name)s!" if "%(name)s" in s else s,
            ngettext=lambda s, p, n: s if n == 1 else p,
        )
        tmpl = env.from_string("{% trans name=user %}Hello, {{ name }}!{% endtrans %}")
        assert tmpl.render(user="Alice") == "Bonjour, Alice!"

    def test_optimized_does_not_affect_plural(self) -> None:
        """Trans blocks with plural still use ngettext (not optimized)."""
        env = Environment(optimize_translations=True)
        tmpl = env.from_string(
            "{% trans count=n %}One.{% plural %}{{ count }} items.{% endtrans %}"
        )
        assert tmpl.render(n=1) == "One."
        assert tmpl.render(n=5) == "5 items."

    def test_not_optimized_by_default(self) -> None:
        """Without optimize_translations, gettext is called at render time."""
        env = Environment()
        tmpl = env.from_string("{% trans %}Hello{% endtrans %}")
        env.install_gettext_callables(
            gettext=lambda s: "Bonjour" if s == "Hello" else s,
            ngettext=lambda s, p, n: s if n == 1 else p,
        )
        # Late-binding works when not optimized
        assert tmpl.render() == "Bonjour"
