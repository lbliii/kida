"""Stress tests for Kida template engine.

Tests deep nesting, large templates, performance boundaries, and extreme edge cases.
"""

from __future__ import annotations

import string
import time
from typing import Any

import pytest

from kida import DictLoader, Environment


class TestDeepNesting:
    """Test deeply nested structures."""

    @pytest.fixture
    def env(self) -> Environment:
        return Environment()

    @pytest.mark.parametrize("depth", [10, 25, 50, 100])
    def test_deep_if_nesting(self, env: Environment, depth: int) -> None:
        """Deep if nesting."""
        template = "{% if true %}" * depth + "x" + "{% endif %}" * depth
        tmpl = env.from_string(template)
        assert tmpl.render() == "x"

    @pytest.mark.parametrize("depth", [5, 10, 20])
    def test_deep_for_nesting(self, env: Environment, depth: int) -> None:
        """Deep for loop nesting."""
        template = "{% for x in [1] %}" * depth + "x" + "{% endfor %}" * depth
        tmpl = env.from_string(template)
        assert "x" in tmpl.render()

    @pytest.mark.parametrize("depth", [5, 10, 20])
    def test_deep_mixed_nesting(self, env: Environment, depth: int) -> None:
        """Mixed if/for nesting."""
        template = ""
        for i in range(depth):
            if i % 2 == 0:
                template += "{% if true %}"
            else:
                template += "{% for x in [1] %}"

        template += "x"

        for i in range(depth - 1, -1, -1):
            if i % 2 == 0:
                template += "{% endif %}"
            else:
                template += "{% endfor %}"

        tmpl = env.from_string(template)
        assert "x" in tmpl.render()

    def test_deep_data_access(self, env: Environment) -> None:
        """Deep attribute/item access."""
        # Create nested data structure
        depth = 20
        data: dict[str, Any] = {"value": "found"}
        for _ in range(depth):
            data = {"child": data}

        access = ".child" * depth + ".value"
        template = "{{ data" + access + " }}"

        tmpl = env.from_string(template)
        assert tmpl.render(data=data) == "found"

    def test_deep_expression_nesting(self, env: Environment) -> None:
        """Deeply nested expressions."""
        depth = 30
        expr = "1" + " + 1" * depth
        template = "{{ " + expr + " }}"

        tmpl = env.from_string(template)
        assert tmpl.render() == str(depth + 1)


class TestLargeTemplates:
    """Test large template handling."""

    @pytest.fixture
    def env(self) -> Environment:
        return Environment()

    def test_many_variables(self, env: Environment) -> None:
        """Template with many variable references."""
        count = 1000
        template = " ".join(f"{{{{ v{i} }}}}" for i in range(count))
        context = {f"v{i}": str(i) for i in range(count)}

        tmpl = env.from_string(template)
        result = tmpl.render(**context)

        assert "0" in result
        assert "999" in result

    def test_many_blocks(self, env: Environment) -> None:
        """Template with many block statements."""
        count = 500
        template = "".join(f"{{% if true %}}x{i}{{% endif %}}" for i in range(count))

        tmpl = env.from_string(template)
        result = tmpl.render()

        assert "x0" in result
        assert "x499" in result

    def test_many_filters(self, env: Environment) -> None:
        """Template with many filter applications (within limit)."""
        count = 100
        filters = "|upper|lower" * count
        template = "{{ 'hello'" + filters + " }}"

        # May hit performance limits, but should work
        try:
            tmpl = env.from_string(template)
            result = tmpl.render()
            assert result in ["hello", "HELLO"]  # Depends on final filter
        except RecursionError:
            pytest.skip("Too many nested filters")

    def test_filter_chain_exceeds_limit_raises(self, env: Environment) -> None:
        """Filter chain exceeding MAX_FILTER_CHAIN_LEN raises TemplateSyntaxError."""
        from kida.environment.exceptions import TemplateSyntaxError

        # 201 filters exceeds default MAX_FILTER_CHAIN_LEN of 200
        filters = "|upper" * 201
        template = "{{ 'x'" + filters + " }}"

        with pytest.raises(TemplateSyntaxError) as exc_info:
            env.from_string(template)

        assert "Filter chain exceeds maximum length" in str(exc_info.value)

    def test_large_literal_list(self, env: Environment) -> None:
        """Template with large literal list."""
        count = 500
        items = ", ".join(str(i) for i in range(count))
        template = f"{{% for x in [{items}] %}}{{{{ x }}}},{{% endfor %}}"

        tmpl = env.from_string(template)
        result = tmpl.render()

        assert "0" in result
        assert "499" in result

    def test_large_literal_dict(self, env: Environment) -> None:
        """Template with large literal dict."""
        count = 200
        items = ", ".join(f"'{i}': {i}" for i in range(count))
        template = (
            f"{{% set d = {{{items}}} %}}{{% for k, v in d.items() %}}{{{{ k }}}},{{% endfor %}}"
        )

        tmpl = env.from_string(template)
        result = tmpl.render()

        assert "0" in result
        assert "199" in result

    def test_long_static_content(self, env: Environment) -> None:
        """Template with long static content."""
        content = "x" * 100000  # 100KB of static content
        template = f"START{content}END"

        tmpl = env.from_string(template)
        result = tmpl.render()

        assert result.startswith("START")
        assert result.endswith("END")
        assert len(result) == len(content) + 8


