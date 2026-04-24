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

{# ── Categorize PRs ─────────────────────────────────────────────── #}
{% set categories = {
  "breaking": {"label": "Breaking Changes", "items": []},
  "highlight": {"label": "Highlights", "items": []},
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
{% set release_note = pr.release_note | default("", true) -%}

{# Breaking changes always promoted to top #}
{% if is_breaking -%}
{% set _ = categories["breaking"]["items"].append(pr) -%}
{% elif is_dep -%}
{% set _ = categories["deps"]["items"].append(pr) -%}
{% else -%}
{% set matched = {"found": false} -%}
{% for prefix in ["feat", "fix", "perf", "docs", "refactor", "test", "ci", "chore"] -%}
{% if not matched.found -%}
{% set has_prefix = title_lower.startswith(prefix ~ ":") or title_lower.startswith(prefix ~ "(") -%}
{% set has_label = labels | select("equalto", prefix) | list | length > 0 -%}
{% if has_prefix or has_label -%}
{% set _ = categories[prefix]["items"].append(pr) -%}
{% set _ = matched.update({"found": true}) -%}
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
## {{ ver }}{% if date %} ({{ date }}){% endif %}

{% endif -%}
{% if stats -%}
{% set files = stats.files_changed | default(0) -%}
{% set ins = stats.insertions | default(0) -%}
{% set dels = stats.deletions | default(0) -%}
{% if files > 0 -%}
> **+{{ ins }}** / **-{{ dels }}** across **{{ files }}** files
{% endif -%}

{% endif -%}
{# ── Breaking Changes (always first, always visible) ─────────────── #}
{% if categories.breaking.items -%}
> [!CAUTION]
> ### Breaking Changes
>
{% for pr in categories.breaking.items -%}
{% set note = pr.release_note | default(pr.title, true) -%}
> - {{ note }}{% if pr.number %} ([#{{ pr.number }}](https://github.com/{{ repo }}/pull/{{ pr.number }})){% endif %}
{% endfor %}

{% endif -%}
{# ── Highlights (PRs with <!-- release-note: ... --> markers) ──── #}
{% set highlighted = [] -%}
{% for pr in pulls -%}
{% if pr.release_note | default("", true) and pr not in categories.breaking.items -%}
{% set _ = highlighted.append(pr) -%}
{% endif -%}
{% endfor -%}
{% if highlighted -%}
### Highlights

{% for pr in highlighted -%}
- **{{ pr.release_note }}**{% if pr.number %} ([#{{ pr.number }}](https://github.com/{{ repo }}/pull/{{ pr.number }})){% endif %}{% if pr.author %} — @{{ pr.author }}{% endif %}

{% endfor %}
{% endif -%}
{# ── Categories ──────────────────────────────────────────────────── #}
{% for key, cat in categories.items() -%}
{% if key not in ["breaking", "deps", "highlight"] and cat.items -%}
### {{ cat.label }}

{% for pr in cat.items -%}
{% set display = pr.release_note | default(pr.title, true) -%}
{% set issues = pr.linked_issues | default([], true) -%}
- {{ display }}{% if pr.number %} ([#{{ pr.number }}](https://github.com/{{ repo }}/pull/{{ pr.number }})){% endif %}{% if issues %} — closes {% for i in issues %}[#{{ i.number }}](https://github.com/{{ repo }}/issues/{{ i.number }}){% if not loop.last %}, {% endif %}{% endfor %}{% endif %}

{% if pr.body_excerpt | default("", true) -%}
  <details><summary>Details</summary>

  {{ pr.body_excerpt | safe }}

  </details>

{% endif -%}
{% endfor %}
{% endif -%}
{% endfor -%}
{# ── Dependencies (collapsed) ───────────────────────────────────── #}
{% if categories.deps.items -%}
<details>
<summary><strong>Dependencies</strong> ({{ categories.deps.items | length }} updates)</summary>

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
{% endfor -%}
{% else -%}
{% for pr in categories.deps.items -%}
- {{ pr.title }}{% if pr.number %} ([#{{ pr.number }}](https://github.com/{{ repo }}/pull/{{ pr.number }})){% endif %}

{% endfor -%}
{% endif %}

</details>

{% endif -%}
{# ── Direct commits (non-PR changes) ────────────────────────────── #}
{% if commits -%}
<details>
<summary><strong>Direct commits</strong> ({{ commits | length }})</summary>

{% for c in commits -%}
- `{{ c.sha[:7] }}` {{ c.message }}{% if c.author %} — @{{ c.author }}{% endif %}

{% endfor %}

</details>

{% endif -%}
{# ── Benchmark deltas ────────────────────────────────────────────── #}
{% if bench.deltas | default([], true) -%}
### Performance

| Benchmark | Change |
| --- | --- |
{% for d in bench.deltas -%}
{% if d.change < 0 -%}
| {{ d.name }} | :rocket: **{{ d.change }}%** faster |
{% elif d.change > 5 -%}
| {{ d.name }} | :warning: **+{{ d.change }}%** slower |
{% else -%}
| {{ d.name }} | {{ d.change }}% |
{% endif -%}
{% endfor %}

{% endif -%}
{# ── New contributors ───────────────────────────────────────────── #}
{% if new_contribs -%}
### New Contributors

{% for c in new_contribs -%}
Welcome @{{ c }}! :tada:
{% endfor %}

{% endif -%}
{# ── All contributors ───────────────────────────────────────────── #}
{% if contribs -%}
### Contributors

{% for c in contribs -%}
@{{ c }}{% if not loop.last %} | {% endif %}
{% endfor %}

{% endif -%}
{# ── Footer ──────────────────────────────────────────────────────── #}
{% if compare -%}
---
**Full diff:** [{{ prev }}...{{ ver }}]({{ compare }})
{% endif -%}
