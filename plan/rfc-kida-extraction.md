# RFC: Kida Extraction to Standalone Package

**Status**: Ready for Implementation  
**Created**: 2026-01-04  
**Updated**: 2026-01-04  
**Author**: Bengal Contributors

---

## Executive Summary

Extract Kida, Bengal's next-generation template engine, into a standalone Python package at `github.com/lbliii/kida`. This enables broader adoption as a modern, free-threaded Jinja2 alternative while Bengal becomes a consumer of the external package.

**Key Metrics:**
- **50 source files** to extract
- **46 test files** + fixtures
- **1 Bengal-specific import** to remove (`bengal.utils.lru_cache`)
- **170 internal imports** to transform (`bengal.rendering.kida.` → `kida.`)

---

## Background

Kida is a pure-Python template engine designed for free-threaded Python 3.14t+. Key features:

- **AST-native compilation** — Generates `ast.Module` directly (no string manipulation)
- **StringBuilder rendering** — 25-40% faster than Jinja2's generator yields
- **Free-threading ready** — GIL-independent via `_Py_mod_gil = 0`
- **Modern syntax** — Unified `{% end %}`, pattern matching, pipelines
- **Native async** — True async/await (no `auto_await()` wrappers)

Currently embedded at `bengal/rendering/kida/`, making it unavailable to the broader Python ecosystem.

### Architecture

```
Template Source → Lexer → Parser → Kida AST → Compiler → Python AST → exec()
```

Unlike Jinja2 which generates Python source strings, Kida generates `ast.Module` objects directly, enabling:
- Structured code manipulation
- Compile-time optimization
- Precise error source mapping

---

## Goals

1. **Standalone package**: `pip install kida` works independently
2. **Zero external dependencies**: Pure Python, no runtime deps
3. **Backward compatibility**: Bengal continues working via external import
4. **Clean separation**: No Bengal-specific code in kida

### Non-Goals

- Changing Kida API
- Adding new features during extraction
- Supporting Python < 3.14

---

## Current State Analysis

### Source Files (50 files)

```
bengal/rendering/kida/
├── __init__.py          # Main API (Environment, Template, etc.)
├── _types.py            # Token, TokenType
├── lexer.py             # Lexer, LexerConfig, tokenize()
├── nodes.py             # Immutable AST node definitions
├── template.py          # Template class with render()
├── tstring.py           # Template string utilities
├── bytecode_cache.py    # Bytecode caching for cold starts
├── py.typed             # PEP 561 type marker
├── analysis/            # Template introspection (7 files)
│   ├── __init__.py
│   ├── analyzer.py      # BlockAnalyzer
│   ├── cache.py         # Cache scope inference
│   ├── config.py        # AnalysisConfig
│   ├── dependencies.py  # DependencyWalker
│   ├── landmarks.py     # LandmarkDetector
│   ├── metadata.py      # BlockMetadata, TemplateMetadata
│   ├── purity.py        # PurityAnalyzer
│   └── roles.py         # classify_role()
├── compiler/            # Kida AST → Python AST (10 files)
│   ├── __init__.py
│   ├── core.py          # Compiler class
│   ├── expressions.py   # Expression compilation
│   ├── utils.py         # Operator utilities
│   └── statements/
│       ├── __init__.py
│       ├── basic.py
│       ├── control_flow.py
│       ├── functions.py
│       ├── special_blocks.py
│       ├── template_structure.py
│       └── variables.py
├── environment/         # Environment, loaders, filters (9 files)
│   ├── __init__.py
│   ├── core.py          # Environment class ⚠️ Bengal dependency
│   ├── exceptions.py    # TemplateSyntaxError, UndefinedError, etc.
│   ├── filters.py       # Built-in filters
│   ├── loaders.py       # FileSystemLoader, etc.
│   ├── protocols.py     # Loader protocol
│   ├── registry.py      # FilterRegistry
│   └── tests.py         # Built-in tests (is_defined, etc.)
├── parser/              # Tokens → Kida AST (14 files)
│   ├── __init__.py
│   ├── core.py          # Parser class
│   ├── errors.py        # Parse error handling
│   ├── expressions.py   # Expression parsing
│   ├── statements.py    # Statement parsing
│   ├── tokens.py        # Token navigation
│   └── blocks/
│       ├── __init__.py
│       ├── control_flow.py
│       ├── core.py
│       ├── functions.py
│       ├── special_blocks.py
│       ├── template_structure.py
│       └── variables.py
└── utils/               # Utilities (2 files)
    ├── __init__.py
    └── html.py          # HTML escaping
```