class TestManyIterations:
    """Test many loop iterations."""

    @pytest.fixture
    def env(self) -> Environment:
        return Environment()

    def test_large_loop(self, env: Environment) -> None:
        """Loop with many iterations."""
        tmpl = env.from_string("{% for x in range(10000) %}{% endfor %}done")
        assert tmpl.render() == "done"

    def test_large_loop_with_output(self, env: Environment) -> None:
        """Loop with many iterations producing output."""
        tmpl = env.from_string("{% for x in range(1000) %}x{% endfor %}")
        result = tmpl.render()
        assert len(result) == 1000

    def test_nested_large_loops(self, env: Environment) -> None:
        """Nested loops with many iterations."""
        tmpl = env.from_string("""
{% for i in range(100) %}
  {% for j in range(100) %}
  {% endfor %}
{% endfor %}
done
""")
        result = tmpl.render()
        assert "done" in result


class TestManyMacros:
    """Test many macro definitions."""

    @pytest.fixture
    def env(self) -> Environment:
        return Environment()

    def test_many_macro_definitions(self, env: Environment) -> None:
        """Template with many macro definitions."""
        count = 100
        macros = "\n".join(f"{{% def m{i}() %}}macro{i}{{% end %}}" for i in range(count))
        template = macros + "\n{{ m0() }}{{ m99() }}"

        tmpl = env.from_string(template)
        result = tmpl.render()

        assert "macro0" in result
        assert "macro99" in result

    def test_many_macro_calls(self, env: Environment) -> None:
        """Template with many macro calls."""
        count = 500
        template = "{% def m() %}x{% end %}" + "{{ m() }}" * count

        tmpl = env.from_string(template)
        result = tmpl.render()

        assert result == "x" * count


class TestManyIncludes:
    """Test many includes."""

    def test_many_includes(self) -> None:
        """Template with many includes."""
        count = 100
        loader = DictLoader({f"partial{i}.html": f"partial{i}" for i in range(count)})
        env = Environment(loader=loader)

        includes = "\n".join(f'{{% include "partial{i}.html" %}}' for i in range(count))
        tmpl = env.from_string(includes)
        result = tmpl.render()

        assert "partial0" in result
        assert "partial99" in result


class TestDeepInheritance:
    """Test deep inheritance chains."""

    def test_deep_inheritance(self) -> None:
        """Deep template inheritance."""
        depth = 10
        templates = {}

        templates["base.html"] = "{% block content %}base{% endblock %}"

        for i in range(1, depth):
            templates[f"level{i}.html"] = (
                f'{{% extends "{"base.html" if i == 1 else f"level{i - 1}.html"}" %}}'
                f"{{% block content %}}level{i}{{% endblock %}}"
            )

        loader = DictLoader(templates)
        env = Environment(loader=loader)

        tmpl = env.get_template(f"level{depth - 1}.html")
        result = tmpl.render()
        assert f"level{depth - 1}" in result

    def test_circular_inheritance_raises(self) -> None:
        """Circular inheritance (A extends B extends A) raises TemplateRuntimeError."""
        from kida.environment.exceptions import TemplateRuntimeError

        templates = {
            "a.html": '{% extends "b.html" %}{% block x %}a{% endblock %}',
            "b.html": '{% extends "a.html" %}{% block x %}b{% endblock %}',
        }
        loader = DictLoader(templates)
        env = Environment(loader=loader)

        with pytest.raises(TemplateRuntimeError) as exc_info:
            env.get_template("a.html").render()

        assert "Maximum extends depth exceeded" in str(exc_info.value)
        assert "circular inheritance" in str(exc_info.value).lower()

    def test_extends_depth_limit(self) -> None:
        """Extends chain beyond max_extends_depth raises."""
        from kida.environment.exceptions import TemplateRuntimeError

        depth = 55  # Exceeds default max_extends_depth of 50
        templates = {"base.html": "{% block content %}base{% endblock %}"}
        for i in range(1, depth):
            parent = "base.html" if i == 1 else f"level{i - 1}.html"
            templates[f"level{i}.html"] = (
                f'{{% extends "{parent}" %}}{{% block content %}}level{i}{{% endblock %}}'
            )

        loader = DictLoader(templates)
        env = Environment(loader=loader)

        with pytest.raises(TemplateRuntimeError) as exc_info:
            env.get_template(f"level{depth - 1}.html").render()

        assert "Maximum extends depth exceeded" in str(exc_info.value)


