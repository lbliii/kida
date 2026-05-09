# Report Contract Hardening

**Status**: Partially implemented — contract inventory, AMP schema checks, readability tests, and docs have shipped; workflow audit remains
**Affects**: `templates/`, `tests/templates/`, `schemas/amp/v1/`, `.github/workflows/`, `.github/kida-templates/`, `src/kida/markdown/`, `src/kida/terminal/`, `site/content/docs/usage/github-action.md`
**Stewards**: report templates, GitHub workflow, AMP schemas, markdown surface, terminal surface, tests, internal docs, documentation site

## Problem

Kida's built-in report templates are now a public product surface: they render CI output, AMP agent messages, release notes, and GitHub Action comments. The current protection is snapshot-heavy. Snapshots catch broad output drift, but they do not clearly prove the contracts that the stewards care about: schema compatibility, fixture realism, safe markdown escaping, stable deduplication markers, action-first report structure, and GitHub workflow behavior that never hides raw failures.

The goal is to harden report contracts without adding public API, new config, new schema versions, or cosmetic template churn.

## Steward Signals

- Report templates: keep report sections, severity labels, deduplication markers, and fixture compatibility stable.
- GitHub workflow: dogfood formatted reports, but keep raw lint/type/test output visible and preserve least-privilege permissions.
- AMP schemas: do not let templates depend on undocumented fields or inconsistent severity/confidence semantics.
- Markdown surface: treat markdown escaping as surface behavior, especially tables, details blocks, code blocks, and PR comments.
- Terminal surface: preserve shared report semantics without leaking ANSI assumptions into markdown reports.
- Tests: add focused assertions for report behavior; snapshots are necessary but not sufficient.
- Docs: keep shipped behavior in user-facing docs and keep product/spec notes marked as plan, not release truth.

## Commit Plan

### 1. `test: inventory built-in report contracts`

Create a small contract inventory for every built-in report template. The inventory should map each template to its fixture, snapshot, render mode, and owning data contract when one exists. Add a test that fails when a built-in template lacks a fixture or snapshot, while allowing explicitly documented exceptions.

Evidence:
- `uv run pytest tests/templates`
- The failure message names the missing template, fixture, or snapshot.

Steward notes:
- Report template steward owns the mapping.
- Test steward owns whether the inventory is enforceable without becoming a brittle duplicate of the file tree.

### 2. `test: validate AMP report fixtures against schemas`

Add schema-validation coverage for AMP-backed fixtures. Keep this limited to existing `schemas/amp/v1/` behavior; do not add fields, loosen schemas, or introduce a v2 contract.

Evidence:
- `uv run pytest tests/templates`
- Each AMP fixture names the schema it validates against.

Steward notes:
- AMP schema steward decides whether existing fixtures or schemas are authoritative if a mismatch appears.
- Report template steward adjusts templates only after schema/fixture authority is settled.

### 3. `test: assert report readability invariants`

Add focused tests for behavior snapshots do not explain well: reports lead with actionable status, severity labels render consistently, empty states remain useful, and dedupe/comment markers stay stable where the GitHub Action relies on them.

Evidence:
- `uv run pytest tests/templates`
- Tests assert specific contract fragments rather than full rendered output.

Steward notes:
- GitHub workflow steward signs off on dedupe/comment marker expectations.
- Report template steward keeps assertions tied to user-visible structure, not cosmetic whitespace.

### 4. `test: cover markdown escaping in report-shaped output`

Add report-shaped markdown fixtures that include untrusted tool output: pipes in table cells, backticks in messages, HTML-looking strings, details markers, and multiline code snippets. Verify the markdown surface protects readability and escaping without treating markdown as plain text.

Evidence:
- `uv run pytest tests/markdown tests/templates`
- New tests fail before any escaping fix they justify.

Steward notes:
- Markdown steward owns escaping semantics.
- Report template steward owns whether a fixture belongs under markdown tests, template tests, or both.

### 5. `fix: repair report contract drift discovered by tests`

Apply only fixes proven by the previous contract tests. Prefer small template, fixture, schema-reference, or escaping corrections. Avoid visual redesign, renaming sections, or changing public schema semantics in the same commit.

Evidence:
- `uv run pytest tests/templates tests/markdown`
- Snapshot updates only when the tested contract intentionally changes.

Steward notes:
- If code and test disagree, stop and ask which is authoritative.
- If a schema change appears necessary, split that into a separate RFC or PR.

### 6. `chore: align GitHub report dogfooding with contracts`

Audit `.github/workflows/` and `.github/kida-templates/` against the hardened contracts. Keep raw command output visible, preserve workflow permissions, and document any intentional divergence from source `templates/`.

Evidence:
- Static workflow review plus the narrow tests affected by any template copy changes.
- No permission expansion unless separately justified.

Steward notes:
- GitHub workflow steward owns permissions, artifact names, and action behavior.
- Report template steward owns source-template parity expectations.

### 7. `docs: document report contract guarantees`

Update user-facing docs only for shipped behavior: supported built-in templates, expected data inputs, markdown mode caveats, PR-comment/step-summary behavior, and fixture-backed contribution guidance. Keep speculative product plans in `docs/`, not `site/content/docs/`.

Evidence:
- `make docs` if site structure or config changes.
- Otherwise, docs review plus links from relevant report docs.

Steward notes:
- Documentation site steward owns user-facing wording.
- Internal docs steward owns any product-plan status cleanup.

## Not Now

- No new report template config knobs.
- No new AMP schema version.
- No new GitHub Action inputs or posting behavior.
- No terminal report redesign.
- No broad template visual refresh.
- No runtime dependency for schema validation unless a steward check-in approves it.

## Done Criteria

- `make lint` and `make ty` remain clean.
- `uv run pytest tests/templates tests/markdown` passes.
- Public-contract or render-surface changes run `make verify-stability`.
- Steward Notes in the PR name consulted stewards, evidence, risks, and unresolved tradeoffs.
- Any snapshot update is paired with a focused assertion or a clear explanation of why the snapshot itself is the contract.
