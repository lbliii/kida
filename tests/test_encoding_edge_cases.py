"""Encoding edge case tests for template source.

Tests invalid UTF-8, BOM, mixed encodings, and null bytes in template source.
Ensures Kida handles pathological or malformed input safely.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kida import Environment
from kida.environment.loaders import FileSystemLoader

if TYPE_CHECKING:
    from pathlib import Path


class TestFromStringEncoding:
    """from_string with edge-case source strings."""

    def test_bom_at_start_compiles_and_renders(self) -> None:
        """BOM (U+FEFF) at start is preserved in output."""
        env = Environment()
        tmpl = env.from_string("\ufeffHello {{ x }}")
        result = tmpl.render(x="World")
        assert result == "\ufeffHello World"

    def test_nul_bytes_in_source_preserved(self) -> None:
        """NUL bytes in template source pass through."""
        env = Environment()
        tmpl = env.from_string("\x00Hello\x00")
        result = tmpl.render()
        assert result == "\x00Hello\x00"

    def test_surrogate_in_source_preserved(self) -> None:
        """Lone surrogate (invalid Unicode) passes through without crash."""
        env = Environment()
        tmpl = env.from_string("\udc00")
        result = tmpl.render()
        assert result == "\udc00"

    def test_mixed_unicode_scripts(self) -> None:
        """Mixed scripts (Latin, CJK, emoji) render correctly."""
        env = Environment()
        source = "Latin: {{ a }} | 中文: {{ b }} | \U0001f600"
        tmpl = env.from_string(source)
        result = tmpl.render(a="A", b="B")
        assert "Latin: A" in result
        assert "中文: B" in result
        assert "\U0001f600" in result

    def test_replacement_char_from_bad_decode(self) -> None:
        """U+FFFD (replacement char) from bad UTF-8 decode passes through."""
        env = Environment()
        # Simulate what read_text(encoding='utf-8', errors='replace') produces
        bad = b"\xff\xfe".decode("utf-8", errors="replace")
        tmpl = env.from_string(f"x{bad}y")
        result = tmpl.render()
        assert "x" in result and "y" in result
        assert "\ufffd" in result


class TestFileSystemLoaderEncoding:
    """FileSystemLoader with encoding edge cases."""

    def test_invalid_utf8_raises_unicodedecodeerror(self, tmp_path: Path) -> None:
        """File with invalid UTF-8 bytes raises UnicodeDecodeError."""
        path = tmp_path / "bad.html"
        path.write_bytes(b"Hello \xff\xfe world")  # Invalid UTF-8
        loader = FileSystemLoader(tmp_path, encoding="utf-8")
        env = Environment(loader=loader)
        with pytest.raises(UnicodeDecodeError):
            env.get_template("bad.html")

    def test_valid_utf8_with_bom_loads(self, tmp_path: Path) -> None:
        """File with UTF-8 BOM loads and renders."""
        path = tmp_path / "bom.html"
        path.write_text("\ufeff{{ x }}", encoding="utf-8")
        loader = FileSystemLoader(tmp_path)
        env = Environment(loader=loader)
        tmpl = env.get_template("bom.html")
        result = tmpl.render(x="ok")
        assert "\ufeff" in result
        assert "ok" in result

    def test_latin1_encoding_loads(self, tmp_path: Path) -> None:
        """File with Latin-1 encoding loads when specified."""
        path = tmp_path / "latin1.html"
        path.write_bytes(b"Gr\xfc\xdfe {{ x }}")  # Grüße in Latin-1
        loader = FileSystemLoader(tmp_path, encoding="iso-8859-1")
        env = Environment(loader=loader)
        tmpl = env.get_template("latin1.html")
        result = tmpl.render(x="World")
        assert "Grüße" in result or "Gr\xfc\xdfe" in result
        assert "World" in result

    def test_nul_bytes_in_file_loads(self, tmp_path: Path) -> None:
        """File with NUL bytes loads (valid in UTF-8)."""
        path = tmp_path / "nul.html"
        path.write_bytes(b"Hello\x00World")
        loader = FileSystemLoader(tmp_path)
        env = Environment(loader=loader)
        tmpl = env.get_template("nul.html")
        result = tmpl.render()
        assert "\x00" in result
        assert "Hello" in result and "World" in result