class TestPerformanceBoundaries:
    """Test performance boundaries."""

    @pytest.fixture
    def env(self) -> Environment:
        return Environment()

    def test_render_time_basic(self, env: Environment) -> None:
        """Basic render completes in reasonable time."""
        tmpl = env.from_string("{{ name }}")

        start = time.perf_counter()
        for _ in range(10000):
            tmpl.render(name="World")
        elapsed = time.perf_counter() - start

        # Should complete in under 5 seconds
        assert elapsed < 5.0

    def test_compile_time_basic(self, env: Environment) -> None:
        """Basic compilation completes in reasonable time."""
        template = "{% if true %}{{ name }}{% endif %}"

        start = time.perf_counter()
        for _ in range(1000):
            env.from_string(template)
        elapsed = time.perf_counter() - start

        # Should complete in under 5 seconds
        assert elapsed < 5.0

    def test_complex_template_performance(self, env: Environment) -> None:
        """Complex template renders in reasonable time."""
        template = """
{% for i in range(100) %}
  {% if i % 2 == 0 %}
    <div class="even">{{ i }}</div>
  {% else %}
    <div class="odd">{{ i }}</div>
  {% endif %}
{% endfor %}
"""
        tmpl = env.from_string(template)

        start = time.perf_counter()
        for _ in range(100):
            tmpl.render()
        elapsed = time.perf_counter() - start

        # Should complete in under 5 seconds
        assert elapsed < 5.0


class TestExtremeCases:
    """Test extreme edge cases."""

    @pytest.fixture
    def env(self) -> Environment:
        return Environment()

    def test_empty_everything(self, env: Environment) -> None:
        """Empty template, context, etc."""
        tmpl = env.from_string("")
        assert tmpl.render() == ""

    def test_unicode_stress(self, env: Environment) -> None:
        """Template with many unicode characters."""
        # Mix of different unicode ranges
        chars = "".join(chr(i) for i in range(0x100, 0x200))
        chars += "こんにちは世界"
        chars += "🎉🚀💻🔥"

        tmpl = env.from_string("{{ text }}")
        result = tmpl.render(text=chars)
        assert chars in result

    def test_special_characters(self, env: Environment) -> None:
        """Template with special characters."""
        special = "<>&\"'\n\r\t\\/"

        env_noauto = Environment(autoescape=False)
        tmpl = env_noauto.from_string("{{ text }}")
        result = tmpl.render(text=special)
        assert special in result

    def test_very_long_variable_names(self, env: Environment) -> None:
        """Very long variable names."""
        name = "x" * 1000
        template = "{{ " + name + " }}"

        tmpl = env.from_string(template)
        result = tmpl.render(**{name: "value"})
        assert result == "value"

    def test_many_unique_variables(self, env: Environment) -> None:
        """Many unique variable names."""
        # Generate 26*26 = 676 unique variable names
        names = [a + b for a in string.ascii_lowercase for b in string.ascii_lowercase]

        parts = [f"{{{{ {name} }}}}" for name in names[:100]]
        template = " ".join(parts)
        context = {name: name for name in names[:100]}

        tmpl = env.from_string(template)
        result = tmpl.render(**context)

        assert "aa" in result
        assert "zz" not in result  # Only first 100