### Test Files (46 files)

```
tests/rendering/kida/           # Main test suite
├── conftest.py
├── test_kida_*.py              # 35+ test files
├── analysis/
│   └── test_block_analyzer.py

tests/unit/rendering/kida/
├── test_dispatch_table.py

tests/kida/
├── test_while.py

tests/unit/rendering/
├── test_kida_thread_safety.py
├── test_template_cycles.py

tests/themes/
├── test_default_theme_kida.py
```

### Bengal Dependencies (to remove)

**1. `environment/core.py:33`** — LRU cache utility:
```python
from bengal.utils.lru_cache import LRUCache
```

**Fix**: The `LRUCache` implementation is self-contained with no Bengal dependencies. Options:
1. **Copy LRUCache** to `kida/utils/lru_cache.py` (recommended - keeps zero deps)
2. **Use functools.lru_cache** + wrapper (less flexible, no TTL support)

The LRUCache is ~228 lines, generic, and explicitly designed to be portable:
```python
# From bengal/utils/lru_cache.py docstring:
# "Zero dependencies on Bengal internals (portable to Kida or elsewhere)"
```

---

## Implementation Plan

### Phase 1: Prepare Kida Repository

**Target**: `/Users/llane/Documents/github/python/kida/`

1. **Create package structure**:
   ```
   kida/
   ├── pyproject.toml
   ├── README.md
   ├── LICENSE
   ├── src/
   │   └── kida/
   │       ├── __init__.py
   │       ├── py.typed
   │       └── ... (all source files)
   └── tests/
       └── ... (all test files)
   ```

2. **Create `pyproject.toml`**:
   ```toml
   [build-system]
   requires = ["setuptools>=61.0"]
   build-backend = "setuptools.build_meta"

   [project]
   name = "kida"
   version = "0.1.0"
   description = "Modern template engine for Python 3.14t — AST-native, free-threading ready"
   readme = "README.md"
   requires-python = ">=3.14"
   license = "MIT"
   keywords = ["template-engine", "jinja2", "free-threading", "async"]
   classifiers = [
       "Development Status :: 4 - Beta",
       "Intended Audience :: Developers",
       "Programming Language :: Python :: 3.14",
       "Topic :: Internet :: WWW/HTTP :: Dynamic Content :: CGI Tools/Libraries",
       "Topic :: Text Processing :: Markup :: HTML",
       "Typing :: Typed",
   ]
   dependencies = []  # Pure Python, no runtime deps

   [project.optional-dependencies]
   dev = [
       "pytest>=8.0",
       "pytest-asyncio>=0.23",
       "pyright>=1.1",
   ]

   [project.urls]
   Homepage = "https://github.com/lbliii/kida"
   Documentation = "https://github.com/lbliii/kida"
   Repository = "https://github.com/lbliii/kida"
   Changelog = "https://github.com/lbliii/kida/blob/main/CHANGELOG.md"

   [tool.setuptools.packages.find]
   where = ["src"]

   [tool.pytest.ini_options]
   testpaths = ["tests"]
   asyncio_mode = "auto"
   asyncio_default_fixture_loop_scope = "function"

   [tool.pyright]
   include = ["src"]
   pythonVersion = "3.14"
   typeCheckingMode = "strict"
   ```

