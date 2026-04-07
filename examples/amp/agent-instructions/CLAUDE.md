# Agent Message Protocol (AMP) — Claude Instructions

When performing code reviews or PR analysis in this repository, output structured JSON conforming to the AMP schemas. This enables the CI pipeline to render your output as formatted PR comments with severity badges, checkboxes, and diff suggestions via Kida templates.

## Code Review

When reviewing code, wrap your findings in a JSON code block tagged `amp:code-review`:

```amp:code-review
{
  "agent": "Claude",
  "model": "<your model>",
  "confidence": 0.85,
  "summary": "One-line review summary.",
  "findings": [
    {
      "file": "path/to/file.py",
      "line": 42,
      "severity": "warn | error | info | suggestion",
      "category": "security | bug | performance | style | complexity | testing",
      "title": "Short finding title",
      "message": "Detailed explanation.",
      "suggestion": "How to fix.",
      "diff": "- old\n+ new",
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

### Severity guide

- **error**: Blocking — security vulnerabilities, data loss, crashes. Must fix.
- **warn**: Should fix — bugs, race conditions, missing validation.
- **info**: FYI — naming, style, minor improvements.
- **suggestion**: Optional — alternative approaches, nice-to-haves.

### Rules

- Always include `file` and `line` so findings render as clickable permalinks.
- Set `confidence` honestly. Findings below 0.5 are auto-collapsed for the reviewer.
- Include `diff` when you can suggest a concrete code change.
- Don't duplicate what linters catch — focus on logic, architecture, and security.

## PR Summary

When summarizing a PR, output a JSON block tagged `amp:pr-summary`:

```amp:pr-summary
{
  "agent": "Claude",
  "title": "Suggested PR title",
  "what_changed": "What this PR does (markdown supported).",
  "why": "Why this change is being made.",
  "files": [
    {"path": "src/foo.py", "change_type": "modified", "summary": "Per-file summary"}
  ],
  "risk_areas": [
    {"area": "Area name", "reason": "Why it's risky"}
  ],
  "breaking_changes": ["List any breaking changes"],
  "test_coverage": "What's tested and what isn't.",
  "suggested_labels": ["enhancement", "security"],
  "suggested_reviewers": ["username"]
}
```

## Security Scan

When performing security analysis, output `amp:security-scan`:

```amp:security-scan
{
  "tool": "Claude",
  "status": "pass | warn | fail",
  "summary": "Scan summary.",
  "findings": [
    {
      "severity": "critical | high | medium | low | info",
      "rule": "Finding identifier",
      "title": "Short title",
      "message": "What's wrong.",
      "file": "path/to/file.py",
      "line": 42,
      "category": "injection | auth | crypto | xss | exposure",
      "cwe": "89",
      "remediation": "How to fix.",
      "diff": "- vulnerable\n+ fixed"
    }
  ]
}
```

## Composition

Multiple agents may review the same PR. Use `comment-mode: append` in the CI workflow to combine all agent outputs into a single PR comment with sections per agent. Keep your output focused on what only you can find — don't repeat what other tools report.
