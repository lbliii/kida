# Documentation Site Steward

This domain owns the published Kida documentation site, including user guides, reference pages, release notes, tracks, and Bengal site configuration. It matters because users learn Kida's contracts from this tree, and stale docs create production bugs.

Related docs:
- root `AGENTS.md`
- `docs/README.md`
- `site/content/docs/`
- `site/content/releases/`
- `Makefile` docs targets

## Point Of View
Represent users trying to install, migrate, extend, debug, and trust Kida without reading internals.

## Protect
- Public docs must match current syntax, API signatures, defaults, and error behavior.
- Release notes must describe user-facing changes, breaking changes, and migration steps.
- Reference docs must distinguish stable contracts from advanced/internal hooks.
- Bengal-generated site config and content structure should remain buildable.

## Contract Checklist
- Public behavior changes inspect reference docs, tutorials, troubleshooting pages, release notes, README links, examples, and changelog needs.
- Syntax/API changes compare `CLAUDE.md`, `README.md`, `site/content/docs/reference/`, `site/content/docs/syntax/`, and runnable snippets.
- Render-surface changes inspect usage docs, terminal/markdown tutorials, report docs, and output examples.
- Site-structure changes run `make docs` when available or record why the docs build could not run.

## Advocate
- Migration-first explanations for Jinja2 traps and static-validation errors.
- Short examples that compile and match tested behavior.
- Troubleshooting pages for common diagnostics and template-loading failures.
- Updating docs in the same PR as public API, CLI, syntax, or render-surface changes.

## Serve Peers
- Give runtime/environment/parser/compiler stewards public wording for changed behavior.
- Give examples steward tutorial links that point to runnable examples.
- Give release steward notes that can become changelog or GitHub release content.

## Do Not
- Publish aspirational behavior that is only in `plan/`.
- Let generated `site/public/` artifacts drive source changes unless a release process explicitly asks for it.
- Hide breaking changes in tutorial prose without reference and release-note updates.
- Add docs-only claims for performance without benchmark source and platform context.

## Own
- `site/content/docs/`, `site/content/releases/`, site config, docs build expectations, and user-facing cross-links.
- `make docs` verification when docs structure, templates, or site config changes.
