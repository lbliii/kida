from kida.formatter import format_template

# --- Default settings ---


def test_format_empty_string() -> None:
    assert format_template("") == ""


def test_format_plain_text_unchanged() -> None:
    assert format_template("Hello world\n") == "Hello world\n"


def test_format_returns_string() -> None:
    result = format_template("<div>{{ name }}</div>")
    assert isinstance(result, str)


# --- Tag spacing normalization ---


def test_normalize_block_tag_spacing() -> None:
    assert format_template("{%if x%}\n") == "{% if x %}\n"


def test_normalize_block_tag_extra_spaces() -> None:
    assert format_template("{%  if x  %}\n") == "{% if x %}\n"


def test_normalize_var_tag_spacing() -> None:
    assert format_template("{{x}}\n") == "{{ x }}\n"


def test_normalize_var_tag_extra_spaces() -> None:
    assert format_template("{{  x  }}\n") == "{{ x }}\n"


def test_normalize_comment_tag_spacing() -> None:
    assert format_template("{#note#}\n") == "{# note #}\n"


def test_normalize_comment_tag_extra_spaces() -> None:
    assert format_template("{#  note  #}\n") == "{# note #}\n"


def test_skip_tag_normalization_when_disabled() -> None:
    source = "{{x}}\n"
    result = format_template(source, normalize_tag_spacing=False)
    assert "{{x}}" in result


# --- Whitespace control markers ---


def test_block_tag_ws_strip_open() -> None:
    result = format_template("{%- if x %}\n")
    assert result == "{%- if x %}\n"


def test_block_tag_ws_strip_close() -> None:
    result = format_template("{% if x -%}\n")
    assert result == "{% if x -%}\n"


def test_block_tag_ws_strip_both() -> None:
    result = format_template("{%- if x -%}\n")
    assert result == "{%- if x -%}\n"


def test_var_tag_ws_strip_open() -> None:
    result = format_template("{{- x }}\n")
    assert result == "{{- x }}\n"


def test_var_tag_ws_strip_close() -> None:
    result = format_template("{{ x -}}\n")
    assert result == "{{ x -}}\n"


def test_comment_tag_ws_strip_both() -> None:
    result = format_template("{#- note -#}\n")
    assert result == "{#- note -#}\n"


# --- Auto-indentation of block bodies ---


def test_indent_if_block_body() -> None:
    source = "{% if x %}\nhello\n{% endif %}\n"
    expected = "{% if x %}\n  hello\n{% endif %}\n"
    assert format_template(source) == expected


def test_indent_for_block_body() -> None:
    source = "{% for i in items %}\n{{ i }}\n{% endfor %}\n"
    expected = "{% for i in items %}\n  {{ i }}\n{% endfor %}\n"
    assert format_template(source) == expected


def test_indent_block_tag() -> None:
    source = "{% block title %}\nHello\n{% endblock %}\n"
    expected = "{% block title %}\n  Hello\n{% endblock %}\n"
    assert format_template(source) == expected


def test_indent_with_block() -> None:
    source = "{% with x=1 %}\n{{ x }}\n{% endwith %}\n"
    expected = "{% with x=1 %}\n  {{ x }}\n{% endwith %}\n"
    assert format_template(source) == expected


def test_indent_custom_indent_size() -> None:
    source = "{% if x %}\nhello\n{% endif %}\n"
    expected = "{% if x %}\n    hello\n{% endif %}\n"
    assert format_template(source, indent=4) == expected


def test_nested_indentation() -> None:
    source = "{% if x %}\n{% for i in y %}\n{{ i }}\n{% endfor %}\n{% endif %}\n"
    expected = "{% if x %}\n  {% for i in y %}\n    {{ i }}\n  {% endfor %}\n{% endif %}\n"
    assert format_template(source) == expected


# --- Dedenting on end/continuation keywords ---


