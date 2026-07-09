"""Implementation of ``kida manifest``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kida._cli.common import iter_templates, write_stderr, write_stdout

if TYPE_CHECKING:
    import argparse
    from pathlib import Path


def serialize_manifest(manifest: Any) -> dict[str, Any]:
    """Convert a render manifest into its stable JSON-compatible shape."""
    entries: list[dict[str, Any]] = []
    for url, capture in manifest.captures:
        entry: dict[str, Any] = {
            "url": url,
            "template": capture.template_name,
            "blocks": {
                name: {
                    "role": fragment.role,
                    "content_hash": fragment.content_hash,
                    "depends_on": sorted(fragment.depends_on),
                    "html_length": len(fragment.html),
                }
                for name, fragment in capture.blocks.items()
            },
        }
        if capture.context_keys:
            entry["context_keys"] = list(capture.context_keys.keys())
        entries.append(entry)
    return {"version": manifest.version, "entries": entries}


def execute(
    template_dir: Path,
    *,
    output: Path | None,
    data_file: Path | None,
    search: bool,
) -> int:
    """Render templates and output a capture or search manifest."""
    import json

    from kida import Environment, FileSystemLoader
    from kida.render_capture import captured_render
    from kida.render_manifest import RenderManifest, SearchManifestBuilder

    root = template_dir.resolve()
    if not root.is_dir():
        write_stderr(f"kida manifest: not a directory: {root}")
        return 2

    env = Environment(
        loader=FileSystemLoader(str(root)),
        enable_capture=True,
        strict_undefined=False,
    )
    context_data: dict[str, dict[str, Any]] = {}
    if data_file is not None:
        context_data = json.loads(data_file.read_text(encoding="utf-8"))

    manifest = RenderManifest()
    rendered = 0
    for path in iter_templates(root):
        relative = path.relative_to(root).as_posix()
        try:
            template = env.get_template(relative)
        except Exception as exc:
            write_stderr(f"kida manifest: skip {relative}: {exc}")
            continue

        context = context_data.get(relative, {})
        capture_context = frozenset(context) if context else None
        try:
            with captured_render(capture_context=capture_context) as capture:
                template.render(**context)
        except Exception as exc:
            write_stderr(f"kida manifest: render error {relative}: {exc}")
            continue
        manifest.add(relative, capture)
        rendered += 1

    result = SearchManifestBuilder().build(manifest) if search else serialize_manifest(manifest)
    serialized = json.dumps(result, indent=2, ensure_ascii=False)
    if output is not None:
        output.write_text(serialized + "\n", encoding="utf-8")
        write_stderr(f"kida manifest: {rendered} templates → {output}")
    else:
        write_stdout(serialized)
    return 0


def run(args: argparse.Namespace) -> int:
    """Adapt parsed arguments to manifest generation."""
    return execute(
        args.template_dir,
        output=args.output,
        data_file=args.data,
        search=args.search,
    )
