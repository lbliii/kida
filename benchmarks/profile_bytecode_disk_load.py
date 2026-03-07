"""Profile bytecode cache disk-load path to find hotspots.

Run with: uv run python benchmarks/profile_bytecode_disk_load.py

Matches test_load_from_bytecode_cache_disk_kida: fresh env per iteration
so each get_template hits disk (marshal.load), not in-memory cache.
"""

from __future__ import annotations

import cProfile
import tempfile
from pathlib import Path

from kida import Environment
from kida import FileSystemLoader as KidaFileSystemLoader
from kida.bytecode_cache import BytecodeCache


def profile_disk_load() -> None:
    """Profile get_template() loading from disk bytecode cache."""
    base = Path(__file__).resolve().parent
    template_dir = base / "templates"

    with tempfile.TemporaryDirectory() as tmp:
        cache_dir = Path(tmp) / "kida_cache"
        cache_dir.mkdir()
        loader = KidaFileSystemLoader(str(template_dir))
        # Pre-populate bytecode cache
        env0 = Environment(
            loader=loader,
            bytecode_cache=BytecodeCache(cache_dir),
            auto_reload=False,
            preserve_ast=False,
        )
        env0.get_template("small.html")

        def run() -> object:
            env = Environment(
                loader=loader,
                bytecode_cache=BytecodeCache(cache_dir),
                auto_reload=False,
                preserve_ast=False,
            )
            return env.get_template("small.html")

        prof = cProfile.Profile()
        prof.enable()
        for _ in range(100):
            run()
        prof.disable()
        prof.print_stats(sort="cumulative")


if __name__ == "__main__":
    profile_disk_load()
