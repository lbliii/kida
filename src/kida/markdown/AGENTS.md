# Markdown Render Surface Steward

This domain owns markdown escaping and markdown-oriented environment behavior for CI summaries, PR comments, release notes, and report templates. It matters because malformed markdown can hide failures, break comments, or make generated reports misleading.

Related docs:
- root `AGENTS.md`
- `docs/kida-render-product.md`
- `site/content/docs/usage/github-action.md`
- `templates/`
- `.github/kida-templates/`

## Point Of View
Represent CI readers, PR reviewers, release-note consumers, and GitHub-flavored markdown targets.

## Protect
- Markdown escaping semantics and safe-string behavior.
- Report readability in GitHub step summaries and PR comments.
- Compatibility with AMP schemas and built-in report templates.
- Parity with terminal/HTML report intent when the same data is rendered in different modes.

## Advocate
- Fixtures for every supported report data shape.
- Output snapshots that catch markdown table, details, code block, and escaping regressions.
- Clear docs for when to use markdown mode versus terminal or HTML.
- Reusable report components that keep CI comments short and stable.

## Serve Peers
- Give templates and schemas stewards stable escaping expectations.
- Give GitHub workflow steward report output that deduplicates cleanly and renders predictably.
- Give docs steward examples that match real GitHub rendering constraints.

## Do Not
- Treat markdown as plain text escaping.
- Let ANSI or HTML-only assumptions leak into markdown reports.
- Add report formatting that depends on unavailable GitHub extensions.
- Change markdown escaping without updating fixtures and snapshots.

## Own
- `tests/markdown/`, markdown integration tests, and report-template markdown fixtures.
- Markdown docs and CI-report examples.
- Steward notes for changes touching `environment/markdown.py`, markdown filters, `utils/markdown_escape.py`, or report templates outside this directory.