class TestSharedEnvironmentStress:
    """Test supported concurrent operations on one shared Environment."""

    def test_concurrent_get_template_while_add_filter(self) -> None:
        """N threads get_template() while 1 thread add_filter(); no partial mutation."""
        import concurrent.futures

        loader = DictLoader(
            {
                "a.html": "{{ x }}",
                "b.html": "{{ y }}",
                "c.html": "{{ z }}",
            }
        )
        env = Environment(loader=loader)

        results: list[str] = []
        errors: list[BaseException] = []

        def get_templates() -> None:
            for _ in range(200):
                try:
                    t = env.get_template("a.html")
                    r = t.render(x="ok")
                    results.append(r)
                except Exception as e:
                    errors.append(e)

        def add_filters() -> None:
            for i in range(50):
                env.add_filter(f"f{i}", lambda x, n=i: str(x) + str(n))

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            readers = [ex.submit(get_templates) for _ in range(4)]
            writer = ex.submit(add_filters)
            concurrent.futures.wait([*readers, writer])

        assert not errors, f"Unexpected errors: {errors}"
        assert all(r == "ok" for r in results), "Corrupt filter dict observed"
        assert len(results) == 4 * 200

    def test_concurrent_registry_registration_publishes_complete_snapshots(self) -> None:
        """Readers see complete registry snapshots while competing writers publish."""
        import concurrent.futures
        import threading

        env = Environment(autoescape=False)

        def stable_filter(value: object) -> str:
            return f"<{value}>"

        def stable_test(value: object) -> bool:
            return value == "ok"

        env.add_filter("stable_filter", stable_filter)
        env.add_test("stable_test", stable_test)
        env.add_global("stable_global", "registry-stable")

        source = (
            "{{ value | stable_filter }}|"
            "{% if value is stable_test %}yes{% else %}no{% endif %}|"
            "{{ stable_global }}"
        )
        rounds = 40
        writer_specs = tuple(
            (registry, writer_id)
            for registry in ("filter", "test", "global")
            for writer_id in range(2)
        )
        reader_count = 4
        worker_count = len(writer_specs) + reader_count
        start = threading.Barrier(worker_count)
        round_start = threading.Barrier(worker_count)
        round_end = threading.Barrier(worker_count)

        def abort_barriers() -> None:
            round_start.abort()
            round_end.abort()

        def register(registry: str, writer_id: int) -> None:
            try:
                start.wait()
                for round_id in range(rounds):
                    round_start.wait()
                    key = f"race_{registry}_{writer_id}_{round_id}"
                    if registry == "filter":
                        env.add_filter(key, lambda _value, marker=key: marker)
                    elif registry == "test":
                        env.add_test(key, lambda value, marker=key: value == marker)
                    else:
                        env.add_global(key, key)
                    round_end.wait()
            except BaseException:
                abort_barriers()
                raise

        def read_registries() -> list[tuple[bool, bool, bool, bool, str]]:
            observations: list[tuple[bool, bool, bool, bool, str]] = []
            try:
                start.wait()
                for _ in range(rounds):
                    round_start.wait()
                    filters = env.filters.copy()
                    tests = env.tests.copy()
                    globals_snapshot = env.globals.copy()
                    rendered = env.from_string(source).render(value="ok")

                    stable = (
                        filters.get("stable_filter") is stable_filter
                        and tests.get("stable_test") is stable_test
                        and globals_snapshot.get("stable_global") == "registry-stable"
                    )
                    filters_complete = all(
                        value(None) == key
                        for key, value in filters.items()
                        if key.startswith("race_filter_")
                    )
                    tests_complete = all(
                        value(key) for key, value in tests.items() if key.startswith("race_test_")
                    )
                    globals_complete = all(
                        value == key
                        for key, value in globals_snapshot.items()
                        if key.startswith("race_global_")
                    )
                    observations.append(
                        (
                            stable,
                            filters_complete,
                            tests_complete,
                            globals_complete,
                            rendered,
                        )
                    )
                    round_end.wait()
            except BaseException:
                abort_barriers()
                raise
            return observations

        with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
            writers = [
                executor.submit(register, registry, writer_id)
                for registry, writer_id in writer_specs
            ]
            readers = [executor.submit(read_registries) for _ in range(reader_count)]
            for future in writers:
                future.result()
            observations = [item for future in readers for item in future.result()]

        assert len(observations) == reader_count * rounds
        assert all(
            stable and filters_ok and tests_ok and globals_ok
            for stable, filters_ok, tests_ok, globals_ok, _rendered in observations
        )
        assert all(
            rendered == "<ok>|yes|registry-stable" for *_snapshot_checks, rendered in observations
        )

        final_filters = {
            key: value for key, value in env.filters.items() if key.startswith("race_filter_")
        }
        final_tests = {
            key: value for key, value in env.tests.items() if key.startswith("race_test_")
        }
        final_globals = {
            key: value for key, value in env.globals.items() if key.startswith("race_global_")
        }
        for registry in (final_filters, final_tests, final_globals):
            # Each round retains at least one publication. When both writers copy
            # the same prior generation, either one's addition may be overwritten.
            assert rounds <= len(registry) <= rounds * 2

        assert all(value(None) == key for key, value in final_filters.items())
        assert all(value(key) for key, value in final_tests.items())
        assert all(value == key for key, value in final_globals.items())

    def test_concurrent_get_template_same_key(self) -> None:
        """Multiple threads get_template(same_name) - thundering herd on cache."""
        import concurrent.futures

        loader = DictLoader({"t.html": "{{ v }}"})
        env = Environment(loader=loader)

        def get_and_render() -> str:
            t = env.get_template("t.html")
            return t.render(v=1)

        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
            futures = [ex.submit(get_and_render) for _ in range(100)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert all(r == "1" for r in results)
        assert len(results) == 100

    def test_concurrent_template_misses_clear_and_eviction(self) -> None:
        """Template clears may repopulate, while every read stays valid and bounded."""
        import concurrent.futures
        import threading

        worker_count = 8
        rounds = 30
        loader = DictLoader({f"t{i}.html": f"Template {i}: {{{{ value }}}}" for i in range(12)})
        env = Environment(loader=loader, cache_size=4, auto_reload=False)
        phase = threading.Barrier(worker_count + 1)

        def reader(worker: int) -> int:
            for iteration in range(rounds):
                template_index = (worker + iteration) % 12
                marker = f"{worker}-{iteration}"
                phase.wait(timeout=30)
                template = env.get_template(f"t{template_index}.html")
                assert template.render(value=marker) == f"Template {template_index}: {marker}"
                phase.wait(timeout=30)
            return worker

        def invalidator() -> None:
            for iteration in range(rounds):
                phase.wait(timeout=30)
                if iteration < rounds // 2:
                    if iteration % 2:
                        env.clear_template_cache([f"t{iteration % 12}.html"])
                    else:
                        env.clear_template_cache()
                phase.wait(timeout=30)

        with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count + 1) as executor:
            readers = [executor.submit(reader, worker) for worker in range(worker_count)]
            invalidation = executor.submit(invalidator)
            results = [future.result() for future in readers]
            invalidation.result()

        assert sorted(results) == list(range(worker_count))
        assert env.cache_info()["template"]["size"] == 4

    def test_concurrent_fragment_misses_clear_and_eviction(self) -> None:
        """Fragment clears and eviction never expose another key's cached output."""
        import concurrent.futures
        import threading

        worker_count = 8
        rounds = 30
        env = Environment(fragment_cache_size=4, fragment_ttl=300)
        template = env.from_string("{% cache key %}{{ value }}{% endcache %}")
        phase = threading.Barrier(worker_count + 1)

        def reader(worker: int) -> int:
            for iteration in range(rounds):
                marker = f"{worker}-{iteration}"
                phase.wait(timeout=30)
                assert template.render(key=marker, value=marker) == marker
                phase.wait(timeout=30)
            return worker

        def invalidator() -> None:
            for iteration in range(rounds):
                phase.wait(timeout=30)
                if iteration < rounds // 2:
                    env.clear_fragment_cache()
                phase.wait(timeout=30)

        with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count + 1) as executor:
            readers = [executor.submit(reader, worker) for worker in range(worker_count)]
            invalidation = executor.submit(invalidator)
            results = [future.result() for future in readers]
            invalidation.result()

        assert sorted(results) == list(range(worker_count))
        assert env.cache_info()["fragment"]["size"] == 4


