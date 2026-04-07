---
title: GitHub Action
description: Render CI reports from structured tool output as GitHub step summaries and PR comments
draft: false
weight: 25
lang: en
type: doc
tags:
- usage
- ci
- github-action
keywords:
- github action
- ci reports
- step summary
- pr comment
- pytest
- coverage
- ruff
icon: github
---

Render CI reports from structured tool output as GitHub step summaries and PR comments.

## Quick start

```yaml
- uses: lbliii/kida@v0.3.3
  with:
    template: pytest
    data: reports/pytest.xml
    data-format: junit-xml
```

## Built-in templates

| Template | Data format | Tool |
| --- | --- | --- |
| `pytest` | `junit-xml` | pytest `--junitxml` |
| `coverage` | `json` or `lcov` | pytest-cov `--cov-report=json` |
| `ruff` | `json` | ruff `--output-format json` |
| `ty` | `junit-xml` | ty `--output-format junit` |
| `jest` | `json` | jest `--json` |
| `gotest` | `junit-xml` | go-junit-report |
| `sarif` | `sarif` | CodeQL, Semgrep, Trivy, ESLint |

## Inputs

| Input | Required | Default | Description |
| --- | --- | --- | --- |
| `template` | yes | — | Built-in name or path to custom `.md` template |
| `data` | yes | — | Path to the data file |
| `data-format` | no | `json` | `json`, `junit-xml`, `sarif`, `lcov` |
| `post-to` | no | `step-summary` | `step-summary`, `pr-comment`, or both (comma-separated) |
| `comment-header` | no | template name | Identifies the PR comment for updates |
| `comment-mode` | no | `replace` | `replace` overwrites; `append` adds below existing content |
| `fail-under` | no | — | Fail the step if coverage/pass-rate is below this % |
| `context` | no | — | JSON string with extra template variables |
| `token` | no | `github.token` | Token for PR comments |
| `python-version` | no | `3.12` | Python version (`3.12+`), or `skip` to use your own |
| `install` | no | `true` | Set `false` if kida is already installed |
| `kida-command` | no | `kida` | Override command (e.g. `uv run kida`) |

## Outputs

| Output | Description |
| --- | --- |
| `report` | Rendered markdown content |
| `comment-id` | PR comment ID (when posting to PR) |

## Examples

### Pytest + coverage with PR comments

```yaml
- name: Run tests
  run: |
    pytest --junitxml=reports/pytest.xml \
      --cov=mypackage --cov-report=json:reports/coverage.json

- name: Test report
  if: always()
  uses: lbliii/kida@v0.3.3
  with:
    template: pytest
    data: reports/pytest.xml
    data-format: junit-xml
    post-to: step-summary,pr-comment

- name: Coverage report
  if: always()
  uses: lbliii/kida@v0.3.3
  with:
    template: coverage
    data: reports/coverage.json
    post-to: step-summary,pr-comment
    fail-under: '80'
```

### Combined PR comment (multiple reports in one comment)

Use the same `comment-header` with `comment-mode: append` to build a single PR comment from multiple report steps:

```yaml
- name: Test report
  uses: lbliii/kida@v0.3.3
  with:
    template: pytest
    data: reports/pytest.xml
    data-format: junit-xml
    post-to: step-summary,pr-comment
    comment-header: CI Report

- name: Coverage report
  uses: lbliii/kida@v0.3.3
  with:
    template: coverage
    data: reports/coverage.json
    post-to: step-summary,pr-comment
    comment-header: CI Report
    comment-mode: append

- name: Lint report
  uses: lbliii/kida@v0.3.3
  with:
    template: ruff
    data: reports/ruff.json
    post-to: step-summary,pr-comment
    comment-header: CI Report
    comment-mode: append
```

This creates one PR comment with all three reports separated by horizontal rules, auto-updated on re-push.

### Diff coverage (changed files only)

Pass changed file paths via `context` to highlight coverage for PR-touched files:

```yaml
- name: Get changed files
  id: changed
  run: |
    FILES=$(gh pr diff ${{ github.event.pull_request.number }} --name-only | grep '\.py$' || true)
    JSON=$(echo "$FILES" | python3 -c "import sys,json; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))")
    echo "files=$JSON" >> "$GITHUB_OUTPUT"
  env:
    GH_TOKEN: ${{ github.token }}

- name: Coverage report
  uses: lbliii/kida@v0.3.3
  with:
    template: coverage
    data: reports/coverage.json
    post-to: step-summary,pr-comment
    context: '{"changed_files": ${{ steps.changed.outputs.files }}}'
```

### Ruff lint violations

```yaml
- name: Run ruff
  run: ruff check src/ --output-format json > reports/ruff.json || true

- name: Lint report
  if: always()
  uses: lbliii/kida@v0.3.3
  with:
    template: ruff
    data: reports/ruff.json
    post-to: step-summary,pr-comment
```

### Custom template

Point `template` at any `.md` file in your repo. Data is unpacked as template variables:

```yaml
- uses: lbliii/kida@v0.3.3
  with:
    template: .github/templates/my-report.md
    data: results.json
```

### Skip Python setup (pre-installed)

```yaml
- uses: lbliii/kida@v0.3.3
  with:
    template: pytest
    data: results.xml
    data-format: junit-xml
    python-version: skip
    install: 'false'
    kida-command: uv run kida
```