3. **Create README.md** with:
   - Feature overview (AST-native, free-threading, zero dependencies)
   - Quick start examples
   - Syntax overview
   - API reference

### Phase 2: Copy and Transform Source

1. **Pre-extraction cleanup** (optional but recommended):
   ```bash
   # Remove empty directories that shouldn't be extracted
   rmdir bengal/rendering/kida/optimizer 2>/dev/null || true
   ```

2. **Copy source files**:
   ```bash
   cp -r bengal/rendering/kida/* kida/src/kida/
   ```

4. **Copy LRUCache utility**:
   ```bash
   mkdir -p kida/src/kida/utils
   cp bengal/utils/lru_cache.py kida/src/kida/utils/lru_cache.py
   ```

5. **Transform imports** (automated via script):
   ```python
   # Before
   from bengal.rendering.kida._types import Token, TokenType
   from bengal.utils.lru_cache import LRUCache

   # After
   from kida._types import Token, TokenType
   from kida.utils.lru_cache import LRUCache
   ```

6. **Update all internal module paths** (170 import statements across 37 files):
   - `from bengal.rendering.kida.` → `from kida.`
   - `import bengal.rendering.kida.` → `import kida.`

7. **Skip empty directories** (e.g., `optimizer/`):
   - The extraction script automatically skips directories with no `.py` files

### Phase 3: Copy and Transform Tests

1. **Copy test files**:
   ```bash
   # Main test suite
   cp -r tests/rendering/kida/* kida/tests/

   # Unit tests
   cp tests/unit/rendering/kida/* kida/tests/unit/
   cp tests/unit/rendering/test_kida_thread_safety.py kida/tests/
   cp tests/unit/rendering/test_template_cycles.py kida/tests/

   # Additional tests
   cp tests/kida/* kida/tests/
   ```

2. **Transform test imports**:
   ```python
   # Before
   from bengal.rendering.kida import Environment

   # After
   from kida import Environment
   ```

3. **Verify test suite passes**:
   ```bash
   cd kida && pytest
   ```

### Phase 4: Update Bengal

1. **Add kida dependency** to `pyproject.toml`:
   ```toml
   dependencies = [
       "kida>=0.1.0",
       # ... existing deps
   ]
   ```

2. **Update Bengal engine adapter** (`bengal/rendering/engines/kida.py`):
   ```python
   # Before
   from bengal.rendering.kida import Environment
   from bengal.rendering.kida.environment import FileSystemLoader

   # After
   from kida import Environment
   from kida.environment import FileSystemLoader
   ```

3. **Update all other Bengal imports**:
   - Perform a global search and replace in the Bengal repository:
     - `from bengal.rendering.kida` → `from kida`
     - `import bengal.rendering.kida` → `import kida`

4. **Delete embedded kida source and tests**:
   ```bash
   rm -rf bengal/rendering/kida/
   rm -rf tests/rendering/kida/
   rm -rf tests/unit/rendering/kida/
   rm -rf tests/kida/
   ```

### Phase 5: Validation

1. **Run automated verification**:
   ```bash
   cd kida
   python scripts/extract_kida.py --verify
   ```

2. **Run kida test suite** in standalone repo:
   ```bash
   cd kida && uv sync && pytest -v
   ```

3. **Run Bengal test suite** with external kida dependency:
   ```bash
   cd bengal && uv sync && pytest -v
   ```

4. **Verify import overhead unchanged** (kida already has lazy loading patterns):
   ```bash
   python -c "import time; t=time.perf_counter(); import kida; print(f'{(time.perf_counter()-t)*1000:.1f}ms')"
   # Should be <50ms
   ```

5. **Test template compilation and rendering** works correctly:
   ```bash
   python -c "from kida import Environment; e=Environment(); print(e.from_string('Hello {{ name }}').render(name='World'))"
   ```

