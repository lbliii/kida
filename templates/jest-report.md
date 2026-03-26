## {{ "pass" | badge if numFailedTests == 0 else "fail" | badge }} Test Results

**{{ numTotalTests }}** tests ran in **{{ (testResults | sum(attribute="perfStats.runtime") / 1000) | round(2) }}s** — {{ numPassedTests }} passed, {{ numFailedTests }} failed, {{ numPendingTests }} pending

{% if numFailedTests > 0 -%}
### Failed Tests

{% for suite in testResults -%}
{% for tc in suite.testResults -%}
{% if tc.status == "failed" -%}
<details>
<summary>{{ "fail" | badge }} <code>{{ tc.ancestorTitles | join(" > ") }}{{ " > " if tc.ancestorTitles }}{{ tc.title }}</code> ({{ ((tc.duration or 0) / 1000) | round(2) }}s)</summary>

{% for msg in tc.failureMessages -%}
```
{{ msg }}
```
{% endfor -%}

</details>

{% endif -%}
{% endfor -%}
{% endfor -%}
{% endif -%}
{% if numPendingTests > 0 -%}
### Pending Tests

{% for suite in testResults -%}
{% for tc in suite.testResults -%}
{% if tc.status == "pending" -%}
- {{ "skip" | badge }} `{{ tc.ancestorTitles | join(" > ") }}{{ " > " if tc.ancestorTitles }}{{ tc.title }}`
{% endif -%}
{% endfor -%}
{% endfor -%}
{% endif -%}
