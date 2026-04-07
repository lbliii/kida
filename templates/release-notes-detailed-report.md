{% set repo = repository | default("", true) -%}
{% set ver = version | default("", true) -%}
{% set prev = previous_version | default("", true) -%}
{% set date = release_date | default("", true) -%}
{% set pulls = pull_requests | default([], true) -%}
{% set contribs = contributors | default([], true) -%}
{% set new_contribs = new_contributors | default([], true) -%}
{% set compare = compare_url | default("", true) -%}
{% set stats = diff_stats | default({}, true) -%}
{% set commits = direct_commits | default([], true) -%}
{% set bench = benchmarks | default({}, true) -%}

{# ── Categorize ──────────────────────────────────────────────────── #}
{% set categories = {
  "breaking": {"label": "Breaking Changes", "items": []},
  "feat": {"label": "New Features", "items": []},
  "fix": {"label": "Bug Fixes", "items": []},
  "perf": {"label": "Performance", "items": []},
  "docs": {"label": "Documentation", "items": []},
  "refactor": {"label": "Refactoring", "items": []},
  "test": {"label": "Tests", "items": []},
  "ci": {"label": "CI / Automation", "items": []},
  "deps": {"label": "Dependencies", "items": []},
  "chore": {"label": "Maintenance", "items": []},
  "other": {"label": "Other Changes", "items": []}
} -%}

{% for pr in pulls -%}
{% set labels = pr.labels | default([], true) -%}
{% set title_lower = pr.title | lower -%}
{% set is_breaking = "breaking" in labels or "BREAKING CHANGE" in pr.body | default("", true) -%}
{% set is_dep = pr.author | default("", true) in ["dependabot[bot]", "renovate[bot]", "dependabot", "renovate"] or "deps" in labels -%}
{% if is_breaking -%}
{% set _ = categories["breaking"]["items"].append(pr) -%}
{% elif is_dep -%}
{% set _ = categories["deps"]["items"].append(pr) -%}
{% else -%}
{% set matched = namespace(found=false) -%}
{% for prefix in ["feat", "fix", "perf", "docs", "refactor", "test", "ci", "chore"] -%}
{% if not matched.found -%}
{% if title_lower.startswith(prefix ~ ":") or title_lower.startswith(prefix ~ "(") or labels | select("equalto", prefix) | list | length > 0 -%}
{% set _ = categories[prefix]["items"].append(pr) -%}
{% set matched.found = true -%}
{% endif -%}
{% endif -%}
{% endfor -%}
{% if not matched.found -%}
{% set _ = categories["other"]["items"].append(pr) -%}
{% endif -%}
{% endif -%}
{% endfor -%}

{# ── Header ──────────────────────────────────────────────────────── #}
{% if ver -%}
# {{ ver }}{% if date %} — {{ date }}{% endif %}

{% endif -%}
{% if stats -%}
{% set files = stats.files_changed | default(0) -%}
{% set ins = stats.insertions | default(0) -%}
{% set dels = stats.deletions | default(0) -%}
{% set new = stats.new_files | default([], true) -%}
{% if files > 0 -%}
| Stat | Value |
| --- | --- |
| Files changed | {{ files }} |
| Insertions | +{{ ins }} |
| Deletions | -{{ dels }} |
{% if new %}| New files | {{ new | length }} |{% endif %}

{% if new -%}
<details>
<summary>New files</summary>

{% for f in new -%}
- `{{ f }}`
{% endfor %}

</details>

{% endif -%}
{% endif -%}
{% endif -%}
{# ── Breaking Changes ────────────────────────────────────────────── #}
{% if categories.breaking.items -%}
> [!CAUTION]
> ## Breaking Changes
>
{% for pr in categories.breaking.items -%}
> - **{{ pr.release_note | default(pr.title, true) }}**{% if pr.number %} ([#{{ pr.number }}](https://github.com/{{ repo }}/pull/{{ pr.number }})){% endif %}
{% endfor %}

{% for pr in categories.breaking.items -%}
{% if pr.body | default("", true) -%}
<details>
<summary>Details: {{ pr.title }} (#{{ pr.number }})</summary>

{{ pr.body }}

</details>

{% endif -%}
{% endfor -%}
{% endif -%}
{# ── Highlights ──────────────────────────────────────────────────── #}
{% set highlighted = [] -%}
{% for pr in pulls -%}
{% if pr.release_note | default("", true) and pr not in categories.breaking.items -%}
{% set _ = highlighted.append(pr) -%}
{% endif -%}
{% endfor -%}
{% if highlighted -%}
## Highlights

{% for pr in highlighted -%}
### {{ pr.release_note }}

{% if pr.body_excerpt | default("", true) -%}
{{ pr.body_excerpt }}

{% endif -%}
{% if pr.number -%}
:point_right: [#{{ pr.number }}](https://github.com/{{ repo }}/pull/{{ pr.number }}){% if pr.author %} by @{{ pr.author }}{% endif %}

{% endif -%}
{% endfor -%}
{% endif -%}
{# ── Category sections with full PR details ──────────────────────── #}
{% for key, cat in categories.items() -%}
{% if key not in ["breaking", "deps"] and cat.items -%}
## {{ cat.label }}

{% for pr in cat.items -%}
{% set display = pr.release_note | default(pr.title, true) -%}
{% set issues = pr.linked_issues | default([], true) -%}
### {{ display }}

{% if pr.number -%}
[#{{ pr.number }}](https://github.com/{{ repo }}/pull/{{ pr.number }}){% if pr.author %} by @{{ pr.author }}{% endif %}{% if issues %} — closes {% for i in issues %}[#{{ i.number }}](https://github.com/{{ repo }}/issues/{{ i.number }}){% if not loop.last %}, {% endif %}{% endfor %}{% endif %}

{% endif -%}
{% if pr.body | default("", true) -%}
{{ pr.body }}

{% endif -%}
---

{% endfor -%}
{% endif -%}
{% endfor -%}
{# ── Dependencies ────────────────────────────────────────────────── #}
{% if categories.deps.items -%}
## Dependencies ({{ categories.deps.items | length }} updates)

{% set dep_updates = [] -%}
{% for pr in categories.deps.items -%}
{% if pr.dependency_updates | default([], true) -%}
{% for dep in pr.dependency_updates -%}
{% set _ = dep_updates.append(dep) -%}
{% endfor -%}
{% else -%}
{% set _ = dep_updates.append({"name": pr.title, "from": "", "to": ""}) -%}
{% endif -%}
{% endfor -%}
{% if dep_updates and dep_updates[0].from | default("", true) -%}
| Package | From | To |
| --- | --- | --- |
{% for dep in dep_updates -%}
| `{{ dep.name }}` | {{ dep.from }} | {{ dep.to }} |
{% endfor %}
{% else -%}
{% for pr in categories.deps.items -%}
- {{ pr.title }}{% if pr.number %} ([#{{ pr.number }}](https://github.com/{{ repo }}/pull/{{ pr.number }})){% endif %}

{% endfor -%}
{% endif %}
{% endif -%}
{# ── Direct commits ──────────────────────────────────────────────── #}
{% if commits -%}
## Direct Commits

| SHA | Message | Author |
| --- | --- | --- |
{% for c in commits -%}
| [`{{ c.sha[:7] }}`](https://github.com/{{ repo }}/commit/{{ c.sha }}) | {{ c.message }} | @{{ c.author | default("—", true) }} |
{% endfor %}

{% endif -%}
{# ── Benchmarks ──────────────────────────────────────────────────── #}
{% if bench.deltas | default([], true) -%}
## Performance Benchmarks

| Benchmark | Previous | Current | Change |
| --- | --- | --- | --- |
{% for d in bench.deltas -%}
{% if d.change < 0 -%}
| {{ d.name }} | {{ d.previous | default("—", true) }} | {{ d.current | default("—", true) }} | :rocket: **{{ d.change }}%** |
{% elif d.change > 5 -%}
| {{ d.name }} | {{ d.previous | default("—", true) }} | {{ d.current | default("—", true) }} | :warning: **+{{ d.change }}%** |
{% else -%}
| {{ d.name }} | {{ d.previous | default("—", true) }} | {{ d.current | default("—", true) }} | {{ d.change }}% |
{% endif -%}
{% endfor %}

{% endif -%}
{# ── Contributors ────────────────────────────────────────────────── #}
{% if new_contribs -%}
## New Contributors :tada:

{% for c in new_contribs -%}
Welcome **@{{ c }}**! Thank you for your first contribution.
{% endfor %}

{% endif -%}
{% if contribs -%}
## All Contributors

{% for c in contribs -%}
@{{ c }}{% if not loop.last %} | {% endif %}
{% endfor %}

{% endif -%}
{# ── Footer ──────────────────────────────────────────────────────── #}
{% if compare -%}
---
**Full diff:** [{{ prev }}...{{ ver }}]({{ compare }})
{% endif -%}
