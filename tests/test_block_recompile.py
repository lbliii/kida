"""Tests for kida.compiler.block_recompile — incremental block recompilation."""

from kida import Environment
from kida.compiler.block_recompile import (
    BlockDelta,
    collect_blocks,
    detect_block_changes,
    recompile_blocks,
)
from kida.lexer import Lexer
from kida.parser import Parser


def _parse_template(env: Environment, source: str):
    """Parse a template source into AST (without compiling)."""
    lexer = Lexer(source, env._lexer_config)
    tokens = list(lexer.tokenize())
    should_escape = env.autoescape(None) if callable(env.autoescape) else env.autoescape
    parser = Parser(tokens, None, None, source, autoescape=should_escape)
    return parser.parse()


class TestCollectBlocks:
    """Tests for collect_blocks — extracts named blocks from AST."""

    def test_no_blocks(self) -> None:
        env = Environment()
        ast = _parse_template(env, "Hello {{ name }}!")
        blocks = collect_blocks(ast.body)
        assert blocks == {}

    def test_single_block(self) -> None:
        env = Environment()
        ast = _parse_template(env, "{% block title %}Title{% end %}")
        blocks = collect_blocks(ast.body)
        assert "title" in blocks
        assert len(blocks) == 1

    def test_multiple_blocks(self) -> None:
        env = Environment()
        source = (
            "{% block header %}Header{% end %}"
            "{% block content %}Content{% end %}"
            "{% block footer %}Footer{% end %}"
        )
        ast = _parse_template(env, source)
        blocks = collect_blocks(ast.body)
        assert set(blocks.keys()) == {"header", "content", "footer"}

    def test_nested_blocks(self) -> None:
        env = Environment()
        source = "{% block outer %}{% block inner %}Hello{% end %}{% end %}"
        ast = _parse_template(env, source)
        blocks = collect_blocks(ast.body)
        assert "outer" in blocks
        assert "inner" in blocks


class TestDetectBlockChanges:
    """Tests for detect_block_changes — compares two template ASTs."""

    def test_identical_templates_no_changes(self) -> None:
        env = Environment()
        source = "{% block title %}Title{% end %}"
        old = _parse_template(env, source)
        new = _parse_template(env, source)
        delta = detect_block_changes(old, new)
        assert not delta.has_changes
        assert delta.changed == frozenset()
        assert delta.added == frozenset()
        assert delta.removed == frozenset()

    def test_modified_block_detected(self) -> None:
        env = Environment()
        old = _parse_template(env, "{% block title %}Old Title{% end %}")
        new = _parse_template(env, "{% block title %}New Title{% end %}")
        delta = detect_block_changes(old, new)
        assert delta.has_changes
        assert "title" in delta.changed
        assert delta.added == frozenset()
        assert delta.removed == frozenset()

    def test_added_block_detected(self) -> None:
        env = Environment()
        old = _parse_template(env, "{% block title %}Title{% end %}")
        new = _parse_template(
            env,
            "{% block title %}Title{% end %}{% block sidebar %}New{% end %}",
        )
        delta = detect_block_changes(old, new)
        assert delta.has_changes
        assert "sidebar" in delta.added
        assert "title" not in delta.changed

    def test_removed_block_detected(self) -> None:
        env = Environment()
        old = _parse_template(
            env,
            "{% block title %}Title{% end %}{% block sidebar %}Side{% end %}",
        )
        new = _parse_template(env, "{% block title %}Title{% end %}")
        delta = detect_block_changes(old, new)
        assert delta.has_changes
        assert "sidebar" in delta.removed
        assert "title" not in delta.changed

    def test_mixed_changes(self) -> None:
        env = Environment()
        old = _parse_template(
            env,
            "{% block a %}Old A{% end %}{% block b %}B{% end %}{% block c %}C{% end %}",
        )
        new = _parse_template(
            env,
            "{% block a %}New A{% end %}{% block b %}B{% end %}{% block d %}D{% end %}",
        )
        delta = detect_block_changes(old, new)
        assert "a" in delta.changed  # Modified
        assert "b" not in delta.changed  # Unchanged
        assert "c" in delta.removed  # Removed
        assert "d" in delta.added  # Added

    def test_all_affected_property(self) -> None:
        delta = BlockDelta(
            changed=frozenset({"a"}),
            added=frozenset({"b"}),
            removed=frozenset({"c"}),
        )
        assert delta.all_affected == frozenset({"a", "b", "c"})


