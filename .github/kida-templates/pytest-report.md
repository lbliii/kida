## {{ "pass" | badge }} Test Results

**{{ summary.total }}** tests ran in **{{ summary.time }}s** — {{ summary.passed }} passed, {{ summary.failed }} failed, {{ summary.errors }} errors, {{ summary.skipped }} skipped

{% if summary.failed > 0 or summary.errors > 0 -%}
### Failed Tests

{% for suite in testsuites -%}
{% for tc in suite.testcases -%}
{% if tc.status == "failed" or tc.status == "error" -%}
<details>
<summary>{{ tc.status | badge }} <code>{{ tc.classname }}.{{ tc.name }}</code> ({{ tc.time }}s)</summary>

{% if tc.message -%}
**Message:** {{ tc.message }}
{% endif -%}
{% if tc.text -%}
```
{{ tc.text }}
```
{% endif -%}

</details>

{% endif -%}
{% endfor -%}
{% endfor -%}
{% endif -%}
{% if summary.skipped > 0 -%}
### Skipped Tests

{% for suite in testsuites -%}
{% for tc in suite.testcases -%}
{% if tc.status == "skipped" -%}
- {{ "skip" | badge }} `{{ tc.classname }}.{{ tc.name }}`{% if tc.message %} — {{ tc.message }}{% endif %}
{% endif -%}
{% endfor -%}
{% endfor -%}
{% endif -%}
