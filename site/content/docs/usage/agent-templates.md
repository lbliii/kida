---
title: Agent Templates
description: Built-in Kida templates for rendering AI agent output — code review, PR summary, deploy preview, dependency review, security scan, and release notes
draft: false
weight: 34
lang: en
type: doc
tags:
- usage
- amp
- templates
- agents
keywords:
- agent templates
- code review template
- pr summary template
- deploy preview
- dependency review
- security scan
- release notes
- amp templates
icon: layout
---

# Agent Templates

Kida ships six built-in templates for rendering [[docs/usage/amp|AMP]] messages as formatted GitHub comments, step summaries, and terminal output. Each template consumes structured JSON from an AI agent and produces surface-appropriate output with severity badges, collapsible sections, diff suggestions, and more.

## Template catalog

| Template | AMP type | Schema | Surfaces |
| --- | --- | --- | --- |
| `code-review-report.md` | `code-review` | `code-review.schema.json` | PR comment, step summary, terminal |
| `pr-summary-report.md` | `pr-summary` | `pr-summary.schema.json` | PR comment, step summary |
| `deploy-preview-report.md` | `deploy-preview` | `deploy-preview.schema.json` | PR comment, step summary |
| `dependency-review-report.md` | `dependency-review` | `dependency-review.schema.json` | PR comment, step summary |
| `security-scan-report.md` | `security-scan` | `security-scan.schema.json` | PR comment, step summary |
| `release-notes-report.md` | `release-notes` | `release-notes.schema.json` | Release, PR comment, step summary, terminal |

All schemas are in `schemas/amp/v1/`. All templates are in `templates/`.

## Code review

The code-review template renders AI review findings as a structured PR comment with severity grouping, clickable file permalinks, and diff suggestions.

### Schema

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `findings` | array | yes | List of findings (see below) |
| `agent` | string | no | Agent name |
| `model` | string | no | Model identifier |
| `confidence` | number | no | Overall confidence (0.0–1.0) |
| `summary` | string | no | One-line review summary |
| `repository` | string | no | `owner/repo` for file permalinks |
| `sha` | string | no | Head commit SHA for permalinks |
| `min_confidence` | number | no | Threshold below which findings are collapsed (default: 0.5) |
| `stats` | object | no | Review statistics (`files_reviewed`, `findings_count`, `by_severity`) |

**Finding fields:**

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `message` | string | yes | Detailed explanation |
| `file` | string | no | Relative file path |
| `line` | integer | no | Line number |
| `severity` | string | no | `error`, `warn`, `info`, or `suggestion` (default: `info`) |
| `category` | string | no | e.g., `security`, `bug`, `performance`, `style` |
| `title` | string | no | Short title for summary views |
| `suggestion` | string | no | How to fix (natural language) |
| `diff` | string | no | Unified diff with `-`/`+` prefixed lines |
| `confidence` | number | no | Per-finding confidence (0.0–1.0) |

### Example input

```json
{
  "agent": "Claude",
  "confidence": 0.87,
  "summary": "Found 2 issues: 1 security warning, 1 bug.",
  "repository": "myorg/myrepo",
  "sha": "abc1234",
  "min_confidence": 0.5,
  "findings": [
    {
      "file": "src/db.py",
      "line": 42,
      "severity": "warn",
      "category": "security",
      "title": "SQL injection risk",
      "message": "Query built with f-string interpolation.",
      "diff": "- query = f\"SELECT * FROM users WHERE id = {user_id}\"\n+ query = \"SELECT * FROM users WHERE id = %s\"",
      "confidence": 0.94
    },
    {
      "file": "src/core.py",
      "line": 156,
      "severity": "warn",
      "category": "bug",
      "title": "Unhandled None return",
      "message": "get_template() can return None but caller assumes Template.",
      "confidence": 0.82
    }
  ],
  "stats": {
    "files_reviewed": 8,
    "findings_count": 2,
    "by_severity": { "error": 0, "warn": 2, "info": 0, "suggestion": 0 }
  }
}
```

### Rendered output

The template produces:

- A header with the agent name and overall confidence badge
- A summary line
- Findings grouped by severity (`error` first, then `warn`, `info`, `suggestion`)
- Each finding shows a severity badge, file permalink (`owner/repo/blob/sha/file#L42`), and the message
- Findings with a `diff` field render as a fenced code block with `diff` syntax highlighting
- Findings below `min_confidence` are collapsed inside a `<details>` block
- A stats footer with files reviewed and severity breakdown

## PR summary

Renders an auto-generated PR description with what changed, why, risk areas, and review suggestions.

