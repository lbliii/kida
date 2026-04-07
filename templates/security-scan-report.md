{% set scan_tool = tool | default("Security Scanner", true) -%}
{% set scan_status = status | default("", true) -%}
{% set scan_findings = findings | default([], true) -%}
{% set scan_summary = summary | default("", true) -%}
{% set scan_stats = stats | default({}, true) -%}
{% set repo = repository | default("", true) -%}
{% set head_sha = sha | default("", true) -%}
{% set scan_url = report_url | default("", true) -%}
{% set policy = policy_status | default("", true) -%}

{# ── Group findings by severity ──────────────────────────────────── #}
{% set by_severity = {"critical": [], "high": [], "medium": [], "low": [], "info": []} -%}
{% for f in scan_findings -%}
{% set sev = f.severity | default("info", true) | lower -%}
{% if sev in by_severity -%}
{% set _ = by_severity[sev].append(f) -%}
{% else -%}
{% set _ = by_severity["info"].append(f) -%}
{% endif -%}
{% endfor -%}

{% set critical_count = by_severity.critical | length -%}
{% set high_count = by_severity.high | length -%}
{% set medium_count = by_severity.medium | length -%}
{% set low_count = by_severity.low | length -%}
{% set info_count = by_severity.info | length -%}
{% set total = scan_findings | length -%}

{# ── Header ──────────────────────────────────────────────────────── #}
## {{ scan_tool }} Results

{% if critical_count > 0 or high_count > 0 -%}
{{ "fail" | badge }} **{{ total }}** finding{{ "s" if total != 1 else "" }}{% if critical_count %} · {{ critical_count }} critical{% endif %}{% if high_count %} · {{ high_count }} high{% endif %}{% if medium_count %} · {{ medium_count }} medium{% endif %}
{% elif medium_count > 0 -%}
{{ "warn" | badge }} **{{ total }}** finding{{ "s" if total != 1 else "" }} · {{ medium_count }} medium{% if low_count %} · {{ low_count }} low{% endif %}
{% elif total > 0 -%}
{{ "info" | badge }} **{{ total }}** finding{{ "s" if total != 1 else "" }} ({{ low_count }} low{% if info_count %}, {{ info_count }} info{% endif %})
{% else -%}
{{ "pass" | badge }} No findings
{% endif %}

{% if policy -%}
Policy: {% if policy == "pass" %}{{ "pass" | badge }} **passed**{% elif policy == "warn" %}{{ "warn" | badge }} **warning**{% else %}{{ "fail" | badge }} **failed**{% endif %}

{% endif -%}
{% if scan_summary %}
{{ scan_summary }}
{% endif %}

{# ── Critical findings ───────────────────────────────────────────── #}
{% if by_severity.critical -%}
> [!CAUTION]
> ### Critical ({{ critical_count }})
>
{% for f in by_severity.critical -%}
> - **{{ f.rule | default(f.id | default("", true), true) }}** — {{ f.title | default(f.message, true) }}{% if f.cwe %} (CWE-{{ f.cwe }}){% endif %}
{% endfor %}

{% for f in by_severity.critical -%}
{% set permalink = "" -%}
{% if repo and head_sha and f.file and f.line -%}
{% set permalink = "https://github.com/" ~ repo ~ "/blob/" ~ head_sha ~ "/" ~ f.file ~ "#L" ~ f.line -%}
{% endif -%}
- [ ] {{ "fail" | badge }} **{{ f.rule | default(f.id | default("finding", true), true) }}** — {% if permalink %}[`{{ f.file }}:{{ f.line }}`]({{ permalink }}){% elif f.file %}`{{ f.file }}{% if f.line %}:{{ f.line }}{% endif %}`{% endif %}

  {{ f.message | default(f.title, true) }}

{% if f.remediation | default("", true) -%}
  **Remediation:** {{ f.remediation }}

{% endif -%}
{% if f.cve | default("", true) -%}
  [:link: {{ f.cve }}](https://nvd.nist.gov/vuln/detail/{{ f.cve }})
{% endif -%}
{% if f.diff | default("", true) -%}
  ```diff
  {{ f.diff }}
  ```
{% endif %}

{% endfor -%}
{% endif -%}
{# ── High findings ───────────────────────────────────────────────── #}
{% if by_severity.high -%}
### High ({{ high_count }})

{% for f in by_severity.high -%}
{% set permalink = "" -%}
{% if repo and head_sha and f.file and f.line -%}
{% set permalink = "https://github.com/" ~ repo ~ "/blob/" ~ head_sha ~ "/" ~ f.file ~ "#L" ~ f.line -%}
{% endif -%}
- [ ] {{ "fail" | badge }} **{{ f.rule | default(f.id | default("finding", true), true) }}** — {% if permalink %}[`{{ f.file }}:{{ f.line }}`]({{ permalink }}){% elif f.file %}`{{ f.file }}{% if f.line %}:{{ f.line }}{% endif %}`{% endif %}{% if f.cwe %} · CWE-{{ f.cwe }}{% endif %}

  {{ f.message | default(f.title, true) }}

{% if f.remediation | default("", true) -%}
  **Remediation:** {{ f.remediation }}

{% endif -%}
{% endfor -%}
{% endif -%}
{# ── Medium findings ─────────────────────────────────────────────── #}
{% if by_severity.medium -%}
<details>
<summary><strong>Medium</strong> ({{ medium_count }})</summary>

{% for f in by_severity.medium -%}
{% set permalink = "" -%}
{% if repo and head_sha and f.file and f.line -%}
{% set permalink = "https://github.com/" ~ repo ~ "/blob/" ~ head_sha ~ "/" ~ f.file ~ "#L" ~ f.line -%}
{% endif -%}
- [ ] {{ "warn" | badge }} **{{ f.rule | default(f.id | default("finding", true), true) }}** — {% if permalink %}[`{{ f.file }}:{{ f.line }}`]({{ permalink }}){% elif f.file %}`{{ f.file }}{% if f.line %}:{{ f.line }}{% endif %}`{% endif %}

  {{ f.message | default(f.title, true) }}

{% if f.remediation | default("", true) -%}
  **Remediation:** {{ f.remediation }}

{% endif -%}
{% endfor %}

</details>

{% endif -%}
{# ── Low + Info findings (collapsed) ─────────────────────────────── #}
{% set minor = by_severity.low + by_severity.info -%}
{% if minor -%}
<details>
<summary><strong>Low & Info</strong> ({{ minor | length }})</summary>

{% for f in minor -%}
- {{ "info" | badge }} **{{ f.rule | default(f.id | default("", true), true) }}**{% if f.file %} — `{{ f.file }}{% if f.line %}:{{ f.line }}{% endif %}`{% endif %}: {{ f.message | default(f.title, true) }}
{% endfor %}

</details>

{% endif -%}
{# ── Category breakdown ──────────────────────────────────────────── #}
{% set categories = {} -%}
{% for f in scan_findings -%}
{% set cat = f.category | default("other", true) -%}
{% if cat not in categories -%}
{% set _ = categories.update({cat: 0}) -%}
{% endif -%}
{% set _ = categories.update({cat: categories[cat] + 1}) -%}
{% endfor -%}
{% if categories | length > 1 -%}
### By category

| Category | Count |
| --- | --- |
{% for cat, count in categories | dictsort -%}
| {{ cat }} | {{ count }} |
{% endfor %}

{% endif -%}
{# ── Footer ──────────────────────────────────────────────────────── #}
{% if scan_url -%}
---
[:page_facing_up: Full report]({{ scan_url }})
{% endif -%}
