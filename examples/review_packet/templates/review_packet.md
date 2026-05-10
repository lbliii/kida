# Kida Review Packet: #{{ pull_request.number }} {{ pull_request.title }}

**Status:** {{ status }}<br>
**Branch:** `{{ pull_request.branch }}` -> `{{ pull_request.base }}`

{{ summary }}

## Checks

| Check | Status | Detail | Next action |
| --- | --- | --- | --- |
{% for check in checks -%}
| `{{ check.name }}` | {{ check.status }} | {{ check.detail }} | {{ check.next_action }} |
{% endfor %}

## Coverage

Overall coverage: **{{ coverage.percent }}%**

| Changed file | Coverage |
| --- | --- |
{% for file in coverage.changed_files -%}
| `{{ file.path }}` | {{ file.display }} |
{% endfor %}

## Changed Files

{% for file in changed_files -%}
- **{{ file.risk }}** `{{ file.path }}` ({{ file.kind }}): {{ file.summary }}
{% endfor %}

## Kida Diagnostics

{% if diagnostics -%}
{% for diag in diagnostics -%}
- **{{ diag.severity }}** `{{ diag.code }}` in `{{ diag.template }}:{{ diag.line }}`: {{ diag.message }}
  Next action: {{ diag.next_action }}
{% endfor %}
{% else -%}
No Kida diagnostics.
{% end %}

## Steward Findings

{% for finding in steward_findings -%}
- **{{ finding.severity }}** {{ finding.steward }} / {{ finding.area }}: {{ finding.finding }}
{% endfor %}

## Release Preview

{{ release_preview.headline }}

{% for note in release_preview.notes -%}
- {{ note }}
{% endfor %}
