

## Semgrep Results

:x: **3** findings · 1 high · 1 medium


Policy: :warning: **warning**


Scanned 42 files. Found 3 issues: 1 high severity \(hardcoded secret\), 1 medium \(path traversal\), 1 low \(debug logging\). No critical findings.




### High (1)

- [ ] :x: **python.lang.security.audit.hardcoded\-secret** — `examples/contrib/flask\_app.py:12` · CWE-798

  A string that looks like an API key is assigned to a variable. Secrets should be loaded from environment variables or a secrets manager.

**Remediation:** Move the secret to an environment variable and load it with \`os.environ.get\('API\_KEY'\)\`.


<details>
<summary><strong>Medium</strong> (1)</summary>

- [ ] :warning: **python.lang.security.audit.path\-traversal** — `src/kida/cli.py:275`

  User input is passed to \`open\(\)\` without sanitization. An attacker could read arbitrary files by passing \`../../etc/passwd\` as the template path.

**Remediation:** Validate that the resolved path is within the expected directory using \`Path.resolve\(\)\` and checking it starts with the root.



</details>


<details>
<summary><strong>Low & Info</strong> (1)</summary>

- :information_source: **python.lang.security.audit.debug\-logging** — `src/kida/environment/core.py:340`: A \`print\(\)\` statement with potentially sensitive context data. Consider using the \`logging\` module with appropriate levels.


</details>


### By category

| Category | Count |
| --- | --- |
| exposure | 2 |
| injection | 1 |
