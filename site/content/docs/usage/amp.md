---
title: Agent Message Protocol (AMP)
description: Decouple AI agent output from presentation with AMP — a protocol for structured, multi-surface rendering
draft: false
weight: 32
lang: en
type: doc
tags:
- usage
- amp
- agents
- protocol
keywords:
- agent message protocol
- amp
- ai agent output
- structured agent messages
- multi-surface rendering
- claude
- copilot
- cursor
icon: radio
---

# Agent Message Protocol (AMP)

AMP is a protocol for how AI agents express structured output for multi-surface rendering. It decouples message production (agents like Claude, Copilot, or Cursor) from message presentation (Kida templates), so teams control how agent output looks without changing agent behavior.

## The problem AMP solves

Without AMP, AI agents dump raw markdown into PR comments. Each surface renders it differently, composition of multiple agent outputs is ad-hoc, and teams have no control over formatting or severity thresholds.

With AMP, agents emit structured JSON. Kida templates render that JSON to the right format for each surface — GitHub PR comments, step summaries, releases, Slack, or terminal. Composition is declarative.

**Without AMP:**

```
Agent → raw markdown → paste into PR comment
Agent → different markdown → paste into Slack
Agent → yet another format → paste into terminal
```

**With AMP:**

```
Agent → structured JSON → Kida template → GitHub PR comment (markdown)
                        → Kida template → Slack message (mrkdwn)
                        → Kida template → Terminal output (ANSI)
```

## How it works

AMP has three layers:

1. **Produce** — An agent outputs JSON conforming to an AMP schema (e.g., `code-review`, `pr-summary`).
2. **Validate** — The JSON conforms to a published JSON Schema at `schemas/amp/v1/`.
3. **Render** — A Kida template consumes the JSON and renders it for a specific surface.

Agents don't need to know about rendering. Templates don't need to know about agents. The schema is the contract.

## Quick example

A Claude code review produces this JSON:

```json
{
  "agent": "Claude",
  "model": "claude-sonnet-4-20250514",
  "confidence": 0.87,
  "summary": "Found 2 issues: 1 security warning, 1 bug.",
  "findings": [
    {
      "file": "src/app/db.py",
      "line": 42,
      "severity": "warn",
      "category": "security",
      "title": "SQL injection risk",
      "message": "Query built with f-string interpolation.",
      "suggestion": "Use parameterized queries.",
      "diff": "- query = f\"SELECT * FROM users WHERE id = {user_id}\"\n+ query = \"SELECT * FROM users WHERE id = %s\"\n+ cursor.execute(query, (user_id,))",
      "confidence": 0.94
    }
  ],
  "stats": {
    "files_reviewed": 8,
    "findings_count": 2,
    "by_severity": { "error": 0, "warn": 2, "info": 0, "suggestion": 0 }
  }
}
```

Render it locally:

```bash
kida render templates/code-review-report.md --data review.json --mode markdown
```

The template produces a formatted PR comment with severity badges, clickable file links, diff suggestions, and collapsible low-confidence findings. See [[docs/usage/agent-templates|Agent Templates]] for all built-in templates.

## Message types

AMP v1 defines six message types. Each has a JSON Schema and one or more reference templates.

| Type | Description | Surfaces |
| --- | --- | --- |
| `code-review` | File-level findings with severity, confidence, and suggested fixes | PR comment, step summary, terminal |
| `pr-summary` | Auto-generated PR description with what/why/risk analysis | PR comment, step summary |
| `deploy-preview` | Deploy status with URL, bundle size, and performance scores | PR comment, step summary |
| `dependency-review` | Dependency changes with vulnerability and license analysis | PR comment, step summary |
| `security-scan` | Security findings grouped by severity with CWE/CVE references | PR comment, step summary |
| `release-notes` | Categorized PRs, breaking changes, and contributor highlights | Release, PR comment, step summary, terminal |

Schemas are published at `schemas/amp/v1/<type>.schema.json`.

## Surfaces

A surface is a rendering target with specific format constraints and capabilities.

| Surface | Format | Max length | Key capabilities |
| --- | --- | --- | --- |
| GitHub PR Comment | markdown | 65 KB | Checkboxes, collapsible sections, alerts, tables, images |
| GitHub Step Summary | markdown | 1 MB | Same as PR comment, with more room |
| GitHub Release | markdown | 125 KB | Tables, collapsible sections, code blocks (no checkboxes, no alerts) |
| Slack | mrkdwn | 40 KB | Links, code blocks, emoji (no tables, no images, no collapsible) |
| Terminal / CLI | ansi | unlimited | ANSI colors, tables, code blocks (no links, no images) |

Templates can adapt output based on surface capabilities. For example, a code-review template uses `<details>` blocks on GitHub but flat headings on terminal.

## Composition

When multiple agents review the same PR, AMP defines four composition modes for combining their output:

| Mode | Behavior | Deduplication | Ordering |
| --- | --- | --- | --- |
| `replace` | Latest message overwrites existing | By header/type | Append |
| `append` | New message added below existing, separated by `---` | By header | Append |
| `thread` | Each agent gets a collapsible section in a shared comment | By agent | By agent |
| `aggregate` | Findings merged, deduplicated by file+line, sorted by severity | By type | By severity |

Set the mode via the `comment-mode` input in the [[docs/usage/github-action|GitHub Action]], or in your workflow's render step.

## Agent metadata

Every AMP message may include metadata to identify its source:

| Field | Type | Description |
| --- | --- | --- |
| `agent` | string | Agent name (e.g., `"Claude"`, `"Copilot"`, `"custom-linter"`) |
| `model` | string | Model identifier (e.g., `"claude-sonnet-4-20250514"`) |
| `confidence` | number | Overall confidence score, 0.0 to 1.0 |
| `timestamp` | string | ISO 8601 timestamp of message production |
| `run_id` | string | Unique identifier for deduplication and tracing |

Templates use `confidence` to filter or collapse low-confidence findings. The `run_id` enables deduplication when the same agent runs multiple times on a PR.

## Next steps

- [[docs/usage/agent-templates|Agent Templates]] — the built-in templates for each message type, with schema details and customization
- [[docs/tutorials/agent-integration|Agent Integration Tutorial]] — end-to-end setup from agent config to rendered PR comments
- [[docs/usage/github-action|GitHub Action]] — CI report rendering and the `comment-mode` input
