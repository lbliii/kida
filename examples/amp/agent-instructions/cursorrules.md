# Cursor Rules — AMP Output

When performing code reviews in this repository, structure your findings as JSON conforming to the Agent Message Protocol (AMP). The CI pipeline renders AMP JSON into formatted PR comments.

## Code Review Format

Output findings as a JSON code block:

```json
{
  "agent": "Cursor",
  "confidence": 0.85,
  "summary": "Review summary.",
  "findings": [
    {
      "file": "path/to/file.py",
      "line": 42,
      "severity": "error | warn | info | suggestion",
      "category": "security | bug | performance | style",
      "message": "What's wrong and why.",
      "suggestion": "How to fix.",
      "diff": "- old\n+ new",
      "confidence": 0.9
    }
  ]
}
```

## Severity

- `error` — Must fix before merge (security, crashes, data loss)
- `warn` — Should fix (bugs, performance, missing validation)
- `info` — Consider fixing (style, naming, minor issues)
- `suggestion` — Optional improvement

## Rules

- Include `file` and `line` for every finding.
- Set `confidence` below 0.5 for uncertain findings (they get auto-collapsed).
- Include `diff` for concrete fix suggestions.
- Focus on logic and architecture, not linter-level style issues.
