{% set project = project_name | default("this project", true) -%}
{% set lang = language | default("", true) -%}
{% set frameworks = frameworks | default([], true) -%}
{% set test_cmd = test_command | default("", true) -%}
{% set lint_cmd = lint_command | default("", true) -%}
{% set build_cmd = build_command | default("", true) -%}
{% set extra_rules = review_rules | default([], true) -%}
{% set schemas_enabled = amp_schemas | default(["code-review", "pr-summary"], true) -%}
{% set severity_rules = severity_guide | default({}, true) -%}
{% set categories = review_categories | default(["security", "bug", "performance", "style", "complexity", "testing"], true) -%}
# Copilot Instructions

{% if lang or frameworks -%}
## Project

{{ project }}{% if lang %} is a {{ lang }} project{% endif %}{% if frameworks %} using {{ frameworks | join(", ") }}{% endif %}.

{% endif -%}
{% if build_cmd or test_cmd or lint_cmd -%}
## Build & Test

{% if build_cmd -%}
- **Build:** `{{ build_cmd }}`
{% endif -%}
{% if test_cmd -%}
- **Test:** `{{ test_cmd }}`
{% endif -%}
{% if lint_cmd -%}
- **Lint:** `{{ lint_cmd }}`
{% endif %}

{% endif -%}
{% if "code-review" in schemas_enabled -%}
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

- `error` — Blocking. Must fix before merge{% if severity_rules.error %} ({{ severity_rules.error }}){% endif %}.
- `warn` — Should fix{% if severity_rules.warn %} ({{ severity_rules.warn }}){% endif %}.
- `info` — Informational{% if severity_rules.info %} ({{ severity_rules.info }}){% endif %}.
- `suggestion` — Optional improvement{% if severity_rules.suggestion %} ({{ severity_rules.suggestion }}){% endif %}.

### Categories

Classify findings using: {{ categories | join(", ") }}.

### Rules

- Always include `file` and `line` for clickable permalinks.
- Set `confidence` honestly (0.0–1.0). Below 0.5 is auto-collapsed.
- Include `diff` for concrete code change suggestions.
- Don't flag issues a linter would catch{% if lint_cmd %} (`{{ lint_cmd }}` runs in CI){% endif %}.
{% for rule in extra_rules -%}
- {{ rule }}
{% endfor -%}

{% endif -%}
{% if "pr-summary" in schemas_enabled -%}
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

{% endif -%}
## General

- Focus on issues that matter — logic, architecture, security.
- Anchor findings to specific files and lines.
- Group related findings rather than creating duplicates.
{% if test_cmd -%}
- When suggesting test changes, verify they work with `{{ test_cmd }}`.
{% endif -%}
