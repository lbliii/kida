"""Implementation of ``kida diff``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, final

from kida._cli.common import write_stderr, write_stdout

if TYPE_CHECKING:
    import argparse
    from pathlib import Path


@final
@dataclass(frozen=True, slots=True)
class DiffResult:
    """Presentation-neutral semantic manifest comparison."""

    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[tuple[str, tuple[tuple[str, str, str, str], ...]], ...]
    unchanged: int

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.changed)


def compare(old_data: dict[str, Any], new_data: dict[str, Any]) -> DiffResult:
    """Compare two decoded render manifests without performing I/O."""
    old_entries = {entry["url"]: entry for entry in old_data.get("entries", [])}
    new_entries = {entry["url"]: entry for entry in new_data.get("entries", [])}
    added = tuple(url for url in new_entries if url not in old_entries)
    removed = tuple(url for url in old_entries if url not in new_entries)
    changed: list[tuple[str, tuple[tuple[str, str, str, str], ...]]] = []
    unchanged = 0

    for url, new_entry in new_entries.items():
        if url not in old_entries:
            continue
        old_blocks = old_entries[url].get("blocks", {})
        new_blocks = new_entry.get("blocks", {})
        block_changes: list[tuple[str, str, str, str]] = []
        for block_name in sorted(set(old_blocks) | set(new_blocks)):
            old_hash = old_blocks.get(block_name, {}).get("content_hash", "")
            new_hash = new_blocks.get(block_name, {}).get("content_hash", "")
            if old_hash != new_hash:
                old_role = old_blocks.get(block_name, {}).get("role", "?")
                new_role = new_blocks.get(block_name, {}).get("role", old_role)
                block_changes.append((block_name, new_role, old_hash, new_hash))
        if block_changes:
            changed.append((url, tuple(block_changes)))
        else:
            unchanged += 1
    return DiffResult(added, removed, tuple(changed), unchanged)


def render_text(result: DiffResult) -> str:
    """Render a semantic comparison using the stable human format."""
    lines: list[str] = []
    if result.added:
        lines.append(f"Added ({len(result.added)}):")
        lines.extend(f"  + {url}" for url in result.added)
    if result.removed:
        lines.append(f"Removed ({len(result.removed)}):")
        lines.extend(f"  - {url}" for url in result.removed)
    if result.changed:
        lines.append(f"Changed ({len(result.changed)}):")
        for url, changes in sorted(result.changed):
            lines.append(f"  {url}:")
            for block_name, role, old_hash, new_hash in changes:
                lines.append(f"      {block_name} ({role}): {old_hash} → {new_hash}")
    if not result.has_changes:
        lines.append("No changes.")
    lines.append("")
    lines.append(
        f"Summary: {len(result.added)} added, {len(result.removed)} removed, "
        f"{len(result.changed)} changed, {result.unchanged} unchanged"
    )
    return "\n".join(lines) + "\n"


def execute(old_path: Path, new_path: Path) -> int:
    """Load, compare, and present two render manifests."""
    import json

    if not old_path.exists():
        write_stderr(f"kida diff: not found: {old_path}")
        return 2
    if not new_path.exists():
        write_stderr(f"kida diff: not found: {new_path}")
        return 2
    old_data = json.loads(old_path.read_text(encoding="utf-8"))
    new_data = json.loads(new_path.read_text(encoding="utf-8"))
    result = compare(old_data, new_data)
    write_stdout(render_text(result), end="")
    return 1 if result.has_changes else 0


def run(args: argparse.Namespace) -> int:
    """Adapt parsed arguments to manifest comparison."""
    return execute(args.old_manifest, args.new_manifest)
