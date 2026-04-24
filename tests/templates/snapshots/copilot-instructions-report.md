# Copilot Instructions

## Project

kida is a Python project using pytest, asyncio.

## Build & Test

- **Build:** `uv build`
- **Test:** `uv run pytest`
- **Lint:** `uv run ruff check`


## Code Review Output

When reviewing pull requests, output findings as structured JSON conforming to the Agent Message Protocol (AMP) code-review schema. The CI pipeline renders this as a formatted PR comment with severity badges, actionable checkboxes, and diff suggestions.

### Output format

Return a single JSON code block:

```json
{
  "agent": "Copilot",
  "model": "<your model identifier>",
  "confidence": 0.85,
  "summary": "<one-line summary>",
  "findings": [
    {
      "file": "path/to/file",
      "line": 42,
      "severity": "warn",
      "category": "security",
      "title": "Short title",
      "message": "Detailed explanation.",
      "suggestion": "How to fix.",
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

- `error` — Blocking. Must fix before merge (security vulnerabilities, data loss).
- `warn` — Should fix (logic bugs, missing validation).
- `info` — Informational (code style, naming).
- `suggestion` — Optional improvement (optional improvements).

### Categories

Classify findings using: security, bug, performance, style.

### Rules

- Always include `file` and `line` for clickable permalinks.
- Set `confidence` honestly (0.0–1.0). Below 0.5 is auto-collapsed.
- Include `diff` for concrete code change suggestions.
- Don't flag issues a linter would catch (`uv run ruff check` runs in CI).
- Prefer immutable data structures
- Always type-annotate public APIs
## PR Summary Output

When asked to summarize a pull request, output JSON conforming to the AMP pr-summary schema:

```json
{
  "agent": "Copilot",
  "title": "Suggested PR title",
  "what_changed": "Description (markdown supported).",
  "why": "Motivation for the change.",
  "files": [
    {"path": "src/foo.py", "change_type": "modified", "summary": "What changed"}
  ],
  "risk_areas": [
    {"area": "area name", "reason": "why it's risky"}
  ],
  "breaking_changes": [],
  "test_coverage": "What's tested.",
  "suggested_labels": ["enhancement"],
  "suggested_reviewers": ["username"]
}
```

## General

- Focus on issues that matter — logic, architecture, security.
- Anchor findings to specific files and lines.
- Group related findings rather than creating duplicates.
- When suggesting test changes, verify they work with `uv run pytest`.
