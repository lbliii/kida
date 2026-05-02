
## Dependency Review

:x: **5** dependency changes · **1** vulnerability


<sub>Reviewed by Dependency Bot</sub>



> [!CAUTION]
> ### Vulnerabilities
>
> - **MEDIUM** — `pydantic` 2.11.0: ReDoS in email validator ([CVE-2026-12345](https://nvd.nist.gov/vuln/detail/CVE-2026-12345))


- [ ] :x: **pydantic@2.11.0** — ReDoS in email validator
  A specially crafted email string can cause exponential backtracking in the email validation regex.

  **Fix:** upgrade to `2.11.1`

  [:link: Advisory](https://github.com/advisories/GHSA-xxxx-yyyy-zzzz)


### License concerns

- :warning: **hypothetical-gpl-lib** — GPL-3.0: GPL-3.0 is copyleft — incompatible with MIT-licensed projects without relicensing



### Added (2)

| Package | Version | License | Size | Notes |
| --- | --- | --- | --- | --- |
| `pydantic` | 2.11.0 | MIT | 1.8 MB | Used for schema validation in AMP protocol |
| `orjson` | 3.10.15 | MIT OR Apache-2.0 | 320 kB | Fast JSON serialization for large PR data payloads |



### Updated (2)

| Package | From | To | Change |
| --- | --- | --- | --- |
| :information_source: `ruff` | 0.9.0 | 0.10.0 | minor |
| :warning: `pytest` | 8.3.0 | 9.0.0 | **major** |



<details>
<summary><strong>Removed</strong> (1)</summary>

- `deprecated-lib@1.2.3` — Replaced by stdlib equivalent in Python 3.14



</details>


### Supply chain

Overall risk: :warning: **medium**
