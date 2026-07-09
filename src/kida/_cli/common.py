"""Shared, dependency-light helpers for CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_TEMPLATE_GLOBS = ("*.html", "*.kida")


def iter_templates(root: Path) -> list[Path]:
    """Collect template files matching all known extensions, sorted."""
    seen: set[Path] = set()
    for glob in _TEMPLATE_GLOBS:
        seen.update(root.rglob(glob))
    return sorted(seen)


def write_stdout(text: str, *, end: str = "\n") -> None:
    """Write one public CLI message to standard output."""
    import sys

    sys.stdout.write(text + end)


def write_stderr(text: str, *, end: str = "\n") -> None:
    """Write one public CLI message to standard error."""
    import sys

    sys.stderr.write(text + end)
