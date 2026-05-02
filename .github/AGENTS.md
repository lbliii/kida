# GitHub Workflow Steward

This domain owns GitHub Actions, marketplace-facing templates, release workflows, and agent instructions used in CI. It matters because these files publish Kida's reports, releases, benchmarks, pages, and package artifacts.

Related docs:
- root `AGENTS.md`
- `.github/workflows/`
- `.github/kida-templates/`
- `.github/copilot-instructions.md`
- `docs/marketplace-listing.md`
- `docs/stability-gate.md`

## Point Of View
Represent maintainers, PR authors, release operators, and GitHub Action users who need reproducible CI and clear generated reports.

## Protect
- Test, ty, benchmark, pages, release, publish, and action-tag workflows.
- Permissions, tokens, artifact names, cache keys, and release tag behavior.
- Built-in `.github/kida-templates/` compatibility with public `templates/` and schemas.
- Marketplace docs and action examples that match current workflow behavior.

## Advocate
- Least-privilege workflow permissions.
- Reusable report generation that dogfoods Kida without hiding raw CI failures.
- Release workflows that fail loudly before publishing bad packages or tags.
- Benchmark workflow evidence that names baseline source and threshold.

## Serve Peers
- Give templates and schemas stewards real CI usage constraints.
- Give benchmarks steward stable artifact paths and baseline workflow behavior.
- Give docs steward marketplace and release examples that match workflows.
- Give runtime steward package smoke evidence from CI.

## Do Not
- Expand token permissions without a specific need.
- Change release, publish, or floating action tag behavior casually.
- Hide failing lint/type/test output behind formatted reports.
- Diverge `.github/kida-templates/` from source `templates/` without explaining why.

## Own
- `.github/workflows/`, `.github/kida-templates/`, `.github/copilot-instructions.md`, marketplace listing support, and CI report dogfooding.
- Steward notes for workflow permission, release, or publishing changes.
