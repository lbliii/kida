{% set repo = repository | default("", true) -%}
{% set ver = version | default("", true) -%}
{% set prev = previous_version | default("", true) -%}
{% set date = release_date | default("", true) -%}
{% set pulls = pull_requests | default([], true) -%}
{% set contribs = contributors | default([], true) -%}
{% set new_contribs = new_contributors | default([], true) -%}
{% set stats = diff_stats | default({}, true) -%}
{% set commits = direct_commits | default([], true) -%}
{% set bench = benchmarks | default({}, true) -%}

{# ── Categorize ──────────────────────────────────────────────────── #}
{% set categories = {
  "breaking": {"label": "Breaking Changes", "color": "red", "items": []},
  "feat": {"label": "New Features", "color": "green", "items": []},
  "fix": {"label": "Bug Fixes", "color": "yellow", "items": []},
  "perf": {"label": "Performance", "color": "cyan", "items": []},
  "docs": {"label": "Documentation", "color": "blue", "items": []},
  "refactor": {"label": "Refactoring", "color": "magenta", "items": []},
  "deps": {"label": "Dependencies", "color": "white", "items": []},
  "other": {"label": "Other", "color": "white", "items": []}
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
{% for prefix in ["feat", "fix", "perf", "docs", "refactor"] -%}
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

{{ "What's New" | bold }}
{% if ver %}{{ ver | bold | cyan }}{% endif %}{% if date %} {{ ("(" ~ date ~ ")") | dim }}{% endif %}

{% if stats -%}
{% set files = stats.files_changed | default(0) -%}
{% set ins = stats.insertions | default(0) -%}
{% set dels = stats.deletions | default(0) -%}
{% if files > 0 -%}
{{ ("+" ~ ins | string) | green }}  {{ ("-" ~ dels | string) | red }}  {{ (files | string ~ " files") | dim }}
{% endif -%}
{% endif -%}

{# ── Breaking changes ────────────────────────────────────────────── #}
{% if categories.breaking.items -%}

{{ " BREAKING CHANGES " | bold | inverse | red }}

{% for pr in categories.breaking.items -%}
{% set note = pr.release_note | default(pr.title, true) -%}
  {{ "fail" | badge }} {{ note | bold }}{% if pr.number %} {{ ("#" ~ pr.number | string) | dim }}{% endif %}

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

{{ " Highlights " | bold | inverse | cyan }}

{% for pr in highlighted -%}
  {{ "info" | badge }} {{ pr.release_note | bold | bright_cyan }}{% if pr.number %} {{ ("#" ~ pr.number | string) | dim }}{% endif %}

{% endfor -%}
{% endif -%}
{# ── Category sections ───────────────────────────────────────────── #}
{% for key, cat in categories.items() -%}
{% if key not in ["breaking", "deps"] and cat.items -%}

{{ (" " ~ cat.label ~ " ") | bold | fg(cat.color) }}

{% for pr in cat.items -%}
{% set display = pr.release_note | default(pr.title, true) -%}
  {{ "pass" | badge if key == "feat" else "info" | badge }} {{ display }}{% if pr.number %} {{ ("#" ~ pr.number | string) | dim }}{% endif %}{% if pr.author %} {{ ("@" ~ pr.author) | dim }}{% endif %}

{% endfor -%}
{% endif -%}
{% endfor -%}
{# ── Dependencies (compact) ──────────────────────────────────────── #}
{% if categories.deps.items -%}

{{ " Dependencies " | dim }} {{ ("(" ~ categories.deps.items | length | string ~ " updates)") | dim }}

{% for pr in categories.deps.items -%}
  {{ "skip" | badge }} {{ pr.title | dim }}{% if pr.number %} {{ ("#" ~ pr.number | string) | dim }}{% endif %}

{% endfor -%}
{% endif -%}
{# ── Benchmarks ──────────────────────────────────────────────────── #}
{% if bench.deltas | default([], true) -%}

{{ " Performance " | bold | inverse | green }}

{% for d in bench.deltas -%}
{% if d.change < 0 -%}
  {{ "pass" | badge }} {{ d.name | kv(d.change | string ~ "%" | green | bold) }}
{% elif d.change > 5 -%}
  {{ "warn" | badge }} {{ d.name | kv("+" ~ d.change | string ~ "%" | red | bold) }}
{% else -%}
  {{ "info" | badge }} {{ d.name | kv(d.change | string ~ "%") }}
{% endif -%}
{% endfor -%}
{% endif -%}
{# ── New contributors ───────────────────────────────────────────── #}
{% if new_contribs -%}

{{ " Welcome! " | bold | inverse | yellow }}

{% for c in new_contribs -%}
  {{ "pass" | badge }} {{ ("@" ~ c) | bold | bright_green }} {{ "— first contribution" | dim }}
{% endfor -%}
{% endif -%}
{# ── All contributors ───────────────────────────────────────────── #}
{% if contribs -%}

{{ "Contributors" | dim }}: {% for c in contribs %}{{ ("@" ~ c) | cyan }}{% if not loop.last %} {{ "·" | dim }} {% endif %}{% endfor %}

{% endif -%}
