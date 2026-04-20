"""Tests for the warn-once dedup on `Environment.from_string()` without `name=`.

The warning fires when a bytecode cache is configured and the caller does not
pass `name=`, because the cache cannot key the compiled artifact. Before v0.7.1
this fired unconditionally per call; now it fires once per distinct source per
Environment.
"""

import warnings

from kida import Environment
from kida.bytecode_cache import BytecodeCache


def _env_with_cache(tmp_path) -> Environment:
    return Environment(bytecode_cache=BytecodeCache(tmp_path / "cache"))


def test_warns_once_per_distinct_source(tmp_path):
    env = _env_with_cache(tmp_path)
    source = "{{ x }}"

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for _ in range(100):
            env.from_string(source)

    relevant = [w for w in caught if "from_string() without name=" in str(w.message)]
    assert len(relevant) == 1


def test_distinct_sources_each_warn_once(tmp_path):
    env = _env_with_cache(tmp_path)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for _ in range(5):
            env.from_string("{{ a }}")
            env.from_string("{{ b }}")
            env.from_string("{{ c }}")

    relevant = [w for w in caught if "from_string() without name=" in str(w.message)]
    assert len(relevant) == 3


def test_two_environments_warn_independently(tmp_path):
    env_a = _env_with_cache(tmp_path / "a")
    env_b = _env_with_cache(tmp_path / "b")
    source = "{{ x }}"

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        env_a.from_string(source)
        env_a.from_string(source)
        env_b.from_string(source)
        env_b.from_string(source)

    relevant = [w for w in caught if "from_string() without name=" in str(w.message)]
    assert len(relevant) == 2


def test_no_warning_without_bytecode_cache():
    env = Environment()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for _ in range(10):
            env.from_string("{{ x }}")

    relevant = [w for w in caught if "from_string() without name=" in str(w.message)]
    assert relevant == []


def test_no_warning_when_name_is_passed(tmp_path):
    env = _env_with_cache(tmp_path)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for i in range(10):
            env.from_string("{{ x }}", name=f"t{i}.html")

    relevant = [w for w in caught if "from_string() without name=" in str(w.message)]
    assert relevant == []


def test_warning_text_and_stacklevel_preserved(tmp_path):
    env = _env_with_cache(tmp_path)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        env.from_string("{{ x }}")

    relevant = [w for w in caught if "from_string() without name=" in str(w.message)]
    assert len(relevant) == 1
    message = str(relevant[0].message)
    assert "bypasses bytecode cache" in message
    assert "Pass name=" in message
    assert relevant[0].filename.endswith("test_from_string_warn_once.py")
