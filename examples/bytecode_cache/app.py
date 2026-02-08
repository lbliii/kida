"""Bytecode cache -- cold start optimization.

Demonstrates BytecodeCache: first load compiles and caches the template
bytecode to disk, second load skips the parser/compiler entirely and
loads the pre-compiled code object from the cache file.

Run:
    python app.py
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from kida import Environment, FileSystemLoader
from kida.bytecode_cache import BytecodeCache

templates_dir = Path(__file__).parent / "templates"

tmpdir = TemporaryDirectory()
cache_dir = Path(tmpdir.name)
cache = BytecodeCache(cache_dir)

context = {"title": "Cached Page", "entries": ["alpha", "beta", "gamma"]}

# First load: compile from source + write bytecode to cache (miss)
env1 = Environment(
    loader=FileSystemLoader(str(templates_dir)),
    bytecode_cache=cache,
)
t1 = env1.get_template("page.html")
output_first = t1.render(**context)
stats_after_first = cache.stats()

# Second environment: same bytecode cache, fresh template cache (hit)
env2 = Environment(
    loader=FileSystemLoader(str(templates_dir)),
    bytecode_cache=cache,
)
t2 = env2.get_template("page.html")
output_second = t2.render(**context)
stats_after_second = cache.stats()

output = output_first


def main() -> None:
    print("=== First Load (compile + cache) ===")
    print(f"  Output: {output_first[:60]}...")
    print(f"  Cache files: {stats_after_first['file_count']}")
    print(f"  Cache bytes: {stats_after_first['total_bytes']}")
    print()
    print("=== Second Load (from bytecode) ===")
    print(f"  Output: {output_second[:60]}...")
    print(f"  Cache files: {stats_after_second['file_count']}")
    print(f"  Outputs match: {output_first == output_second}")


if __name__ == "__main__":
    main()
