{% set total = summary.total | default(0, true) -%}
## {{ "pass" | badge if total == 0 else "fail" | badge }} {{ tool | default("Static Analysis", true) }} Report

{% if total == 0 -%}
No issues found.
{% else -%}
**{{ total }}** issue{{ "s" if total != 1 else "" }} found{% if summary.errors %} (**{{ summary.errors }}** error{{ "s" if summary.errors != 1 else "" }}){% endif %}.

| Level | Count |
|-------|-------|
| Errors | {{ summary.errors | default(0, true) }} |
| Warnings | {{ summary.warnings | default(0, true) }} |
| Notes | {{ summary.notes | default(0, true) }} |

{% set by_level = {} -%}
{% for r in results -%}
{% set lvl = r.level | default("warning", true) -%}
{% if lvl not in by_level -%}
{% set _ = by_level.update({lvl: []}) -%}
{% endif -%}
{% set _ = by_level[lvl].append(r) -%}
{% endfor -%}
{% for level in ["error", "warning", "note"] -%}
{% if level in by_level -%}
### {{ level | capitalize }}s ({{ by_level[level] | length }})

{% for r in by_level[level] -%}
- `{{ r.file }}:{{ r.line }}` **{{ r.rule_id }}** — {{ r.message }}
{% endfor %}

{% endif -%}
{% endfor -%}
{% endif -%}
