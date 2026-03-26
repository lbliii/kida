## Coverage Report

{% set pct = totals.percent_covered | round(1) -%}
{% if pct >= 80 -%}
{{ "pass" | badge }} **{{ pct }}%** overall coverage
{% elif pct >= 60 -%}
{{ "warn" | badge }} **{{ pct }}%** overall coverage
{% else -%}
{{ "fail" | badge }} **{{ pct }}%** overall coverage
{% endif %}

{% if files -%}
| File | Coverage | Missing Lines |
| --- | --- | --- |
{% for f in files | sort(attribute="summary.percent_covered") -%}
{% set fpct = f.summary.percent_covered | default(0) | round(1) -%}
| `{{ f.filename }}` | {{ fpct }}% | {{ f.summary.missing_lines | default("", true) }} |
{% endfor -%}
{% endif -%}
