# Kida 0.2.5 Release Notes

**Release date:** 2026-03-07

## Summary

Kida 0.2.5 focuses on performance, maintainability, and release automation. Highlights include a ~2µs improvement per `render_block()` call, filter modularization for easier maintenance, safer polymorphic `+` operator behavior, and a PyPI publish workflow with regression gates.

## What's New

### Performance

- **`render_block()` cache-hit optimization** — Lock removed from the cache-hit path in inherited block resolution. Cache-hit reads are now lock-free; the lock is only acquired on miss for double-check. Saves ~2µs per `render_block()` call in block-heavy templates.

### Improvements

- **Filter modularization** — Built-in filters are now organized into category submodules (`_collections`, `_debug`, `_html_security`, `_misc`, `_numbers`, `_string`, `_type_conversion`, `_validation`). The main `_impl.py` acts as a registry. Improves maintainability and makes it easier to add or modify filters.

- **Polymorphic `+` operator** — `add_polymorphic()` now preserves Python semantics for compatible types (`list + list`, `tuple + tuple`). Previously, mixed-type expressions like `{{ items + more_items }}` could silently stringify and produce huge output. String concatenation fallback (`{{ count + " items" }}`) still works when one operand is string-like.

- **Template refactor** — Inheritance logic extracted to `TemplateInheritanceMixin`; error enhancement to `enhance_template_error()` pure function. Attribute helpers (`safe_getattr`, `getattr_preserve_none`) moved to shared `helpers.py`.

### Documentation

- **Tests reference** — New reference page for all built-in tests (`defined`, `undefined`, `string`, `number`, `mapping`, comparison tests, HTMX tests, etc.).

- **Configuration reference** — Expanded docs for all `Environment` options.

### Release Automation

- **PyPI publish workflow** — `.github/workflows/python-publish.yml` runs on release publish. Executes a regression gate (expression tests, render output guards, benchmark compare) before building and uploading to PyPI.

- **Render output regression guards** — New test suite guards against empty render, loop count mismatches, include chain duplication, inheritance block duplication, and stream/render parity. These run as part of the release gate.

- **Benchmark dimensions** — New benchmark suites for static_context vs dynamic render, bytecode cache disk load, and introspection (template_metadata, list_blocks, get_template_structure, render_block). `benchmark_compare.sh` integrated into the release gate.

## Upgrade Notes

No breaking changes. The polymorphic `+` change affects only expressions where *both* operands are non-string and incompatible (e.g. `{{ count + items }}` when one is int and one is list). Previously these were silently stringified; now they raise `TypeError`. String concatenation (`{{ count + " items" }}`, `{{ name + "!" }}`) is unchanged.

## Full Changelog

See [CHANGELOG.md](CHANGELOG.md) for the complete list of changes.
