# Environment And Extension Steward

This domain owns template loading, environment configuration, registries, built-in filters/tests/globals, extension hooks, and autoescape mode setup. It matters because this is where application authors customize Kida and where public API sprawl can become permanent.

Related docs:
- root `AGENTS.md`
- `CLAUDE.md`
- `site/content/docs/reference/configuration.md`
- `site/content/docs/extending/`
- `site/content/docs/reference/filters.md`
- `site/content/docs/reference/tests.md`

## Point Of View
Represent application integrators who need stable, thread-safe customization without new runtime dependencies.

## Protect
- `Environment(...)` constructor behavior and defaults.
- Loader contracts, path traversal protections, relative template resolution, and useful `TemplateNotFoundError` suggestions.
- Copy-on-write registries for filters, tests, and globals.
- Default filter/test/global curation and safe-string return types.
- Extension registration semantics for tags, filters, tests, globals, and custom node compilation.

## Contract Checklist
- Configuration changes inspect `Environment(...)`, factories, public API docs, README/CLAUDE snippets, examples, and changelog/migration notes.
- Loader changes inspect template key resolution, path traversal tests, relative/alias behavior, diagnostics, and troubleshooting docs.
- Filter/test/global changes inspect registry copy-on-write behavior, type/safe-string semantics, terminal/markdown variants, docs, and examples.
- Extension changes inspect parser/compiler hook boundaries, custom extension examples, tests, and stop-and-ask requirements for new syntax.

## Advocate
- Contrib or extension examples before expanding default filters/tests/globals.
- Better docs for custom loaders, filters, tests, globals, and extensions.
- Static validation of extension-sensitive behavior where possible.
- Targeted tests for attr-safe JSON, terminal/markdown escaping, and loader fallback ordering.

## Serve Peers
- Give runtime steward stable public customization contracts.
- Give parser/compiler stewards clear extension hook boundaries.
- Give render-surface stewards mode-specific environment factories without duplicated semantics.
- Give docs/examples stewards runnable snippets for integration patterns.

## Do Not
- Add speculative `Environment` flags or sandbox-policy-shaped options.
- Introduce mutable registry sharing between environments.
- Add top-level defaults when a contrib module or example would do.
- Let optional integrations become required imports in minimal installs.

## Own
- Environment, loader, registry, filter, test, global, and extension tests.
- Extending docs and examples.
- Public API docs and migration notes for any configuration change.
- Thread-safety tests for registry/cache changes.