### Schema

| Field | Type | Description |
| --- | --- | --- |
| `title` | string | Suggested PR title |
| `what_changed` | string | Description of changes (markdown supported) |
| `why` | string | Motivation for the change |
| `change_size` | string | T-shirt size: `trivial`, `small`, `medium`, `large`, `x-large` |
| `files` | array | Per-file summaries (`path`, `change_type`, `summary`) |
| `risk_areas` | array | Areas needing extra review (`area`, `reason`) |
| `breaking_changes` | array | List of breaking changes (strings) |
| `test_coverage` | string | Test coverage summary |
| `suggested_labels` | array | Suggested GitHub labels |
| `suggested_reviewers` | array | Suggested reviewer usernames |
| `diff_stats` | object | `files_changed`, `insertions`, `deletions` |

### Example input

```json
{
  "agent": "Claude",
  "title": "Add rate limiting to API endpoints",
  "what_changed": "Added token-bucket rate limiting to all `/api/v2/` endpoints.",
  "why": "Production is seeing 10x traffic spikes from a single client.",
  "change_size": "medium",
  "files": [
    { "path": "src/middleware/rate_limit.py", "change_type": "added", "summary": "New rate limiter middleware" },
    { "path": "src/api/router.py", "change_type": "modified", "summary": "Wired rate limiter into router" }
  ],
  "risk_areas": [
    { "area": "Redis connection pool", "reason": "Rate limiter uses Redis; pool exhaustion could block requests" }
  ],
  "breaking_changes": [],
  "test_coverage": "Unit tests for token bucket logic. Integration test for rate-limited endpoint.",
  "suggested_labels": ["enhancement", "api"],
  "suggested_reviewers": ["alice"]
}
```

### Rendered output

- Breaking changes alert (if any) with a `> [!CAUTION]` block
- What/why sections
- File change table with change type badges
- Risk areas with explanations
- Test coverage summary
- Suggested labels and reviewers
- Diff stats footer

## Deploy preview

Renders deploy status with a preview URL, bundle size deltas, and Lighthouse performance scores.

### Schema

| Field | Type | Description |
| --- | --- | --- |
| `url` | string | URL to the deployed preview |
| `status` | string | `success`, `fail`, `building`, or `cancelled` |
| `environment` | string | Environment name (default: `"Preview"`) |
| `provider` | string | Deploy provider (e.g., `"Vercel"`, `"Netlify"`) |
| `build_time_seconds` | number | Build duration |
| `bundle_stats` | object | `total_size`, `size_delta`, `entries[]` (name, size, delta) |
| `lighthouse` | object | Scores: `performance`, `accessibility`, `best_practices`, `seo` (0–100) |
| `pages` | array | Per-page details (`path`, `url`, `status`, `size`) |

### Rendered output

- Status badge (pass/fail/building)
- Clickable preview URL
- Bundle size table with per-entry deltas
- Lighthouse score badges (color-coded: green >= 90, yellow >= 50, red < 50)
- Per-page status table

## Dependency review

Renders dependency change analysis with vulnerability detection and license compliance.

### Schema

| Field | Type | Description |
| --- | --- | --- |
| `risk` | string | Overall risk: `low`, `medium`, `high`, `critical` |
| `added` | array | New deps (`name`, `version`, `license`, `size`, `transitive_count`) |
| `updated` | array | Updated deps (`name`, `from`, `to`, `change_type`, `changelog_url`) |
| `removed` | array | Removed deps (`name`, `version`, `reason`) |
| `vulnerabilities` | array | Known vulns (`package`, `severity`, `cve`, `title`, `fix_version`, `url`) |
| `license_issues` | array | License concerns (`package`, `license`, `reason`) |

### Rendered output

- Overall risk badge
- Added/updated/removed dependency tables
- Vulnerability alerts with severity badges, CVE links, and fix versions
- License compliance warnings

## Security scan

Renders security findings grouped by severity with CWE/CVE references and remediation steps.

### Schema

| Field | Type | Description |
| --- | --- | --- |
| `findings` | array | **Required.** Security findings (see below) |
| `tool` | string | Scanner name (e.g., `"Semgrep"`, `"CodeQL"`, `"Claude"`) |
| `status` | string | Overall status: `pass`, `fail`, `warn` |
| `summary` | string | Scan summary |
| `policy_status` | string | Whether scan meets security policy |
| `stats` | object | `total`, `by_severity` (critical/high/medium/low/info) |

**Finding fields:**

