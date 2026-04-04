## Coverage Report

{% set pct = totals.percent_covered | round(1) -%}
{% if pct >= 80 -%}
{{ "pass" | badge }} **{{ pct }}%** overall coverage
{% elif pct >= 60 -%}
{{ "warn" | badge }} **{{ pct }}%** overall coverage
{% else -%}
{{ "fail" | badge }} **{{ pct }}%** overall coverage
{% endif %}

{% if changed_files is defined and changed_files -%}
{% set diff_files = {} -%}
{% for fname, fdata in files | dictsort -%}
{% for cf in changed_files -%}
{% if fname.endswith(cf) or cf.endswith(fname) -%}
{% set _ = diff_files.update({fname: fdata}) -%}
{% endif -%}
{% endfor -%}
{% endfor -%}
{% if diff_files -%}
### Changed files

| File | Coverage |
| --- | --- |
{% for fname, fdata in diff_files | dictsort -%}
{% set fpct = fdata.summary.percent_covered | default(0) | round(1) -%}
| `{{ fname }}` | {{ fpct }}% |
{% endfor %}
{% endif -%}

<details><summary>All files</summary>

{% endif -%}
{% if files -%}
| File | Coverage |
| --- | --- |
{% for fname, fdata in files | dictsort -%}
{% set fpct = fdata.summary.percent_covered | default(0) | round(1) -%}
| `{{ fname }}` | {{ fpct }}% |
{% endfor -%}
{% endif -%}
{% if changed_files is defined and changed_files -%}

</details>
{% endif -%}