class TestMixedRenderConcurrency:
    """Test mixed public operations on one shared Template from different threads."""

    def test_mixed_render_and_render_stream(self) -> None:
        """Concurrent render() and render_stream() on same template; no corruption."""
        import concurrent.futures

        env = Environment()
        tmpl = env.from_string("Hello {{ name }}!")

        def do_render() -> str:
            return tmpl.render(name="World")

        def do_render_stream() -> str:
            return "".join(tmpl.render_stream(name="World"))

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(do_render) for _ in range(50)]
            futures.extend(ex.submit(do_render_stream) for _ in range(50))
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == 100
        assert all(r == "Hello World!" for r in results), "No corruption under mixed render"

    def test_shared_template_render_block_stream_and_introspection(self) -> None:
        """All read-only Template surfaces agree under synchronized concurrency."""
        import concurrent.futures
        import threading

        env = Environment()
        template = env.from_string(
            "{% def badge(label: str) %}<b>{{ label }}</b>{% end %}"
            "{% block content %}Block {{ value }} {{ badge(label) }}{% end %}"
            "|Full {{ value }}"
        )
        operation_kinds = ["render", "stream", "block", "introspection"] * 3
        start = threading.Barrier(len(operation_kinds))

        def exercise(kind: str, worker: int) -> tuple[str, int]:
            start.wait(timeout=30)
            for iteration in range(40):
                marker = f"{kind}-{worker}-{iteration}"
                context = {"value": marker, "label": marker}

                if kind == "render":
                    assert template.render(**context) == (
                        f"Block {marker} <b>{marker}</b>|Full {marker}"
                    )
                elif kind == "stream":
                    assert "".join(template.render_stream(**context)) == (
                        f"Block {marker} <b>{marker}</b>|Full {marker}"
                    )
                elif kind == "block":
                    assert template.render_block("content", **context) == (
                        f"Block {marker} <b>{marker}</b>"
                    )
                else:
                    assert template.list_blocks() == ["content"]
                    assert template.list_defs() == ["badge"]
                    block = template.block_metadata()["content"]
                    definition = template.def_metadata()["badge"]
                    metadata = template.template_metadata()
                    assert block.name == "content"
                    assert definition.name == "badge"
                    assert metadata is not None
                    assert metadata.blocks["content"] == block

            return kind, worker

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(operation_kinds)) as executor:
            futures = [
                executor.submit(exercise, kind, worker)
                for worker, kind in enumerate(operation_kinds)
            ]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        assert sorted(kind for kind, _worker in results) == sorted(operation_kinds)
        assert sorted(worker for _kind, worker in results) == list(range(len(operation_kinds)))


