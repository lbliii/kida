## {{ "pass" | badge if summary.failed == 0 and summary.errors == 0 else "fail" | badge }} Type Check Results

**{{ summary.total }}** checks — {{ summary.passed }} passed, {{ summary.failed }} failed, {{ summary.errors }} errors

{% if summary.failed > 0 or summary.errors > 0 -%}
### Errors

{% for suite in testsuites -%}
{% for tc in suite.testcases -%}
{% if tc.status == "failed" or tc.status == "error" -%}
<details>
<summary>{{ tc.status | badge }} <code>{{ tc.name }}</code></summary>

{% if tc.message -%}
{{ tc.message }}
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