6. **Verify no remaining Bengal imports in kida**:
   ```bash
   grep -r "from bengal\|import bengal" kida/src/
   # Should return empty
   ```

7. **Verify type checking passes** in kida:
   ```bash
   cd kida && pyright src/
   ```

### Phase 6: Publish (optional, after validation)

1. **Test PyPI first**:
   ```bash
   cd kida
   uv build
   uv publish --publish-url https://test.pypi.org/legacy/
   ```

2. **Verify installation from TestPyPI**:
   ```bash
   pip install -i https://test.pypi.org/simple/ kida
   ```

3. **Publish to PyPI**:
   ```bash
   uv publish
   ```

---

## Migration Script

Create `scripts/extract_kida.py`:

```python
#!/usr/bin/env python3
"""Extract kida from Bengal to standalone package.

Usage:
    python scripts/extract_kida.py           # Execute extraction
    python scripts/extract_kida.py --dry-run # Preview without writing
    python scripts/extract_kida.py --verify  # Verify extraction succeeded
"""

import argparse
import shutil
import sys
from pathlib import Path
import re

BENGAL_ROOT = Path("/Users/llane/Documents/github/python/bengal")
KIDA_ROOT = Path("/Users/llane/Documents/github/python/kida")

# Import transformations
IMPORT_TRANSFORMS: list[tuple[str, str]] = [
    (r"from bengal\.rendering\.kida\.", "from kida."),
    (r"import bengal\.rendering\.kida\.", "import kida."),
    (r"bengal\.rendering\.kida\.", "kida."),
    (r"from bengal\.utils\.lru_cache", "from kida.utils.lru_cache"),
]

# Files/dirs to skip (empty or not needed)
SKIP_DIRS = {"__pycache__", "optimizer"}


def transform_file(content: str) -> str:
    """Apply all transformations to file content."""
    for pattern, replacement in IMPORT_TRANSFORMS:
        content = re.sub(pattern, replacement, content)
    return content


def should_skip(path: Path) -> bool:
    """Check if path should be skipped."""
    return any(skip in path.parts for skip in SKIP_DIRS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract Kida from Bengal")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--verify", action="store_true", help="Verify extraction")
    args = parser.parse_args()

    if args.verify:
        verify_extraction()
        return

    src_dir = KIDA_ROOT / "src" / "kida"
    test_dir = KIDA_ROOT / "tests"

    if args.dry_run:
        print("🔍 DRY RUN - No files will be written\n")
    else:
        src_dir.mkdir(parents=True, exist_ok=True)
        test_dir.mkdir(parents=True, exist_ok=True)

    stats = {"source": 0, "tests": 0, "skipped": 0, "transforms": 0}

    # 1. Copy and transform source files
    print("📦 Source files:")
    source_src = BENGAL_ROOT / "bengal" / "rendering" / "kida"
    for py_file in source_src.rglob("*.py"):
        if should_skip(py_file):
            stats["skipped"] += 1
            continue

        rel_path = py_file.relative_to(source_src)
        dest_path = src_dir / rel_path

        content = py_file.read_text()
        transformed = transform_file(content)
        transform_count = len(content) - len(transformed.replace("kida.", "bengal.rendering.kida."))

        if not args.dry_run:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_text(transformed)

        stats["source"] += 1
        print(f"  ✓ {rel_path}")

    # 2. Copy py.typed marker
    if not args.dry_run:
        shutil.copy(source_src / "py.typed", src_dir / "py.typed")
    print("  ✓ py.typed")

    # 3. Copy LRU cache utility
    print("\n📦 Utilities:")
    utils_dir = src_dir / "utils"
    if not args.dry_run:
        utils_dir.mkdir(exist_ok=True)

    lru_cache_src = BENGAL_ROOT / "bengal" / "utils" / "lru_cache.py"
    if not args.dry_run:
        content = lru_cache_src.read_text()
        (utils_dir / "lru_cache.py").write_text(content)
        (utils_dir / "__init__.py").write_text(
            '"""Kida utilities."""\n\n'
            'from kida.utils.lru_cache import LRUCache\n\n'
            '__all__ = ["LRUCache"]\n'
        )
    print("  ✓ utils/lru_cache.py")
    print("  ✓ utils/__init__.py")

    # 4. Copy and transform tests
    print("\n🧪 Test files:")
    test_sources = [
        (BENGAL_ROOT / "tests" / "rendering" / "kida", test_dir),
        (BENGAL_ROOT / "tests" / "unit" / "rendering" / "kida", test_dir / "unit"),
        (BENGAL_ROOT / "tests" / "kida", test_dir / "misc"),
    ]

    for source_dir, dest_base in test_sources:
        if not source_dir.exists():
            continue
        for py_file in source_dir.rglob("*.py"):
            if should_skip(py_file):
                stats["skipped"] += 1
                continue

            rel_path = py_file.relative_to(source_dir)
            dest_path = dest_base / rel_path

            content = py_file.read_text()
            transformed = transform_file(content)

            if not args.dry_run:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                dest_path.write_text(transformed)

            stats["tests"] += 1
            print(f"  ✓ {dest_base.name}/{rel_path}")

    # 5. Copy standalone tests
    standalone_tests = [
        BENGAL_ROOT / "tests" / "unit" / "rendering" / "test_kida_thread_safety.py",
        BENGAL_ROOT / "tests" / "unit" / "rendering" / "test_template_cycles.py",
    ]
    for test_file in standalone_tests:
        if test_file.exists():
            content = test_file.read_text()
            transformed = transform_file(content)
            if not args.dry_run:
                (test_dir / test_file.name).write_text(transformed)
            stats["tests"] += 1
            print(f"  ✓ {test_file.name}")

    # Summary
    print(f"\n{'📋 DRY RUN SUMMARY' if args.dry_run else '✅ EXTRACTION COMPLETE'}")
    print(f"   Source files: {stats['source']}")
    print(f"   Test files:   {stats['tests']}")
    print(f"   Skipped:      {stats['skipped']}")

    if not args.dry_run:
        print(f"\n📍 Extracted to: {KIDA_ROOT}")
        print("\n🚀 Next steps:")
        print("   1. cd kida && uv sync")
        print("   2. pytest")
        print("   3. pyright src/")
        print("   4. python scripts/extract_kida.py --verify")


def verify_extraction() -> None:
    """Verify extraction succeeded."""
    print("🔍 Verifying extraction...\n")
    errors = []

    src_dir = KIDA_ROOT / "src" / "kida"

    # Check for Bengal imports
    for py_file in src_dir.rglob("*.py"):
        content = py_file.read_text()
        if "from bengal" in content or "import bengal" in content:
            rel_path = py_file.relative_to(KIDA_ROOT)
            errors.append(f"Bengal import found in {rel_path}")

    # Check key files exist
    required = [
        src_dir / "__init__.py",
        src_dir / "py.typed",
        src_dir / "environment" / "core.py",
        src_dir / "utils" / "lru_cache.py",
    ]
    for path in required:
        if not path.exists():
            errors.append(f"Missing required file: {path.relative_to(KIDA_ROOT)}")

    if errors:
        print("❌ Verification failed:")
        for error in errors:
            print(f"   • {error}")
        sys.exit(1)
    else:
        print("✅ Verification passed!")
        print("   • No Bengal imports found")
        print("   • All required files present")


if __name__ == "__main__":
    main()
```

