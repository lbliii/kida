{% set agent_name = agent | default("AI", true) -%}
{% set agent_model = model | default("", true) -%}
{% set review_summary = summary | default("", true) -%}
{% set review_findings = findings | default([], true) -%}
{% set review_stats = stats | default({}, true) -%}
{% set overall_confidence = confidence | default(0, true) -%}
{% set min_confidence = min_confidence | default(0.5, true) -%}
{% set repo = repository | default("", true) -%}
{% set pr_num = pr_number | default("", true) -%}
{% set head_sha = sha | default("", true) -%}

{# ── Separate findings by confidence ─────────────────────────────── #}
{% set high_conf = [] -%}
{% set low_conf = [] -%}
{% for f in review_findings -%}
{% if f.confidence | default(1.0, true) >= min_confidence -%}
{% set _ = high_conf.append(f) -%}
{% else -%}
{% set _ = low_conf.append(f) -%}
{% endif -%}
{% endfor -%}

{# ── Group by severity ───────────────────────────────────────────── #}
{% set by_severity = {"error": [], "warn": [], "info": [], "suggestion": []} -%}
{% for f in high_conf -%}
{% set sev = f.severity | default("info", true) -%}
{% if sev in by_severity -%}
{% set _ = by_severity[sev].append(f) -%}
{% else -%}
{% set _ = by_severity["info"].append(f) -%}
{% endif -%}
{% endfor -%}

{# ── Header ──────────────────────────────────────────────────────── #}
## {{ agent_name }} Code Review

{% if review_stats -%}
{% set total = review_stats.findings_count | default(high_conf | length, true) -%}
{% set files = review_stats.files_reviewed | default(0, true) -%}
{% set sev_counts = review_stats.by_severity | default({}, true) -%}
{% set errors = sev_counts.error | default(0, true) -%}
{% set warns = sev_counts.warn | default(0, true) -%}
{% if errors > 0 -%}
{{ "fail" | badge }} **{{ total }}** finding{{ "s" if total != 1 else "" }} across **{{ files }}** file{{ "s" if files != 1 else "" }}
{% elif warns > 0 -%}
{{ "warn" | badge }} **{{ total }}** finding{{ "s" if total != 1 else "" }} across **{{ files }}** file{{ "s" if files != 1 else "" }}
{% else -%}
{{ "pass" | badge }} **{{ total }}** finding{{ "s" if total != 1 else "" }} across **{{ files }}** file{{ "s" if files != 1 else "" }}
{% endif -%}
{% endif -%}

{% if review_summary %}
{{ review_summary }}
{% endif %}

{% if agent_model -%}
<sub>Model: {{ agent_model }}{% if overall_confidence %} · Confidence: {{ (overall_confidence * 100) | round(0) | int }}%{% endif %}</sub>
{% endif %}

{# ── Errors (blocking) ───────────────────────────────────────────── #}
{% if by_severity.error -%}
> [!CAUTION]
> ### Errors ({{ by_severity.error | length }})
>
{% for f in by_severity.error -%}
> {{ "fail" | badge }} **{{ f.file }}{% if f.line %}:{{ f.line }}{% endif %}** — {{ f.title | default(f.message, true) }}
{% endfor %}

{% for f in by_severity.error -%}
{% set permalink = "" -%}
{% if repo and head_sha and f.file and f.line -%}
{% set permalink = "https://github.com/" ~ repo ~ "/blob/" ~ head_sha ~ "/" ~ f.file ~ "#L" ~ f.line -%}
{% endif -%}
- [ ] {{ "fail" | badge }} {% if permalink %}[`{{ f.file }}:{{ f.line }}`]({{ permalink }}){% else %}`{{ f.file }}{% if f.line %}:{{ f.line }}{% endif %}`{% endif %}{% if f.category %} · `{{ f.category }}`{% endif %}{% if f.confidence %} · {{ (f.confidence * 100) | round(0) | int }}%{% endif %}

  {{ f.message }}

{% if f.suggestion -%}
  **Suggestion:** {{ f.suggestion }}

{% endif -%}
{% if f.diff -%}
  ```diff
  {{ f.diff }}
  ```

{% endif -%}
{% endfor -%}
{% endif -%}
{# ── Warnings ────────────────────────────────────────────────────── #}
{% if by_severity.warn -%}
### Warnings ({{ by_severity.warn | length }})

{% for f in by_severity.warn -%}
{% set permalink = "" -%}
{% if repo and head_sha and f.file and f.line -%}
{% set permalink = "https://github.com/" ~ repo ~ "/blob/" ~ head_sha ~ "/" ~ f.file ~ "#L" ~ f.line -%}
{% endif -%}
- [ ] {{ "warn" | badge }} {% if permalink %}[`{{ f.file }}:{{ f.line }}`]({{ permalink }}){% else %}`{{ f.file }}{% if f.line %}:{{ f.line }}{% endif %}`{% endif %}{% if f.category %} · `{{ f.category }}`{% endif %}{% if f.confidence %} · {{ (f.confidence * 100) | round(0) | int }}%{% endif %}

  {{ f.message }}

{% if f.suggestion -%}
  **Suggestion:** {{ f.suggestion }}

{% endif -%}
{% if f.diff -%}
  ```diff
  {{ f.diff }}
  ```

{% endif -%}
{% endfor -%}
{% endif -%}
{# ── Info / Suggestions ──────────────────────────────────────────── #}
{% set minor = by_severity.info + by_severity.suggestion -%}
{% if minor -%}
<details>
<summary><strong>Info & Suggestions</strong> ({{ minor | length }})</summary>

{% for f in minor -%}
{% set permalink = "" -%}
{% if repo and head_sha and f.file and f.line -%}
{% set permalink = "https://github.com/" ~ repo ~ "/blob/" ~ head_sha ~ "/" ~ f.file ~ "#L" ~ f.line -%}
{% endif -%}
{% set badge_type = "info" if f.severity | default("info", true) == "info" else "skip" -%}
- [ ] {{ badge_type | badge }} {% if permalink %}[`{{ f.file }}:{{ f.line }}`]({{ permalink }}){% else %}`{{ f.file }}{% if f.line %}:{{ f.line }}{% endif %}`{% endif %}{% if f.category %} · `{{ f.category }}`{% endif %}

  {{ f.message }}

{% if f.suggestion -%}
  **Suggestion:** {{ f.suggestion }}

{% endif -%}
{% if f.diff -%}
  ```diff
  {{ f.diff }}
  ```

{% endif -%}
{% endfor -%}

</details>

{% endif -%}
{# ── Low-confidence findings (collapsed) ─────────────────────────── #}
{% if low_conf -%}
<details>
<summary><strong>Low-confidence findings</strong> ({{ low_conf | length }}, below {{ (min_confidence * 100) | round(0) | int }}% threshold)</summary>

{% for f in low_conf -%}
- `{{ f.file }}{% if f.line %}:{{ f.line }}{% endif %}` — {{ f.message }}{% if f.confidence %} ({{ (f.confidence * 100) | round(0) | int }}%){% endif %}

{% endfor -%}

</details>

{% endif -%}
{# ── File summary ────────────────────────────────────────────────── #}
{% set files_with_findings = [] -%}
{% for f in high_conf -%}
{% if f.file not in files_with_findings -%}
{% set _ = files_with_findings.append(f.file) -%}
{% endif -%}
{% endfor -%}
{% if review_stats.files_reviewed | default(0, true) > 0 and files_with_findings -%}
<details>
<summary><strong>Files reviewed</strong> ({{ review_stats.files_reviewed }})</summary>

{% set reviewed_files = review_stats.reviewed_files | default([], true) -%}
{% if reviewed_files -%}
{% for rf in reviewed_files -%}
{% if rf in files_with_findings -%}
- {{ "warn" | badge }} `{{ rf }}`
{% else -%}
- {{ "pass" | badge }} `{{ rf }}`
{% endif -%}
{% endfor -%}
{% else -%}
{% for rf in files_with_findings -%}
- {{ "warn" | badge }} `{{ rf }}`
{% endfor -%}
{% endif %}

</details>
{% endif -%}
