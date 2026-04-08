---
title: Agent Integration
description: End-to-end guide — configure an AI agent to produce AMP output, wire it through GitHub Actions, and render formatted PR comments
draft: false
weight: 35
lang: en
type: doc
tags:
- tutorial
- amp
- agents
- github-action
keywords:
- agent integration
- claude code review
- copilot code review
- amp tutorial
- github action agent
- ai pr comments
icon: cpu
---

# Agent Integration

This tutorial walks through setting up an AI agent to produce structured code reviews that render as formatted PR comments via the [[docs/usage/amp|Agent Message Protocol (AMP)]].

By the end, you'll have:

- Agent instructions that produce AMP JSON
- A GitHub Actions workflow that collects and renders agent output
- Formatted PR comments with severity badges, file links, and diff suggestions

## Prerequisites

- A GitHub repository
- An AI coding agent: Claude Code, GitHub Copilot, or Cursor
- The Kida GitHub Action (`lbliii/kida`)

## Step 1: Add agent instructions

Agent instruction files tell your AI agent how to produce AMP-formatted output. Each agent reads instructions from a different location.

### Claude

Create `.claude/CLAUDE.md` (or add to your existing file):

```markdown
When performing code reviews, wrap findings in a JSON code block tagged `amp:code-review`:

~~~
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
      "severity": "warn",
      "category": "security",
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
~~~
```

A full instruction file is available at `examples/amp/agent-instructions/CLAUDE.md` covering code-review, pr-summary, and security-scan message types.

### GitHub Copilot

Create `.github/copilot-instructions.md` with the same JSON schema. Copilot reads this file automatically. See `examples/amp/agent-instructions/copilot-instructions.md`.

### Cursor

Create `.cursorrules` at your repo root. See `examples/amp/agent-instructions/cursorrules.md`.

### Severity guide

All agents should follow the same severity levels:

| Severity | Meaning | When to use |
| --- | --- | --- |
| `error` | Blocking | Security vulnerabilities, data loss, crashes. Must fix. |
| `warn` | Should fix | Bugs, race conditions, missing validation. |
| `info` | FYI | Naming, style, minor improvements. |
| `suggestion` | Optional | Alternative approaches, nice-to-haves. |

Instruct agents to set `confidence` honestly. Findings below 0.5 are auto-collapsed in the rendered output so reviewers can focus on high-signal items.

## Step 2: Create the GitHub Actions workflow

Create `.github/workflows/amp-review.yml`:

```yaml
name: AMP Review

on:
  pull_request:
    types: [opened, synchronize]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.14'

      - name: Install kida
        run: python -m pip install --quiet kida-templates

      - name: Collect AMP messages
        id: collect
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          set -euo pipefail
          mkdir -p .amp/collected

          # Source 1: .amp/ directory files
          for f in .amp/*.json; do
            [ -f "$f" ] || continue
            cp "$f" ".amp/collected/$(basename "$f")"
          done

          # Source 2: PR body amp: code blocks
          PR_BODY=$(gh pr view "${{ github.event.pull_request.number }}" \
            --json body --jq '.body // ""')
          export PR_BODY

          if [ -n "$PR_BODY" ]; then
            python3 -c "
          import re, json, os
          body = os.environ['PR_BODY']
          for msg_type, content in re.findall(r'\`\`\`amp:(\w[\w-]*)\s*\n(.*?)\`\`\`', body, re.DOTALL):
              try:
                  data = json.loads(content.strip())
                  path = f'.amp/collected/{msg_type}.json'
                  if not os.path.exists(path):
                      json.dump(data, open(path, 'w'), indent=2)
              except json.JSONDecodeError:
                  pass
          "
          fi

          # Count collected messages
          shopt -s nullglob
          FILES=(.amp/collected/*.json)
          echo "count=${#FILES[@]}" >> "$GITHUB_OUTPUT"

      - name: Render AMP messages
        if: steps.collect.outputs.count != '0'
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          set -euo pipefail

          declare -A TEMPLATE_MAP=(
            ["code-review"]="code-review"
            ["pr-summary"]="pr-summary"
            ["security-scan"]="security-scan"
            ["dependency-review"]="dependency-review"
            ["deploy-preview"]="deploy-preview"
          )

          PR_NUMBER="${{ github.event.pull_request.number }}"
          REPO="${{ github.repository }}"
          SHA="${{ github.event.pull_request.head.sha }}"

          for f in .amp/collected/*.json; do
            [ -f "$f" ] || continue

            BASENAME=$(basename "$f" .json)
            MSG_TYPE="${BASENAME%-comment}"
            TEMPLATE="${TEMPLATE_MAP[$MSG_TYPE]:-}"
            [ -z "$TEMPLATE" ] && continue

            # Inject repo context
            python3 -c "
          import json
          with open('$f') as fh: data = json.load(fh)
          data.setdefault('repository', '$REPO')
          data.setdefault('sha', '$SHA')
          data.setdefault('pr_number', $PR_NUMBER)
          json.dump(data, open('$f', 'w'), indent=2)
          "

            # Render
            OUTPUT=$(kida render "templates/${TEMPLATE}-report.md" \
              --data "$f" --mode markdown)
            [ -z "$OUTPUT" ] && continue

            # Post with deduplication
            MARKER="<!-- amp:${MSG_TYPE} -->"
            BODY=$(printf '%s\n%s' "$MARKER" "$OUTPUT")

            EXISTING_ID=$(gh api \
              "repos/${REPO}/issues/${PR_NUMBER}/comments" \
              --paginate --jq ".[] | select(.body | startswith(\"$MARKER\")) | .id" \
              2>/dev/null | head -1)

            if [ -n "$EXISTING_ID" ]; then
              gh api "repos/${REPO}/issues/comments/${EXISTING_ID}" \
                -X PATCH -f body="$BODY" --silent
            else
              gh api "repos/${REPO}/issues/${PR_NUMBER}/comments" \
                -f body="$BODY" --silent
            fi
          done
```

