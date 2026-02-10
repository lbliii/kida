# RFC: Optional C Extension for HTML Escaping

**Status**: Draft  
**Created**: 2026-02-10  
**Updated**: 2026-02-10  
**Related**: Gap Analysis — Kida/Chirp Strategic Plan, `rfc-performance-optimization.md`  
**Priority**: P2 (measurable performance gain, small scope)

---

## Executive Summary

Kida's pure Python `_escape_str()` (`src/kida/utils/html.py:478-499`) uses
`str.translate()` for O(n) single-pass escaping. This is already well-optimized,
but on medium templates (~100 escaped variables), HTML escaping becomes the
dominant cost and Jinja2's markupsafe C extension pulls ahead.

This RFC proposes an optional C extension (`kida[fast]`) that accelerates
`_escape_str()` without adding a runtime dependency. Zero-dep remains the
default. The C extension is explicit opt-in.

| Change | Scope | Effort |
|--------|-------|--------|
| C extension for `_escape_str()` | New `src/kida/_cescape.c` | Medium |
| Conditional import in `utils/html.py` | 5-line change | Low |
| `[fast]` extra in `pyproject.toml` | 1 line | Trivial |
| Benchmark comparison | `benchmarks/` | Low |

---

## Problem

### Current State

`_escape_str()` is a one-liner (`src/kida/utils/html.py:499`):

```python
def _escape_str(s: str) -> str:
    return s.translate(_ESCAPE_TABLE)
```

`html_escape()` wraps it with type dispatch — skip Markup, skip `__html__`,
skip numerics, then call `_escape_str()` (`src/kida/utils/html.py:515-564`).

### Performance Profile

From the existing performance RFC (`plan/rfc-performance-optimization.md:95-108`):

- Small templates: Kida is 1.5x-3.6x faster than Jinja2 (compilation +
  StringBuilder dominate)
- Medium templates (~100 vars): Kida is at parity with Jinja2 (escaping
  dominates)
- Large templates: Kida is 1.1x faster (escaping is a smaller fraction)

The bottleneck is `str.translate()` vs markupsafe's hand-tuned C
`_speedups.c` which:
1. Scans for characters needing escaping in a single pass
2. Pre-allocates the output buffer based on the scan
3. Copies in a tight C loop

CPython's `str.translate()` is general-purpose — it handles arbitrary
mapping tables, not just the 6 HTML escape characters. A specialized C
function can be 3-5x faster for the HTML escaping case.

### Why Not Just Use markupsafe?

1. **Zero-dependency principle** — Kida's core value proposition includes
   no runtime dependencies.
2. **Markup class divergence** — Kida's `Markup` has features markupsafe
   doesn't (NUL stripping, attribute validation, context-specific escaping).
3. **Security model** — Kida strips NUL bytes (`\x00`) during escaping.
   markupsafe does not.

---

## Proposed Design

### C Extension

A single C file implementing `_escape_str()` with Kida's exact semantics:

```c
/* src/kida/_cescape.c */

/*
 * Escapes &, <, >, ", ' and strips NUL bytes.
 * Matches kida.utils.html._escape_str() behavior exactly.
 */

static const char *ESCAPE_TABLE[256] = {NULL};
/* & → &amp;   < → &lt;   > → &gt;   " → &quot;   ' → &#x27;   \0 → (skip) */

static PyObject *
kida_escape_str(PyObject *self, PyObject *arg)
{
    /* Fast path: scan for escapable chars */
    /* If none found, return input string (INCREF, no copy) */
    /* Slow path: single-pass escape with pre-allocated buffer */
}
```

Key implementation details:

1. **Fast path for clean strings**: Scan the input for any of the 6 escape
   characters + NUL. If none found, `Py_INCREF` and return the original
   string object (zero-copy).
2. **Pre-allocated output**: Count escape expansions during scan, allocate
   exact buffer size, copy in one pass. No realloc.
