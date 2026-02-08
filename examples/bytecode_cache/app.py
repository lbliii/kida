"""Bytecode cache -- cold start optimization.

Demonstrates BytecodeCache: first load compiles and caches the template
bytecode to disk, second load skips the parser/compiler entirely and
loads the pre-compiled code object from the cache file.

Run:
    python app.py
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from kida import Environment
from kida.bytecode_cache import BytecodeCache

TEMPLATE_SOURCE = """\
<html>
<head><title>{{ title }}</title></head>
<body>
  <h1>{{ title }}</h1>
  {% for item in items %}
    <p>{{ item }}</p>
  {% end %}
</body>
</html>"""

tmpdir = TemporaryDirectory()
cache_dir = Path(tmpdir.name)
cache = BytecodeCache(cache_dir)

# First load: compile from source + write bytecode to cache (miss)
env1 = Environment(bytecode_cache=cache)
t1 = env1.from_string(TEMPLATE_SOURCE)
output_first = t1.render(title="Cached Page", items=["alpha", "beta", "gamma"])
stats_after_first = cache.stats()

# Second environment: same cache, forces load from bytecode (hit)
env2 = Environment(bytecode_cache=cache)
t2 = env2.from_string(TEMPLATE_SOURCE)
output_second = t2.render(title="Cached Page", items=["alpha", "beta", "gamma"])
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