### How collection works

The workflow collects AMP messages from two sources, in priority order:

1. **`.amp/` directory** — Agents or CI steps write JSON files here (e.g., `.amp/code-review.json`). Highest priority.
2. **PR body** — Agents like Claude Code can embed `` ```amp:type `` code blocks directly in the PR description.

File-based sources take precedence — if `.amp/code-review.json` exists, a code-review block in the PR body is ignored.

> [!NOTE]
> The full workflow in `.github/workflows/amp-review.yml` also collects from PR comments. The simplified workflow above omits that step for clarity.

### How rendering works

For each collected message:

1. The message type is derived from the filename (e.g., `code-review.json` maps to `code-review`)
2. Repository and SHA context are injected for file permalink generation
3. The matching Kida template renders the JSON to markdown
4. The output is posted as a PR comment with an HTML marker (`<!-- amp:code-review -->`) for deduplication
5. On subsequent pushes, existing comments are updated in place

## Step 3: Test locally

Before pushing, verify rendering locally with the example data:

```bash
# Install kida
pip install kida-templates

# Render a code review
kida render templates/code-review-report.md \
  --data examples/amp/code-review.json \
  --mode markdown

# Render a PR summary
kida render templates/pr-summary-report.md \
  --data examples/amp/pr-summary.json \
  --mode markdown

# Render to terminal (with ANSI colors)
kida render templates/code-review-report.md \
  --data examples/amp/code-review.json \
  --mode terminal
```

## Step 4: Trigger a review

1. Push a branch and open a PR
2. If your agent is configured (e.g., Claude Code in a CI step, or Copilot's auto-review), it produces AMP JSON
3. The `amp-review.yml` workflow collects the JSON and renders it
4. A formatted PR comment appears with severity badges, file permalinks, and diff suggestions
5. On subsequent pushes, the comment updates in place

## Composing multiple agents

When Claude and Copilot both review the same PR, you get separate AMP messages that render as separate PR comments (one per message type, deduplicated by the `<!-- amp:type -->` marker).

The current `kida render` CLI does not expose a `--compose` flag, so composition is handled as an upstream data-preparation step, not at render time.

- **One comment per message type** (default) — The workflow above already deduplicates by type using `<!-- amp:type -->` markers, so each agent's output gets its own auto-updating comment.
- **Threaded or aggregated views** — Merge multiple agent outputs into a single AMP JSON payload in a CI step before passing it to `kida render`. For example, combine Claude and Semgrep security findings into one `security-scan.json`, then render once.

See [[docs/usage/amp#composition|AMP Composition]] for the four composition models defined by the protocol.

## Adding new message types

To support a new AMP message type:

1. **Define the schema** — Create `schemas/amp/v1/my-type.schema.json`
2. **Write a template** — Create `templates/my-type-report.md` using Kida syntax
3. **Update the workflow** — Add the type to the `TEMPLATE_MAP` in `amp-review.yml`
4. **Add agent instructions** — Tell agents how to produce the new JSON format

See [[docs/usage/agent-templates#customizing-templates|Customizing Templates]] for template authoring patterns.

## Next steps

- [[docs/usage/amp|Agent Message Protocol]] — protocol spec, surfaces, and composition
- [[docs/usage/agent-templates|Agent Templates]] — schema details and customization for all built-in templates
- [[docs/usage/github-action|GitHub Action]] — CI report rendering beyond agent messages