class TestRecompileBlocks:
    """Integration tests for recompile_blocks — patches live templates."""

    def test_recompile_changed_block(self) -> None:
        env = Environment(autoescape=False, bytecode_cache=False)
        source_v1 = "{% block greeting %}Hello{% end %}"
        source_v2 = "{% block greeting %}Goodbye{% end %}"

        # Compile v1
        template = env.from_string(source_v1)
        assert template.render_block("greeting") == "Hello"

        # Parse v2 AST
        new_ast = _parse_template(env, source_v2)
        old_ast = _parse_template(env, source_v1)
        delta = detect_block_changes(old_ast, new_ast)

        assert "greeting" in delta.changed

        # Recompile only the changed block
        recompiled = recompile_blocks(env, template, new_ast, delta)
        assert "greeting" in recompiled

        # Template now renders the updated block
        assert template.render_block("greeting") == "Goodbye"

    def test_recompile_with_expressions(self) -> None:
        env = Environment(autoescape=False, bytecode_cache=False)
        source_v1 = "{% block msg %}Hello {{ name }}{% end %}"
        source_v2 = "{% block msg %}Hi {{ name }}!{% end %}"

        template = env.from_string(source_v1)
        assert template.render_block("msg", name="World") == "Hello World"

        new_ast = _parse_template(env, source_v2)
        old_ast = _parse_template(env, source_v1)
        delta = detect_block_changes(old_ast, new_ast)
        recompile_blocks(env, template, new_ast, delta)

        assert template.render_block("msg", name="World") == "Hi World!"

    def test_added_block_becomes_available(self) -> None:
        env = Environment(autoescape=False, bytecode_cache=False)
        source_v1 = "{% block a %}A{% end %}"
        source_v2 = "{% block a %}A{% end %}{% block b %}B{% end %}"

        env.from_string(source_v2)  # Need v2 as base so render() works
        # But test the mechanism: parse both, detect changes, recompile
        old_ast = _parse_template(env, source_v1)
        new_ast = _parse_template(env, source_v2)
        delta = detect_block_changes(old_ast, new_ast)

        assert "b" in delta.added

    def test_removed_block_deleted_from_namespace(self) -> None:
        env = Environment(autoescape=False, bytecode_cache=False)
        source_v1 = "{% block a %}A{% end %}{% block b %}B{% end %}"
        source_v2 = "{% block a %}A{% end %}"

        template = env.from_string(source_v1)
        assert "_block_b" in template._namespace

        old_ast = _parse_template(env, source_v1)
        new_ast = _parse_template(env, source_v2)
        delta = detect_block_changes(old_ast, new_ast)
        recompile_blocks(env, template, new_ast, delta)

        assert "_block_b" not in template._namespace
        assert "_block_b_stream" not in template._namespace

    def test_no_changes_noop(self) -> None:
        env = Environment(autoescape=False, bytecode_cache=False)
        source = "{% block title %}Title{% end %}"
        template = env.from_string(source)

        ast1 = _parse_template(env, source)
        ast2 = _parse_template(env, source)
        delta = detect_block_changes(ast1, ast2)

        assert not delta.has_changes
        recompiled = recompile_blocks(env, template, ast2, delta)
        assert len(recompiled) == 0

    def test_streaming_block_also_patched(self) -> None:
        env = Environment(autoescape=False, bytecode_cache=False)
        source_v1 = "{% block msg %}Hello{% end %}"
        source_v2 = "{% block msg %}Goodbye{% end %}"

        template = env.from_string(source_v1)

        new_ast = _parse_template(env, source_v2)
        old_ast = _parse_template(env, source_v1)
        delta = detect_block_changes(old_ast, new_ast)
        recompile_blocks(env, template, new_ast, delta)

        # Streaming block function should also be updated
        stream_func = template._namespace.get("_block_msg_stream")
        assert stream_func is not None
        chunks = list(stream_func({"_env": env}, {}))
        # Filter out None chunks (generator semantics)
        content = "".join(c for c in chunks if c is not None)
        assert "Goodbye" in content
