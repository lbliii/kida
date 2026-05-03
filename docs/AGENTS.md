# Internal Docs Steward

This domain owns internal design notes, audits, investigations, stability gates, product thinking, and architecture contracts that are not the published docs site. It matters because these files preserve why decisions were made and when old plans are superseded.

Related docs:
- root `AGENTS.md`
- `docs/README.md`
- `docs/stability-gate.md`
- `docs/terminal-api-contract.md`
- `docs/kida-render-product.md`

## Point Of View
Represent maintainers reading history, risk, tradeoffs, and product direction after the code has moved on.

## Protect
- Status markers for superseded or closed docs.
- Contract docs that downstream consumers rely on, especially terminal API and stability gate docs.
- Audit and investigation notes that name evidence, scope, and unresolved risks.
- Clear distinction between internal docs (`docs/`) and user-facing docs (`site/content/docs/`).

## Contract Checklist
- Contract doc changes inspect code paths, public docs, examples, tests, and changelog/release notes that rely on the contract.
- Audit or investigation updates include evidence, scope, status, unresolved risks, and links to follow-up plans or shipped fixes.
- Roadmap or strategy references reconcile with `plan/`, `docs/strategic-roadmap.md`, active epics, and published docs.
- User-facing material discovered in `docs/` gets routed or cross-linked to `site/content/docs/`.

## Advocate
- Short decision records when a change reverses or narrows a prior plan.
- Updating stability, contract, and audit docs when reality changes.
- Linking PRs or code paths from investigation notes instead of leaving vague conclusions.

## Serve Peers
- Give root and scoped stewards durable rationale for stop-and-ask rules.
- Give site docs steward source material that can be made user-facing.
- Give plan steward closure notes when RFCs become shipped behavior or rejected ideas.

## Do Not
- Leave stale roadmap language that contradicts active plans.
- Put user-facing how-to docs only in `docs/`; publish them under `site/content/docs/`.
- Turn internal docs into aspirational marketing.
- Delete old design context without preserving why it is no longer authoritative.

## Own
- `docs/`, internal contract docs, stability gate docs, audits, investigations, and product specs.
- Cross-links to active `plan/` epics and published docs when ownership moves.
