{% set violations = data | default([], true) -%}
{% set count = violations | length -%}
## {{ "pass" | badge if count == 0 else "fail" | badge }} Ruff Report

{% if count == 0 -%}
No violations found.
{% else -%}
**{{ count }}** violation{{ "s" if count != 1 else "" }} found.

{% set by_code = {} -%}
{% for v in violations -%}
{% set code = v.code | default("unknown", true) -%}
{% if code not in by_code -%}
{% set _ = by_code.update({code: []}) -%}
{% endif -%}
{% set _ = by_code[code].append(v) -%}
{% endfor -%}
{% for code, items in by_code.items() -%}
### {{ code }} ({{ items | length }})

{% for v in items -%}
- `{{ v.filename }}:{{ v.location.row }}` — {{ v.message }}
{% endfor %}

{% endfor -%}
{% endif -%}