3. **NUL byte stripping**: Matches `_ESCAPE_TABLE` which maps `\x00` to `""`
   (`src/kida/utils/html.py:33-42`).
4. **Free-threading safe**: No global state. The function is pure — same input
   always produces same output.

### Conditional Import

In `src/kida/utils/html.py`, replace the direct definition with a conditional:

```python
try:
    from kida._cescape import _escape_str  # C extension (kida[fast])
except ImportError:
    def _escape_str(s: str) -> str:
        """Pure Python fallback — O(n) single-pass str.translate()."""
        return s.translate(_ESCAPE_TABLE)
```

Everything else in the module stays the same. `html_escape()`,
`html_escape_filter()`, and the `Markup` class all call `_escape_str()` —
they get the speedup automatically.

### pyproject.toml

```toml
[project.optional-dependencies]
fast = []  # C extension is built-in when installed from source

[tool.setuptools.ext-modules]
# Built via setuptools — only when installing kida[fast]
# The extension is optional; sdist includes the C source
```

Actually, since this is a C extension that compiles from source, the better
approach is to use a build flag. The extension is always included in the
source distribution but only compiled when the `fast` extra is requested or
when a C compiler is available:

```toml
[build-system]
requires = ["setuptools>=75.0"]

[project.optional-dependencies]
fast = []  # Marker for "build with C extensions"
```

The `setup.py` or build hook checks for the `fast` extra and includes the
extension module. If compilation fails (no C compiler), fall back gracefully
to pure Python.

### Alternative: Use markupsafe as Optional Accelerator

A simpler approach: detect markupsafe at import time and use its escaping
for the hot path, while keeping Kida's NUL-stripping as a post-process:

```python
try:
    from markupsafe import _speedups
    _ms_escape = _speedups.escape

    def _escape_str(s: str) -> str:
        # markupsafe escape + NUL stripping
        escaped = str(_ms_escape(s))
        return escaped.replace("\x00", "") if "\x00" in escaped else escaped

except ImportError:
    def _escape_str(s: str) -> str:
        return s.translate(_ESCAPE_TABLE)
```

**Pros**: No C code to maintain. markupsafe is battle-tested.
**Cons**: markupsafe doesn't strip NUL bytes (need post-process). Adds an
external dependency (even if optional). Less control over future optimization.

**Recommendation**: Start with the markupsafe accelerator (simpler), then
evaluate whether a custom C extension is worth the maintenance cost based on
benchmark data.

---

## Testing Strategy

1. **Equivalence tests**: For every input, `_escape_str_c(s) == _escape_str_py(s)`.
   Use Hypothesis to generate random strings including NUL bytes, unicode,
   and all escape characters.
2. **Benchmark tests**: Compare C extension vs pure Python vs markupsafe on
   small (10 char), medium (1KB), and large (100KB) strings.
3. **Security tests**: Verify NUL byte stripping, all 6 escape characters,
   and edge cases (empty string, only escape chars, only NUL bytes).
4. **Free-threading tests**: Run escaping from multiple threads concurrently,
   verify no data races.

---

## Expected Impact

Based on markupsafe benchmarks and the current performance profile:

| Template size | Current (pure Python) | Expected (C extension) | Improvement |
|--------------|----------------------|----------------------|-------------|
| Small (10 vars) | 1.5-3.6x faster than Jinja2 | 2-4x faster | Marginal |
| Medium (100 vars) | ~1x (parity) | 1.5-2x faster | Significant |
| Large (500+ vars) | 1.1x faster | 1.5-2x faster | Moderate |

The medium-template case is where this matters most — it's the common case
for web applications (forms, tables, dashboards).

---

## Future Considerations

1. **Context-specific C extensions**: `_js_escape_str()` and `_css_escape_str()`
   could also benefit from C acceleration.
2. **SIMD escaping**: For very large strings, AVX2/NEON vectorized scanning
   could provide further speedup. Likely overkill for templates.
3. **Cython alternative**: If maintenance cost of raw C is too high, Cython
   could generate the extension with less effort.
