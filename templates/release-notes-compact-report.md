{% set repo = repository | default("", true) -%}
{% set ver = version | default("", true) -%}
{% set prev = previous_version | default("", true) -%}
{% set date = release_date | default("", true) -%}
{% set pulls = pull_requests | default([], true) -%}
{% set compare = compare_url | default("", true) -%}
{% set stats = diff_stats | default({}, true) -%}

{% if ver -%}
## {{ ver }}{% if date %} ({{ date }}){% endif %}

{% endif -%}
{% if stats.files_changed | default(0) > 0 -%}
> +{{ stats.insertions | default(0) }} / -{{ stats.deletions | default(0) }} across {{ stats.files_changed }} files

{% endif -%}
{# ── Breaking changes inline ─────────────────────────────────────── #}
{% set breaking = [] -%}
{% for pr in pulls -%}
{% if "breaking" in pr.labels | default([], true) or "BREAKING CHANGE" in pr.body | default("", true) -%}
{% set _ = breaking.append(pr) -%}
{% endif -%}
{% endfor -%}
{% if breaking -%}
> [!CAUTION]
{% for pr in breaking -%}
> **Breaking:** {{ pr.release_note | default(pr.title, true) }}{% if pr.number %} (#{{ pr.number }}){% endif %}
{% endfor %}

{% endif -%}
{% for pr in pulls -%}
{% if pr not in breaking -%}
{% set note = pr.release_note | default(pr.title, true) -%}
- {{ note }}{% if pr.number %} ([#{{ pr.number }}](https://github.com/{{ repo }}/pull/{{ pr.number }})){% endif %}

{% endif -%}
{% endfor -%}
{% if compare -%}

[{{ prev }}...{{ ver }}]({{ compare }})
{% endif -%}
