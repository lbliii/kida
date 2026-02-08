"""Block-level recompilation for Kida templates.

When a template changes but only some blocks are affected, this module
avoids recompiling the entire template by:

1. Detecting which named blocks changed (via AST comparison).
2. Compiling only the changed block functions.
3. Patching the existing Template's namespace with the new functions.

This enables O(changed_blocks) recompilation instead of O(template)
for incremental build pipelines.

Thread Safety:
    ``detect_block_changes`` is a pure function — safe from any thread.
    ``recompile_blocks`` mutates a Template's namespace; callers must
    ensure the template is not being rendered concurrently during
    the patch.  In practice, Bengal's build pipeline serializes
    compilation and rendering, so this is safe.

"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from kida.nodes import Block, Node

if TYPE_CHECKING:
    from kida.environment import Environment
    from kida.nodes import Template as TemplateNode
    from kida.template import Template


@dataclass(frozen=True, slots=True)
class BlockDelta:
    """Describes which blocks changed between two template versions.

    Attributes:
        changed: Block names whose AST content changed.
        added: Block names present in new but not old.
        removed: Block names present in old but not new.

    """

    changed: frozenset[str]
    added: frozenset[str]
    removed: frozenset[str]

    @property
    def has_changes(self) -> bool:
        """True if any blocks were changed, added, or removed."""
        return bool(self.changed or self.added or self.removed)

    @property
    def all_affected(self) -> frozenset[str]:
        """Union of changed, added, and removed block names."""
        return self.changed | self.added | self.removed


def collect_blocks(nodes: Sequence[Node]) -> dict[str, Block]:
    """Recursively collect all named Block nodes from an AST body.

    Returns a dict mapping block name to the Block node.

    """
    blocks: dict[str, Block] = {}
    _walk_for_blocks(nodes, blocks)
    return blocks


def _walk_for_blocks(nodes: Sequence[Node], out: dict[str, Block]) -> None:
    """Walk AST nodes, collecting Block nodes into *out*."""
    for node in nodes:
        if isinstance(node, Block):
            out[node.name] = node
            _walk_for_blocks(node.body, out)
        elif hasattr(node, "body"):
            body = node.body
            if isinstance(body, Sequence):
                _walk_for_blocks(body, out)
            # Walk alternate branches
            for attr in ("else_", "empty"):
                branch = getattr(node, attr, None)
                if isinstance(branch, Sequence):
                    _walk_for_blocks(branch, out)
            elif_ = getattr(node, "elif_", None)
            if elif_:
                for _, elif_body in elif_:
                    _walk_for_blocks(elif_body, out)


def detect_block_changes(
    old_ast: TemplateNode,
    new_ast: TemplateNode,
) -> BlockDelta:
    """Compare two template ASTs and identify changed blocks.

    Uses frozen-dataclass ``==`` for O(1) equality on unchanged subtrees.

    Args:
        old_ast: Previous template AST.
        new_ast: New template AST.

    Returns:
        BlockDelta describing the differences.

    """
    old_blocks = collect_blocks(old_ast.body)
    new_blocks = collect_blocks(new_ast.body)

    old_names = frozenset(old_blocks)
    new_names = frozenset(new_blocks)

    added = new_names - old_names
    removed = old_names - new_names
    common = old_names & new_names

    changed = frozenset(
        name for name in common if old_blocks[name] != new_blocks[name]
    )

    return BlockDelta(changed=changed, added=added, removed=removed)


def recompile_blocks(
    env: Environment,
    template: Template,
    new_ast: TemplateNode,
    delta: BlockDelta,
) -> frozenset[str]:
    """Recompile only the changed/added blocks and patch the template.

    Compiles each affected block into three function variants
    (standard, streaming, async streaming) and replaces them in the
    template's namespace.  Removed blocks are deleted from the namespace.

    Args:
        env: The Environment (needed for compiler construction).
        template: The live Template object to patch.
        new_ast: The new template AST (source of changed block bodies).
        delta: The BlockDelta from ``detect_block_changes``.

    Returns:
        The set of block names that were recompiled.

    """
    import ast as pyast

    from kida.compiler import Compiler

    new_blocks = collect_blocks(new_ast.body)
    recompiled: set[str] = set()

    # Recompile changed + added blocks
    to_compile = delta.changed | delta.added
    for block_name in to_compile:
        block_node = new_blocks.get(block_name)
        if block_node is None:
            continue

        compiler = Compiler(env)
        # Reset compiler state for each block
        compiler._locals = set()
        compiler._block_counter = 0
        compiler._has_async = False
        compiler._streaming = False
        compiler._async_mode = False

        module_body: list[pyast.stmt] = []

        # Standard (StringBuilder) block function
        module_body.append(compiler._make_block_function(block_name, block_node))

        # Streaming block function
        compiler._streaming = True
        module_body.append(compiler._make_block_function_stream(block_name, block_node))
        compiler._streaming = False

        # Async streaming block function
        compiler._streaming = True
        compiler._async_mode = True
        module_body.append(
            compiler._make_block_function_stream_async(block_name, block_node)
        )
        compiler._async_mode = False
        compiler._streaming = False

        module = pyast.Module(body=module_body, type_ignores=[])
        pyast.fix_missing_locations(module)

        code = compile(module, template._filename or "<template>", "exec")

        # Execute in the template's existing namespace so block functions
        # can access all helpers (_escape, _lookup, etc.)
        exec(code, template._namespace)  # noqa: S102
        recompiled.add(block_name)

    # Remove deleted blocks
    for block_name in delta.removed:
        template._namespace.pop(f"_block_{block_name}", None)
        template._namespace.pop(f"_block_{block_name}_stream", None)
        template._namespace.pop(f"_block_{block_name}_stream_async", None)

    return frozenset(recompiled)
