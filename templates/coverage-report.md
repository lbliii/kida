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
| File | Coverage |
| --- | --- |
{% for fname, fdata in files | dictsort -%}
{% set fpct = fdata.summary.percent_covered | default(0) | round(1) -%}
| `{{ fname }}` | {{ fpct }}% |
{% endfor -%}
{% endif -%}
