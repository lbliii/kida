{% set deps_added = added | default([], true) -%}
{% set deps_removed = removed | default([], true) -%}
{% set deps_updated = updated | default([], true) -%}
{% set vulns = vulnerabilities | default([], true) -%}
{% set license_issues = license_issues | default([], true) -%}
{% set agent_name = agent | default("", true) -%}
{% set total_changes = deps_added | length + deps_removed | length + deps_updated | length -%}
{% set risk_level = risk | default("", true) -%}

{# ── Header ──────────────────────────────────────────────────────── #}
## Dependency Review

{% if vulns -%}
{{ "fail" | badge }} **{{ total_changes }}** dependency change{{ "s" if total_changes != 1 else "" }} · **{{ vulns | length }}** vulnerabilit{{ "ies" if vulns | length != 1 else "y" }}
{% elif license_issues -%}
{{ "warn" | badge }} **{{ total_changes }}** dependency change{{ "s" if total_changes != 1 else "" }} · **{{ license_issues | length }}** license concern{{ "s" if license_issues | length != 1 else "" }}
{% else -%}
{{ "pass" | badge }} **{{ total_changes }}** dependency change{{ "s" if total_changes != 1 else "" }}
{% endif %}

{% if agent_name -%}
<sub>Reviewed by {{ agent_name }}</sub>
{% endif %}

{# ── Vulnerabilities (always first) ──────────────────────────────── #}
{% if vulns -%}
> [!CAUTION]
> ### Vulnerabilities
>
{% for v in vulns -%}
> - **{{ v.severity | default("unknown", true) | upper }}** — `{{ v.package }}` {{ v.version | default("", true) }}: {{ v.title | default(v.id | default("", true), true) }}{% if v.cve %} ([{{ v.cve }}](https://nvd.nist.gov/vuln/detail/{{ v.cve }})){% endif %}
{% endfor %}

{% for v in vulns -%}
- [ ] {{ "fail" | badge }} **{{ v.package }}{% if v.version %}@{{ v.version }}{% endif %}** — {{ v.title | default("", true) }}
{% if v.description | default("", true) %}  {{ v.description }}{% endif %}

{% if v.fix_version | default("", true) %}  **Fix:** upgrade to `{{ v.fix_version }}`{% endif %}

{% if v.url | default("", true) %}  [:link: Advisory]({{ v.url }}){% endif %}

{% endfor -%}
{% endif -%}
{# ── License issues ──────────────────────────────────────────────── #}
{% if license_issues -%}
### License concerns

{% for l in license_issues -%}
- {{ "warn" | badge }} **{{ l.package }}** — {{ l.license | default("unknown", true) }}{% if l.reason %}: {{ l.reason }}{% endif %}

{% endfor %}
{% endif -%}
{# ── Added dependencies ──────────────────────────────────────────── #}
{% if deps_added -%}
### Added ({{ deps_added | length }})

| Package | Version | License | Size | Notes |
| --- | --- | --- | --- | --- |
{% for d in deps_added -%}
{% set lic = d.license | default("—", true) -%}
{% set risky_lic = lic in ["GPL-3.0", "AGPL-3.0", "SSPL", "unknown"] -%}
| `{{ d.name }}` | {{ d.version | default("—", true) }} | {% if risky_lic %}{{ "warn" | badge }} {% endif %}{{ lic }} | {{ d.size | default("—", true) }} | {{ d.notes | default("", true) }} |
{% endfor %}

{% endif -%}
{# ── Updated dependencies ────────────────────────────────────────── #}
{% if deps_updated -%}
### Updated ({{ deps_updated | length }})

| Package | From | To | Change |
| --- | --- | --- | --- |
{% for d in deps_updated -%}
{% set change_type = d.change_type | default("patch", true) -%}
{% if change_type == "major" -%}
| {{ "warn" | badge }} `{{ d.name }}` | {{ d.from }} | {{ d.to }} | **major** |
{% elif change_type == "minor" -%}
| {{ "info" | badge }} `{{ d.name }}` | {{ d.from }} | {{ d.to }} | minor |
{% else -%}
| `{{ d.name }}` | {{ d.from }} | {{ d.to }} | {{ change_type }} |
{% endif -%}
{% endfor %}

{% endif -%}
{# ── Removed dependencies ────────────────────────────────────────── #}
{% if deps_removed -%}
<details>
<summary><strong>Removed</strong> ({{ deps_removed | length }})</summary>

{% for d in deps_removed -%}
- `{{ d.name }}{% if d.version %}@{{ d.version }}{% endif %}`{% if d.reason %} — {{ d.reason }}{% endif %}

{% endfor %}

</details>

{% endif -%}
{# ── Supply chain summary ────────────────────────────────────────── #}
{% set total_transitive = 0 -%}
{% for d in deps_added -%}
{% set total_transitive = total_transitive + d.transitive_count | default(0, true) -%}
{% endfor -%}
{% if total_transitive > 0 or risk_level -%}
### Supply chain

{% if total_transitive > 0 -%}
New direct dependencies pull in **{{ total_transitive }}** transitive dependencies.
{% endif -%}
{% if risk_level -%}
Overall risk: {% if risk_level == "critical" or risk_level == "high" %}{{ "fail" | badge }}{% elif risk_level == "medium" %}{{ "warn" | badge }}{% else %}{{ "pass" | badge }}{% endif %} **{{ risk_level }}**
{% endif %}
{% endif -%}
