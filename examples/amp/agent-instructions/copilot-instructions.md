# Copilot Instructions

## Code Review Output

When reviewing pull requests, output your findings as structured JSON conforming to the Agent Message Protocol (AMP) code-review schema. This allows the CI pipeline to render your review as a formatted PR comment with severity badges, actionable checkboxes, and diff suggestions.

### Output format

Return a single JSON code block with this structure:

```json
{
  "agent": "Copilot",
  "model": "<your model identifier>",
  "confidence": 0.85,
  "summary": "<one-line summary of the review>",
  "findings": [
    {
      "file": "src/example.py",
      "line": 42,
      "severity": "warn",
      "category": "security",
      "title": "Short title",
      "message": "Detailed explanation of the issue.",
      "suggestion": "How to fix it.",
      "diff": "- old line\n+ new line",
      "confidence": 0.9
    }
  ],
  "stats": {
    "files_reviewed": 5,
    "findings_count": 3,
    "by_severity": {"error": 0, "warn": 2, "info": 1, "suggestion": 0}
  }
}
```

### Severity levels

- `error` — Blocking. Must fix before merge (security vulnerabilities, data loss, crashes).
- `warn` — Should fix. Bugs, performance issues, or code that will cause problems.
- `info` — Informational. Style, naming, or minor improvements.
- `suggestion` — Optional. Alternative approaches or nice-to-haves.

### Categories

Use these categories to classify findings: `security`, `bug`, `performance`, `style`, `complexity`, `testing`, `documentation`, `accessibility`.

### Confidence scores

Include a confidence score (0.0–1.0) for each finding. Findings below 0.5 confidence will be collapsed in the rendered output. If you are unsure about a finding, set confidence lower rather than omitting it.

### Diff suggestions

When suggesting a code change, include a `diff` field with unified diff format (lines prefixed with `-` for removal and `+` for addition). This renders as a syntax-highlighted code block in the PR comment.

### Custom release notes

When reviewing PRs that introduce user-facing changes, add a `<!-- release-note: description -->` HTML comment to the PR body suggesting what should appear in release notes.

## PR Summary Output

When asked to summarize a pull request, output JSON conforming to the AMP pr-summary schema:

```json
{
  "agent": "Copilot",
  "title": "Suggested PR title",
  "what_changed": "Description of changes (supports markdown).",
  "why": "Motivation for the change.",
  "files": [
    {"path": "src/foo.py", "change_type": "modified", "summary": "What changed in this file"}
  ],
  "risk_areas": [
    {"area": "auth middleware", "reason": "Session handling changed, verify token refresh"}
  ],
  "breaking_changes": [],
  "test_coverage": "Summary of test coverage for the changes.",
  "suggested_labels": ["enhancement"],
  "suggested_reviewers": ["username"]
}
```

## General Guidelines

- Focus on issues that matter. Don't flag trivial style issues that a linter would catch.
- Anchor findings to specific files and lines so they render as clickable permalinks.
- Group related findings under a single entry rather than creating duplicates.
- When multiple agents review the same PR, findings are composed into a single comment. Avoid duplicating what linters or other tools already report.
