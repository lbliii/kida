<!-- generated from .stewards/manifest.toml — edit the manifest, not this file -->

# Steward: plan

Keep RFCs, epics, roadmap status, dependency order, tradeoffs, and not-now decisions useful without smuggling approval into implementation.

Ordinary work: use this map directly with the root map and run only affected checks.
Do not open `.stewards/PROTOCOL.md` or `.stewards/manifest.toml` unless the task is an explicit review/audit or steward-network maintenance.

## Protects

| Invariant | Sev | Backing | Proof / anchor |
| --- | --- | --- | --- |
| Active, proposed, shipped, superseded, rejected, and historical plans remain distinguishable from current commands and approvals. | P2 | manual | plan/README.md · `## Open Kida Work` |
| Roadmap priority and not-now tradeoffs remain explicit human product judgment. | P2 | none | — |

## Guardrails

- Plans name affected stewards, safety boundaries, proof, collateral, migration, and not-now scope.
- Proposed syntax, APIs, dependencies, surfaces, security behavior, and worker tuning remain stop-and-ask decisions.

## Edges

- resolved-into → **docs** (durable decisions)
- bounded-by → **root** (constitution and stop rules)

## Owns

- **code:** `plan/`
- **docs:** `plan/`, `docs/strategic-roadmap.md`

## Do Not

- Treat an RFC as approval for a stop-and-ask change.
- Leave active-looking zombie plans that contradict shipped code.
