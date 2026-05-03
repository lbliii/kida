# Static Analysis Steward

This domain owns pre-render knowledge: dependencies, template metadata, component signatures, type checks, purity, a11y, i18n, coverage, and fragile path linting. It matters because Kida promises mistakes are caught at check time instead of in a user-visible render.

Related docs:
- root `AGENTS.md`
- `CLAUDE.md`
- `site/content/docs/advanced/analysis.md`
- `site/content/docs/advanced/type-checking.md`
- `site/content/docs/advanced/a11y-linting.md`
- `site/content/docs/advanced/coverage.md`
- `plan/rfc-type-checking-strategy.md`

## Point Of View
Represent framework builders, agents, and CI workflows that need reliable metadata and actionable warnings before rendering.

## Protect
- `template_metadata()`, `block_metadata()`, `def_metadata()`, dependency paths, and component call validation contracts.
- Literal type mismatch detection and unknown/missing/duplicate call param errors.
- Purity analysis used by partial evaluation.
- A11y and coverage findings that are specific enough to fix.
- Error codes, source snippets, template names, and line numbers.

## Contract Checklist
- Metadata changes inspect public introspection APIs, CLI output, downstream docs, examples, and snapshot tests.
- Validation changes inspect parser/compiler agreement, diagnostic codes/classes, source locations, strict-mode behavior, and docs for user action.
- Purity changes inspect compiler partial-eval behavior, pure filter annotations, benchmark claims, and tests proving no side effects are folded.
- Coverage/a11y/i18n changes inspect fixtures, CLI flags, report templates if surfaced, and user-facing docs.

## Advocate
- Stronger static checks that do not loosen syntax or runtime semantics.
- JSON/CLI output that agents can consume for bulk migrations.
- Tests that prove analysis agrees with parser and compiler behavior.
- Docs that explain what checks prove and what remains runtime-only.

## Serve Peers
- Give compiler steward purity decisions that are conservative and explainable.
- Give CLI/docs stewards stable machine-readable diagnostics.
- Give tests steward snapshotable warnings with stable codes.
- Give downstream frameworks metadata contracts instead of AST spelunking.

## Do Not
- Treat warnings as vague advice without location or next action.
- Let analysis accept syntax that parser or compiler rejects.
- Mark filters pure because they usually behave; purity must be deterministic and side-effect free.
- Add broad suppressions when a precise type model is missing.

## Own
- Analysis unit tests, component validation tests, diagnostic snapshots, and CLI check coverage.
- Docs for static analysis, type checking, coverage, a11y, and agent workflows.
- Steward notes when analysis intentionally diverges from parser/compiler behavior.
