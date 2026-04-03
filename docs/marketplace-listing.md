# GitHub Actions Marketplace Listing Guide

Steps to list the Kida Report action on GitHub Marketplace.

## Prerequisites

- [x] `action.yml` with `name`, `description`, `branding` (icon + color)
- [x] 7 built-in templates in `templates/`
- [x] Composite action with Python setup, install, render, and post steps
- [x] PR comment deduplication via HTML markers
- [x] Self-dogfooded in `.github/workflows/tests.yml`

## Listing Steps

1. Go to **github.com/lbliii/kida** > Releases > Draft a new release
2. Check **"Publish this action to the GitHub Marketplace"**
3. GitHub will validate `action.yml` and show the marketplace form
4. Fill in:
   - **Primary category**: Code quality
   - **Secondary category**: Continuous integration
5. Publish the release (e.g., v0.3.2 or the next tag)

## Marketplace Description

Use this as the short description (appears in search results):

> Render CI reports from pytest, coverage, ruff, and other tools as GitHub step summaries and PR comments. 7 built-in templates, custom template support, JUnit XML / JSON / SARIF / LCOV parsing.

## Search Keywords

These should appear naturally in the description and README:

- CI report
- test results
- coverage report
- PR comment
- step summary
- pytest
- junit xml
- sarif
- code quality
- template

## Screenshot Suggestions

For the marketplace listing, include:

1. **Step summary** — Screenshot of a rendered pytest report in GitHub Actions
2. **PR comment** — Screenshot of a coverage report posted as PR comment
3. **Custom template** — Example of a branded custom report

## Quick-Start YAML (for marketplace page)

```yaml
name: CI Report
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run tests
        run: pytest --junitxml=results.xml --cov --cov-report=json

      - name: Post test report
        if: always()
        uses: lbliii/kida@v0.3.2
        with:
          template: pytest
          data: results.xml
          data-format: junit-xml

      - name: Post coverage report
        if: always()
        uses: lbliii/kida@v0.3.2
        with:
          template: coverage
          data: coverage.json
          post-to: step-summary,pr-comment
```
