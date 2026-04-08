{% set env_name = environment | default("Preview", true) -%}
{% set deploy_url = url | default("", true) -%}
{% set deploy_status = status | default("success", true) -%}
{% set build_time = build_time_seconds | default(0, true) -%}
{% set deploy_sha = sha | default("", true) -%}
{% set deploy_branch = branch | default("", true) -%}
{% set provider = provider | default("", true) -%}
{% set bundle = bundle_stats | default({}, true) -%}
{% set lighthouse = lighthouse | default({}, true) -%}
{% set pages = pages | default([], true) -%}
{% set logs_url = logs_url | default("", true) -%}
{% set previous = previous_deploy | default({}, true) -%}

{# ── Header ──────────────────────────────────────────────────────── #}
## {{ deploy_status | badge }} Deploy {{ env_name }}

{% if deploy_url -%}
:link: **{{ deploy_url }}**
{% endif %}

{% if provider or deploy_branch or deploy_sha -%}
<sub>{% if provider %}{{ provider }}{% endif %}{% if deploy_branch %} · `{{ deploy_branch }}`{% endif %}{% if deploy_sha %} · `{{ deploy_sha[:7] }}`{% endif %}{% if build_time %} · {{ build_time }}s{% endif %}</sub>
{% endif %}

{# ── Bundle size ─────────────────────────────────────────────────── #}
{% if bundle -%}
### Bundle size

{% set total = bundle.total_size | default("", true) -%}
{% set prev_total = previous.total_size | default("", true) -%}
{% set delta = bundle.size_delta | default("", true) -%}

{% if bundle.entries | default([], true) -%}
| Entry | Size | Delta |
| --- | --- | --- |
{% for e in bundle.entries -%}
{% set d = e.delta | default("", true) -%}
{% if d and d.startswith("+") -%}
| `{{ e.name }}` | {{ e.size }} | {{ "warn" | badge }} {{ d }} |
{% elif d and d.startswith("-") -%}
| `{{ e.name }}` | {{ e.size }} | {{ "pass" | badge }} {{ d }} |
{% else -%}
| `{{ e.name }}` | {{ e.size }} | {{ d | default("—", true) }} |
{% endif -%}
{% endfor -%}
{% if total %}| **Total** | **{{ total }}** | {% if delta %}**{{ delta }}**{% else %}—{% endif %} |{% endif %}

{% elif total -%}
**Total:** {{ total }}{% if delta %} ({{ delta }} from previous){% endif %}

{% endif -%}
{% endif -%}
{# ── Lighthouse / performance scores ─────────────────────────────── #}
{% if lighthouse -%}
### Performance

{% set perf = lighthouse.performance | default(0, true) -%}
{% set a11y = lighthouse.accessibility | default(0, true) -%}
{% set bp = lighthouse.best_practices | default(0, true) -%}
{% set seo = lighthouse.seo | default(0, true) -%}

| Metric | Score |
| --- | --- |
{% if perf is defined and perf is not none -%}
{% if perf >= 90 -%}
| Performance | {{ "pass" | badge }} **{{ perf }}** |
{% elif perf >= 50 -%}
| Performance | {{ "warn" | badge }} **{{ perf }}** |
{% else -%}
| Performance | {{ "fail" | badge }} **{{ perf }}** |
{% endif -%}
{% endif -%}
{% if a11y is defined and a11y is not none -%}
{% if a11y >= 90 -%}
| Accessibility | {{ "pass" | badge }} **{{ a11y }}** |
{% elif a11y >= 50 -%}
| Accessibility | {{ "warn" | badge }} **{{ a11y }}** |
{% else -%}
| Accessibility | {{ "fail" | badge }} **{{ a11y }}** |
{% endif -%}
{% endif -%}
{% if bp is defined and bp is not none -%}
{% if bp >= 90 -%}
| Best Practices | {{ "pass" | badge }} **{{ bp }}** |
{% elif bp >= 50 -%}
| Best Practices | {{ "warn" | badge }} **{{ bp }}** |
{% else -%}
| Best Practices | {{ "fail" | badge }} **{{ bp }}** |
{% endif -%}
{% endif -%}
{% if seo is defined and seo is not none -%}
{% if seo >= 90 -%}
| SEO | {{ "pass" | badge }} **{{ seo }}** |
{% elif seo >= 50 -%}
| SEO | {{ "warn" | badge }} **{{ seo }}** |
{% else -%}
| SEO | {{ "fail" | badge }} **{{ seo }}** |
{% endif -%}
{% endif %}

{% if lighthouse.audits | default([], true) -%}
<details>
<summary>Audit details</summary>

{% for a in lighthouse.audits -%}
{% if a.score | default(1, true) < 1.0 -%}
- {{ "warn" | badge }} **{{ a.title }}** — {{ a.description | default("", true) }}
{% endif -%}
{% endfor %}

</details>

{% endif -%}
{% endif -%}
{# ── Page-level previews ─────────────────────────────────────────── #}
{% if pages -%}
### Pages

{% for p in pages -%}
- {{ p.status | default("pass", true) | badge }} {% if p.url %}[{{ p.path }}]({{ p.url }}){% else %}`{{ p.path }}`{% endif %}{% if p.size %} ({{ p.size }}){% endif %}{% if p.notes %} — {{ p.notes }}{% endif %}

{% endfor %}
{% endif -%}
{# ── Footer ──────────────────────────────────────────────────────── #}
{% if logs_url -%}
---
[:page_facing_up: Build logs]({{ logs_url }})
{% endif -%}
