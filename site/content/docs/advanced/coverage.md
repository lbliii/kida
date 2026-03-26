---
title: Template Coverage
description: Track which template lines execute during rendering with LCOV and Cobertura export
draft: false
weight: 65
lang: en
type: doc
tags:
  - advanced
  - coverage
  - testing
keywords:
  - template coverage
  - CoverageCollector
  - LCOV
  - Cobertura
  - testing
icon: chart-bar
---

# Template Coverage

Kida can track which template lines execute during rendering and export coverage data in standard formats (LCOV, Cobertura XML). Coverage collection is **opt-in** — it has zero overhead when disabled because the compiler-emitted `_rc.line = N` markers only record hits when a `CoverageCollector` is active.

```python
from kida.coverage import CoverageCollector
```

## Quick Start

```python
from kida import Environment, FileSystemLoader
from kida.coverage import CoverageCollector

env = Environment(loader=FileSystemLoader("templates/"))
cov = CoverageCollector()

with cov:
    template = env.get_template("page.html")
    template.render(title="Hello")

print(cov.summary())
cov.write_lcov("coverage.lcov")
```

Output:

```text
Template                                            Lines    Hit   Cover
-----------------------------------------------------------------------
page.html                                               8      8  100.0%
-----------------------------------------------------------------------
TOTAL                                                   8      8  100.0%
```

## CoverageCollector API

`CoverageCollector` is the primary interface. It dynamically patches `RenderContext.__setattr__` while active, so there is zero overhead when no collector is running.

### Context Manager

The recommended usage is as a context manager:

```python
with CoverageCollector() as cov:
    template.render(**context)
# cov now contains all line hits from the render
```

### Manual Start / Stop

For longer-lived collection (e.g., across an entire test suite):

```python
cov = CoverageCollector()
cov.start()

# ... render many templates ...

cov.stop()
print(cov.summary())
```

Calling `start()` on an already-started collector is a no-op. Calling `stop()` resets the `ContextVar` token and decrements the internal reference count.

### Raw Data

Access the raw coverage data directly:

```python
cov.data
# {"page.html": {1, 3, 5, 7, 8}, "base.html": {2, 4, 6}}
```

The `data` property returns a `dict[str, set[int]]` mapping template names to sets of executed line numbers.

### Clearing Data

Reset collected data without creating a new collector:

```python
cov.clear()
```

### Getting Results

`get_results()` returns a list of `CoverageResult` objects, one per template, sorted by name:

```python
results = cov.get_results()
for r in results:
    print(f"{r.template_name}: {r.hit_count}/{r.total_count} ({r.percentage:.1f}%)")
```

Pass an optional `source_map` to provide full line enumeration for accurate miss counting:

```python
source_map = {
    "page.html": frozenset({1, 2, 3, 4, 5, 6, 7, 8, 9, 10}),
}
results = cov.get_results(source_map=source_map)
for r in results:
    print(f"{r.template_name}: {r.missed_count} lines missed")
```

Without a `source_map`, `total_lines` equals `executed_lines` (100% coverage for all touched templates). This is useful for hit tracking even without full line enumeration.

### CoverageResult

| Property | Type | Description |
|---|---|---|
| `template_name` | `str` | Template identifier |
| `executed_lines` | `frozenset[int]` | Line numbers that executed |
| `total_lines` | `frozenset[int]` | All trackable line numbers |
| `hit_count` | `int` | Number of executed lines (property) |
| `total_count` | `int` | Total trackable lines (property) |
| `missed_count` | `int` | Lines not executed (property) |
| `percentage` | `float` | Coverage percentage (property) |

### Text Summary

`summary()` returns a formatted text table of coverage across all templates:

```python
print(cov.summary(source_map=source_map))
```

If no templates were rendered, `summary()` returns `"No templates rendered."`.

## LCOV Export

Write coverage data in [LCOV tracefile format](https://ltp.sourceforge.net/coverage/lcov.php), compatible with `lcov`, `genhtml`, and most CI coverage tools:

```python
cov.write_lcov("coverage.lcov")
```

Or get the LCOV content as a string:

```python
lcov_string = cov.format_lcov()
```

The output follows the standard LCOV format:

```text
SF:page.html
DA:1,1
DA:3,1
DA:5,1
LH:3
LF:3
end_of_record
```

Each `DA:` line records a line number and its hit count (always `1` for any executed line). `LH` is the number of lines hit, `LF` is the total number of lines in the record.

## Cobertura Export

Write coverage data in [Cobertura XML format](https://cobertura.github.io/cobertura/), compatible with Jenkins, GitLab CI, and other CI systems:

```python
cov.write_cobertura("coverage.xml")
```

Or get the XML content as a string:

```python
xml_string = cov.format_cobertura()
```

The output follows the Cobertura schema. Templates are grouped under a single `"templates"` package, with each template represented as a class. The root element includes a `line-rate` attribute with the aggregate coverage ratio.

## Thread Safety

`CoverageCollector` uses `ContextVar` for data isolation and a `threading.Lock` for the global reference count. This means:

- **Concurrent renders** — each collector tracks only its own renders; parallel test runners or async handlers do not interfere with each other.
- **Nested collectors** — multiple `CoverageCollector` instances can be active simultaneously. The `RenderContext.__setattr__` patch stays active as long as at least one collector is running (reference-counted via `_active_count`).
- **Cleanup** — when the last active collector stops, the `__setattr__` patch is removed entirely, restoring zero-overhead rendering.

## CI Integration Example

### pytest + LCOV

```python
import pytest
from kida.coverage import CoverageCollector

@pytest.fixture(scope="session")
def template_coverage():
    cov = CoverageCollector()
    cov.start()
    yield cov
    cov.stop()
    cov.write_lcov("template-coverage.lcov")
    cov.write_cobertura("template-coverage.xml")

def test_homepage(template_coverage, env):
    template = env.get_template("home.html")
    result = template.render(title="Home")
    assert "Home" in result

def test_about(template_coverage, env):
    template = env.get_template("about.html")
    result = template.render(title="About")
    assert "About" in result
```

### GitHub Actions

```yaml
- name: Run tests with template coverage
  run: pytest --tb=short

- name: Upload template coverage
  uses: codecov/codecov-action@v4
  with:
    files: template-coverage.lcov
    flags: templates
```

### GitLab CI

```yaml
test:
  script:
    - pytest --tb=short
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: template-coverage.xml
```

## See Also

- [[docs/advanced/profiling|Profiling]] — Render-time instrumentation
- [[docs/advanced/analysis|Static Analysis]] — Dependency and purity analysis