---

## Files Changed Summary

### Kida Repository (new)

| Path | Action | Notes |
|------|--------|-------|
| `pyproject.toml` | Create | Package metadata, dev deps, tool config |
| `README.md` | Create | Feature docs, examples |
| `LICENSE` | Create | MIT license |
| `CHANGELOG.md` | Create | Version history |
| `scripts/extract_kida.py` | Copy from Bengal | Extraction script with --verify |
| `src/kida/**/*.py` | Copy + Transform | 50 files, import path changes |
| `src/kida/utils/lru_cache.py` | Copy | LRUCache utility (no transforms) |
| `tests/**/*.py` | Copy + Transform | 46 files |

### Bengal Repository (updates)

| Path | Action | Notes |
|------|--------|-------|
| `pyproject.toml` | Update | Add `kida>=0.1.0` dependency |
| `bengal/rendering/kida/` | Delete | Remove embedded source immediately |
| `tests/rendering/kida/` | Delete | Tests move to kida repo |
| `tests/unit/rendering/kida/` | Delete | Tests move to kida repo |
| `tests/kida/` | Delete | Tests move to kida repo |
| `bengal/rendering/engines/kida.py` | Update | External import |
| `bengal/rendering/engines/__init__.py` | Update | External import |
| Other Bengal files | Update | Global search/replace for imports |

