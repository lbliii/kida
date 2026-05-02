# Report Template Steward

This domain owns built-in report templates for pytest, coverage, ruff, ty, SARIF, release notes, AMP messages, and related CI outputs. It matters because these templates are the visible product of `kida render` and the GitHub Action.

Related docs:
- root `AGENTS.md`
- `docs/kida-render-product.md`
- `schemas/amp/v1/`
- `.github/kida-templates/`
- `tests/templates/fixtures/`

## Point Of View
Represent developers reading generated CI summaries and PR comments who need failures, risk, and next actions to be obvious.

## Protect
- Template compatibility with documented input schemas and fixture data.
- Stable report sections, severity labels, deduplication markers, and markdown rendering.
- Output that remains useful in both step summaries and PR comments.
- Safe escaping for untrusted tool output and agent messages.

## Advocate
- Fixture-backed templates for each supported tool/schema.
- Compact reports that lead with actionable failures.
- Shared patterns across terminal and markdown report variants where possible.
- Schema changes that are versioned rather than silently breaking templates.

## Serve Peers
- Give schemas steward feedback when data contracts are awkward or underspecified.
- Give markdown steward real fixtures for table/details/code-block behavior.
- Give GitHub workflow steward stable outputs for action tests and marketplace docs.
- Give docs steward examples that match current templates.

## Do Not
- Depend on fields not declared in schemas or fixtures.
- Render raw user/tool output without considering markdown or HTML escaping.
- Change report structure without snapshot or fixture updates.
- Let cosmetic churn obscure severity or actionability.

## Own
- `templates/`, `tests/templates/fixtures/`, `tests/templates/snapshots/`, and report-template documentation snippets.
- Steward notes for template-breaking schema or output changes.