| Field | Type | Description |
| --- | --- | --- |
| `severity` | string | **Required.** `critical`, `high`, `medium`, `low`, `info` |
| `title` | string | Short title |
| `message` | string | Detailed description |
| `file` | string | File path |
| `line` | integer | Line number |
| `category` | string | e.g., `injection`, `auth`, `crypto`, `xss`, `exposure` |
| `cwe` | string | CWE number (e.g., `"89"` for CWE-89) |
| `cve` | string | CVE identifier |
| `remediation` | string | How to fix |
| `diff` | string | Suggested fix as unified diff |

### Rendered output

- Overall status badge and policy compliance
- Findings grouped by severity (critical first)
- Each finding shows severity badge, CWE/CVE links, file permalink
- Remediation steps and diff suggestions
- Stats footer with severity breakdown

## Release notes

Renders categorized release notes with contributor highlights, breaking changes, and dependency digests. This type has four template variants for different surfaces.

### Schema

| Field | Type | Description |
| --- | --- | --- |
| `version` | string | Release version (e.g., `"1.2.0"`) |
| `previous_version` | string | Previous version for comparison |
| `release_date` | string | Release date (YYYY-MM-DD) |
| `repository` | string | `owner/repo` |
| `compare_url` | string | URL to full diff between versions |
| `pull_requests` | array | PRs in this release (`number`, `title`, `author`, `labels`, `release_note`) |
| `contributors` | array | All contributor usernames |
| `new_contributors` | array | First-time contributors |
| `direct_commits` | array | Commits not via PR (`sha`, `message`, `author`) |
| `diff_stats` | object | `files_changed`, `insertions`, `deletions`, `new_files` |
| `benchmarks` | object | Benchmark deltas (`name`, `change`, `previous`, `current`) |

### Template variants

| Template | Surface | Description |
| --- | --- | --- |
| `release-notes-report.md` | GitHub Release, step summary | Full release notes with all sections |
| `release-notes-compact-report.md` | PR comment | Condensed version for PR comments |
| `release-notes-detailed-report.md` | Step summary | Extended version with PR body excerpts |
| `release-notes-terminal-report.md` | Terminal | ANSI-colored output for CLI |

### Rendered output

- Version header with release date and compare link
- PRs grouped by label category (features, fixes, docs, etc.)
- Breaking changes callout
- Contributor list with first-time contributor highlights
- Dependency update digest (for dependabot/renovate PRs)
- Diff stats and benchmark deltas

## Customizing templates

### Override a built-in template

Copy the built-in template and modify it:

```bash
cp templates/code-review-report.md .github/templates/my-code-review.md
```

Then point your workflow at the custom template:

```yaml
kida render .github/templates/my-code-review.md --data review.json --mode markdown
```

Or in the GitHub Action:

```yaml
- uses: lbliii/kida@v0.3.3
  with:
    template: .github/templates/my-code-review.md
    data: .amp/collected/code-review.json
```

### Template patterns

Built-in agent templates follow consistent patterns you can reuse:

**Variable defaults at the top:**

```kida
{% set min_confidence = min_confidence | default(0.5) %}
{% set repository = repository | default("") %}
{% set sha = sha | default("") %}
```

**Severity badges:**

```kida
{{ finding.severity | badge }}
```

**Conditional file permalinks:**

```kida
{% if repository and sha %}
[`{{ finding.file }}#L{{ finding.line }}`](https://github.com/{{ repository }}/blob/{{ sha }}/{{ finding.file }}#L{{ finding.line }})
{% else %}
`{{ finding.file }}:{{ finding.line }}`
{% endif %}
```

**Collapsible low-confidence findings:**

```kida
{% if finding.confidence < min_confidence %}
<details>
<summary>{{ finding.title }} (low confidence: {{ (finding.confidence * 100) | round | int }}%)</summary>

{{ finding.message }}

</details>
{% endif %}
```

### Available filters

Agent templates use these Kida filters:

| Filter | Usage | Description |
| --- | --- | --- |
| `badge` | `{{ severity \| badge }}` | Renders a severity/status badge |
| `default` | `{{ val \| default("fallback") }}` | Default value for missing fields |
| `round` | `{{ confidence \| round }}` | Round a number |
| `int` | `{{ score \| int }}` | Convert to integer |
| `length` | `{{ findings \| length }}` | Collection length |

## Next steps

- [[docs/usage/amp|Agent Message Protocol]] — the protocol spec, surfaces, and composition modes
- [[docs/tutorials/agent-integration|Agent Integration Tutorial]] — end-to-end setup from agent config to PR comments
- [[docs/usage/github-action|GitHub Action]] — CI report rendering with the Kida action