---

## Related Files

### Bengal files importing kida (verified, will need updates)

**Core Bengal Engine Integration:**
```
bengal/rendering/engines/kida.py
bengal/rendering/engines/__init__.py
bengal/rendering/adapters/__init__.py
```

**Pipeline and Caching:**
```
bengal/rendering/pipeline/autodoc_renderer.py
bengal/rendering/block_cache.py
```

**Rosettes (syntax highlighting for Kida templates):**
```
bengal/rendering/rosettes/lexers/kida_sm.py  # Kida lexer for syntax highlighting
```

**Scripts and Benchmarks:**
```
scripts/test_kida_from_extends.py
scripts/test_kida_extends.py
benchmarks/test_kida_real_templates.py
benchmarks/test_kida_comprehensive.py
benchmarks/test_kida_vs_jinja.py
benchmarks/test_block_level_incremental.py
```

**Tests (remain in Bengal, update imports):**
```
tests/themes/test_default_theme_kida.py
```

**Documentation (update references):**
```
site/content/docs/theming/templating/kida/  # Update import examples
plan/rfc-kida-spec-driven-testing.md        # Update references
```

---

## Feature Comparison: Kida vs Jinja2

| Feature | Kida | Jinja2 |
|---------|------|--------|
| **Compilation** | AST → AST | String generation |
| **Rendering** | StringBuilder | Generator yields |
| **Block endings** | Unified `{% end %}` | Specific `{% endif %}`, `{% endfor %}` |
| **Scoping** | Explicit `let`/`set`/`export` | Implicit |
| **Async** | Native `async for`, `await` | `auto_await()` wrapper |
| **Pattern matching** | `{% match %}...{% case %}` | N/A |
| **Pipelines** | `{{ value \|> filter1 \|> filter2 }}` | N/A |
| **Caching** | `{% cache key %}...{% end %}` | N/A |
| **Free-threading** | Native (PEP 703) | N/A |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking Bengal builds | High | Phase 4-5 must be atomic; verify all imports updated via grep |
| Import overhead increase | Medium | Measure before/after (<50ms target); Kida already uses lazy patterns |
| Test fixture mismatches | Low | Copy fixtures alongside tests; run `--dry-run` first |
| Version drift | Low | Pin kida version in Bengal initially (`kida>=0.1.0,<0.2.0`) |
| Type checking breaks | Low | Verify pyright pass in standalone repo before merge |
| Rosettes kida_sm lexer | Low | Keep in Bengal for now; consider `kida[syntax]` extra later |
| Empty directories | Low | Script skips `optimizer/` and `__pycache__/` automatically |
| Documentation stale | Low | Update docs in Phase 4; add migration notes to kida pages |

---

## Success Criteria

