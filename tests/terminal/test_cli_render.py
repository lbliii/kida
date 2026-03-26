"""Tests for the kida render CLI subcommand."""

import json

from kida.cli import main


class TestCliRender:
    def test_render_simple_template(self, tmp_path):
        tpl = tmp_path / "test.txt"
        tpl.write_text("Hello {{ name }}!")
        assert main(["render", str(tpl), "--data-str", '{"name": "world"}']) == 0

    def test_render_missing_file(self):
        assert main(["render", "/nonexistent/template.txt"]) == 2

    def test_render_invalid_json_data_str(self, tmp_path):
        tpl = tmp_path / "test.txt"
        tpl.write_text("Hello")
        assert main(["render", str(tpl), "--data-str", "not-json"]) == 2

    def test_render_with_data_file(self, tmp_path):
        tpl = tmp_path / "test.txt"
        tpl.write_text("{{ x }}")
        data = tmp_path / "data.json"
        data.write_text(json.dumps({"x": "hello"}))
        assert main(["render", str(tpl), "--data", str(data)]) == 0

    def test_render_invalid_data_file(self, tmp_path):
        tpl = tmp_path / "test.txt"
        tpl.write_text("{{ x }}")
        data = tmp_path / "bad.json"
        data.write_text("not json")
        assert main(["render", str(tpl), "--data", str(data)]) == 2

    def test_render_with_width(self, tmp_path):
        tpl = tmp_path / "test.txt"
        tpl.write_text("ok")
        assert main(["render", str(tpl), "--width", "40"]) == 0

    def test_render_with_color_none(self, tmp_path):
        tpl = tmp_path / "test.txt"
        tpl.write_text("ok")
        assert main(["render", str(tpl), "--color", "none"]) == 0

    def test_render_html_mode(self, tmp_path):
        tpl = tmp_path / "test.txt"
        tpl.write_text("<p>Hello</p>")
        assert main(["render", str(tpl), "--mode", "html"]) == 0

    def test_render_template_error(self, tmp_path):
        tpl = tmp_path / "test.txt"
        tpl.write_text("{{ undefined_var }}")
        assert main(["render", str(tpl)]) == 1

    def test_render_stream_flag(self, tmp_path):
        tpl = tmp_path / "test.txt"
        tpl.write_text("streaming {{ x }}")
        assert main(["render", str(tpl), "--stream", "--data-str", '{"x": "ok"}']) == 0
