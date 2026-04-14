"""Kida README generator — auto-detect project metadata, render styled READMEs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from kida.readme.detect import ProjectContext


def detect_project(root: Path, *, depth: int = 2) -> ProjectContext:
    """Auto-detect project metadata from a directory.

    Convenience re-export of :func:`kida.readme.detect.detect_project`.
    """
    from kida.readme.detect import detect_project as _detect

    return _detect(root, depth=depth)


def render_readme(
    root: Path,
    *,
    preset: str = "default",
    template: Path | None = None,
    context: dict[str, Any] | ProjectContext | None = None,
    depth: int = 2,
) -> str:
    """Auto-detect project metadata and render a README.

    Args:
        root: Project root directory to scan.
        preset: Built-in template preset (``"default"``, ``"minimal"``,
            ``"library"``, ``"cli"``).
        template: Path to a custom template file (overrides *preset*).
        context: Extra context variables that override auto-detected values.
        depth: Directory tree depth for auto-detection (default 2).

    Returns:
        Rendered README as a markdown string.
    """
    from kida.readme.detect import detect_project as _detect

    detected = _detect(root, depth=depth)
    if context:
        detected.update(context)

    if template is not None:
        from kida import Environment, FileSystemLoader

        env = Environment(
            loader=FileSystemLoader(str(template.parent)),
            autoescape=False,
        )
        tpl = env.get_template(template.name)
    else:
        from kida import Environment
        from kida.environment.loaders import ChoiceLoader, PackageLoader

        env = Environment(
            loader=ChoiceLoader(
                [
                    PackageLoader("kida", "readme/presets"),
                    PackageLoader("kida", "readme"),
                ]
            ),
            autoescape=False,
        )
        tpl = env.get_template(f"{preset}.kida")

    return tpl.render(**detected)