class TestConcurrentCompilation:
    """Test concurrent template compilation."""

    def test_concurrent_from_string(self) -> None:
        """Concurrent from_string calls."""
        import concurrent.futures

        env = Environment()

        def compile_template(i: int) -> str:
            tmpl = env.from_string(f"Template {{{{ n }}}}: {i}")
            return tmpl.render(n=i)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(compile_template, i) for i in range(100)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == 100

    def test_concurrent_render(self) -> None:
        """Concurrent render calls."""
        import concurrent.futures

        env = Environment()
        tmpl = env.from_string("{{ name }}: {{ value }}")

        def render_template(i: int) -> str:
            return tmpl.render(name=f"Item{i}", value=i)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(render_template, i) for i in range(100)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == 100
        for result in results:
            assert "Item" in result


class TestPartialEvalDepthLimit:
    """Test partial evaluator depth limit (DoS protection)."""

    def test_deep_attribute_chain_compile_does_not_stack_overflow(self) -> None:
        """Compiling template with 150-level attr chain does not overflow.

        Without static_context, partial eval is skipped. With static_context
        containing a 150-level nested structure, partial eval hits
        MAX_PARTIAL_EVAL_DEPTH (100) and returns _UNRESOLVED. This test
        verifies compile completes (no RecursionError) when the expression
        would require deep recursion to evaluate.
        """
        from kida import Environment

        env = Environment()
        depth = 150  # Exceeds MAX_PARTIAL_EVAL_DEPTH of 100
        obj: dict[str, Any] = {"value": "leaf"}
        for _ in range(depth):
            obj = {"child": obj}

        access = ".child" * depth + ".value"
        # Compile without static_context - no partial eval, but parser/compiler
        # must handle 150-level chain. Render with runtime data.
        tmpl = env.from_string("{{ data" + access + " }}")
        result = tmpl.render(data=obj)
        assert result == "leaf"


class TestMemoryStress:
    """Test memory under stress."""

    @pytest.fixture
    def env(self) -> Environment:
        return Environment()

    def test_large_output(self, env: Environment) -> None:
        """Generate large output."""
        tmpl = env.from_string("{% for i in range(100000) %}x{% endfor %}")
        result = tmpl.render()
        assert len(result) == 100000

    def test_many_template_instances(self, env: Environment) -> None:
        """Create many template instances."""
        templates = []
        for i in range(1000):
            tmpl = env.from_string(f"Template {i}: {{{{ x }}}}")
            templates.append(tmpl)

        # All templates should work
        assert templates[0].render(x="test") == "Template 0: test"
        assert templates[999].render(x="test") == "Template 999: test"