def test_dedent_on_endif() -> None:
    source = "{% if x %}\nhello\n{% endif %}\n"
    result = format_template(source)
    lines = result.strip().split("\n")
    assert lines[0] == "{% if x %}"
    assert lines[1] == "  hello"
    assert lines[2] == "{% endif %}"


def test_dedent_on_else() -> None:
    source = "{% if x %}\na\n{% else %}\nb\n{% endif %}\n"
    expected = "{% if x %}\n  a\n{% else %}\n  b\n{% endif %}\n"
    assert format_template(source) == expected


def test_dedent_on_elif() -> None:
    source = "{% if x %}\na\n{% elif y %}\nb\n{% endif %}\n"
    expected = "{% if x %}\n  a\n{% elif y %}\n  b\n{% endif %}\n"
    assert format_template(source) == expected


def test_dedent_on_empty() -> None:
    source = "{% for i in items %}\n{{ i }}\n{% empty %}\nnone\n{% endfor %}\n"
    expected = "{% for i in items %}\n  {{ i }}\n{% empty %}\n  none\n{% endfor %}\n"
    assert format_template(source) == expected


# --- Blank line normalization ---


def test_collapse_multiple_blank_lines() -> None:
    source = "a\n\n\n\nb\n"
    expected = "a\n\nb\n"
    assert format_template(source) == expected


def test_max_blank_lines_zero() -> None:
    source = "a\n\n\nb\n"
    expected = "a\nb\n"
    assert format_template(source, max_blank_lines=0) == expected


def test_max_blank_lines_two() -> None:
    source = "a\n\n\n\n\nb\n"
    expected = "a\n\n\nb\n"
    assert format_template(source, max_blank_lines=2) == expected


def test_single_blank_line_preserved() -> None:
    source = "a\n\nb\n"
    assert format_template(source) == "a\n\nb\n"


# --- Trailing whitespace trimming ---


def test_trailing_whitespace_removed() -> None:
    source = "hello   \nworld  \n"
    expected = "hello\nworld\n"
    assert format_template(source) == expected


def test_trailing_whitespace_inside_block() -> None:
    source = "{% if x %}\nhello   \n{% endif %}\n"
    expected = "{% if x %}\n  hello\n{% endif %}\n"
    assert format_template(source) == expected


# --- Final newline enforcement ---


def test_final_newline_added() -> None:
    result = format_template("hello")
    assert result.endswith("\n")


def test_final_newline_not_doubled() -> None:
    result = format_template("hello\n")
    assert result == "hello\n"


def test_final_newline_empty_stays_empty() -> None:
    assert format_template("") == ""


# --- Self-closing blocks on same line ---


def test_self_closing_block_no_extra_indent() -> None:
    source = "{% if x %}hello{% endif %}\nnext\n"
    expected = "{% if x %}hello{% endif %}\nnext\n"
    assert format_template(source) == expected


# --- Indent does not go negative ---


def test_indent_floor_at_zero() -> None:
    source = "{% endif %}\nhello\n"
    expected = "{% endif %}\nhello\n"
    assert format_template(source) == expected


# --- Lines with no block tags ---


def test_plain_html_not_indented() -> None:
    source = "<div>\n<p>text</p>\n</div>\n"
    assert format_template(source) == source


# --- Various block-opening keywords ---


def test_indent_while_block() -> None:
    source = "{% while True %}\nstuff\n{% endwhile %}\n"
    expected = "{% while True %}\n  stuff\n{% endwhile %}\n"
    assert format_template(source) == expected


def test_indent_raw_block() -> None:
    source = "{% raw %}\ncode\n{% endraw %}\n"
    expected = "{% raw %}\n  code\n{% endraw %}\n"
    assert format_template(source) == expected


def test_indent_call_block() -> None:
    source = "{% call widget() %}\ncontent\n{% endcall %}\n"
    expected = "{% call widget() %}\n  content\n{% endcall %}\n"
    assert format_template(source) == expected