1. ☐ `pip install kida` works
2. ☐ `from kida import Environment` works
3. ☐ Kida test suite passes (standalone)
4. ☐ Bengal test suite passes (with external kida)
5. ☐ No Bengal-specific code in kida (`grep -r "from bengal" kida/src/` returns empty)
6. ☐ Import overhead within 5% of current (<50ms cold start)
7. ☐ Type checking passes in kida repo (`pyright src/` returns 0 errors)
8. ☐ Verification script passes (`python scripts/extract_kida.py --verify`)

---

## Timeline Estimate

| Phase | Effort | Dependencies | Status |
|-------|--------|--------------|--------|
| Phase 1: Prepare repo | 1 hour | None | ☐ Pending |
| Phase 2: Extract source | 2 hours | Phase 1 | ☐ Pending |
| Phase 3: Extract tests | 1 hour | Phase 2 | ☐ Pending |
| Phase 4: Update Bengal | 3 hours | Phase 3 | ☐ Pending |
| Phase 5: Validation | 1.5 hours | Phase 4 | ☐ Pending |
| Phase 6: Publish | 0.5 hours | Phase 5 | ☐ Optional |
| **Total** | **~9 hours** | | |

### Documentation Migration (Post-Extraction)

Update references in Bengal documentation (`site/content/docs/theming/templating/kida/`):

1. Change import examples from:
   ```python
   from bengal.rendering.kida import Environment
   ```
   to:
   ```python
   from kida import Environment
   ```

2. Add migration note at top of each page:
   ```markdown
   :::note[Standalone Package]
   Kida is now available as a standalone package: `pip install kida`.
   Import paths changed from `bengal.rendering.kida` to `kida`.
   :::
   ```

3. Update cross-references in RFCs:
   - `plan/rfc-kida-spec-driven-testing.md` → update import paths

---

## Appendix: Kida Syntax Reference

### Basic Output
```kida
{{ variable }}
{{ user.name }}
{{ items[0] }}
```

### Control Flow
```kida
{% if condition %}
    ...
{% elif other %}
    ...
{% else %}
    ...
{% end %}

{% for item in items %}
    {{ item }}
{% else %}
    No items
{% end %}
```

### Pattern Matching
```kida
{% match status %}
{% case "active" %}
    Active user
{% case "pending" %}
    Pending verification
{% case _ %}
    Unknown status
{% end %}
```

### Pipelines
```kida
{{ title |> escape |> capitalize |> truncate(50) }}
```

### Functions
```kida
{% def greet(name, greeting="Hello") %}
    {{ greeting }}, {{ name }}!
{% end %}

{{ greet("World") }}
```

### Caching
```kida
{% cache "navigation" %}
    {% for item in nav_items %}
        <a href="{{ item.url }}">{{ item.title }}</a>
    {% end %}
{% end %}
```

### Template Inheritance
```kida
{# base.html #}
{% block content %}{% end %}

{# page.html #}
{% extends "base.html" %}
{% block content %}
    Page content here
{% end %}
```

### Async Support
```kida
{% async for item in fetch_items() %}
    {{ item }}
{% end %}

{{ await get_user() }}
```

---

## References

**Source Locations:**
- Kida source: `bengal/rendering/kida/` (50 files)
- Kida tests: `tests/rendering/kida/`, `tests/unit/rendering/kida/`, `tests/kida/` (46 files)
- Kida documentation: `site/content/docs/theming/templating/kida/`
- LRU cache: `bengal/utils/lru_cache.py` (portable, no Bengal deps)

**Related RFCs:**
- Rosettes extraction RFC: `plan/rfc-rosettes-extraction.md` (template for this RFC)
- Kida spec-driven testing: `plan/rfc-kida-spec-driven-testing.md` (update after extraction)

**Related Files:**
- Kida lexer for Rosettes: `bengal/rendering/rosettes/lexers/kida_sm.py`

**External Resources:**
- PEP 703: Making the Global Interpreter Lock Optional
- Jinja2 documentation: https://jinja.palletsprojects.com/
