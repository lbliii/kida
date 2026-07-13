<!-- generated from .stewards/manifest.toml — edit the manifest, not this file -->

# Steward: github

Keep CI, release, benchmark, downstream-canary, report, and copied-template workflows least-privilege and evidence-producing.

Ordinary work: use this map directly with the root map and run only affected checks.
Do not open `.stewards/PROTOCOL.md` or `.stewards/manifest.toml` unless the task is an explicit review/audit or steward-network maintenance.

## Protects

| Invariant | Sev | Backing | Proof / anchor |
| --- | --- | --- | --- |
| CI retains one authoritative Ty lane, repository-wide Ruff, raw failure output, rendered reports, and supported setup inputs. | P1 | machine-backed | `uv run pytest tests/action tests/templates/test_github_report_contracts.py -q` (`action-suite`) |
| Report-only downstream canaries stay least-privilege, fork-safe, source-pinned, GIL-disabled, and multi-surface. | P1 | machine-backed | `uv run pytest tests/test_downstream_canary.py -q` (`downstream-canary`) |
| Release events, curated release bodies, Python publishing, Pages, artifacts, and floating action tags retain their fail-loud contract. | P0 | machine-backed | `uv run pytest tests/action tests/templates/test_github_report_contracts.py -q` (`action-suite`) |

## Guardrails

- The authoritative CI lanes keep raw failures visible alongside rendered reports.
- Scheduled free-threading stress preserves pinned seeds, GIL-disabled provenance, and debug-runtime semantics without overstating sanitizer coverage.
- Release, publish, package, Pages, marketplace, and floating action-tag workflows preserve least privilege, artifact provenance, and fail-loud preconditions.
- Downstream canaries are report-only and never substitute for change-specific pilot evidence.

## Edges

- runs → **action** (typed support code)
- gates → **benchmarks** (Linux baselines)
- copies → **templates** (report templates)

## Owns

- **code:** `.github/workflows/`, `.github/kida-templates/`
- **tests:** `tests/templates/test_github_report_contracts.py`, `tests/test_downstream_canary.py`
- **docs:** `docs/stability-gate.md`, `docs/downstream-pilot-policy.md`, `docs/marketplace-listing.md`
