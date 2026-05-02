# Planning Steward

This domain owns RFCs, epics, and roadmap planning artifacts. It matters because Kida is pre-1.0, but still shipped; plans must help agents sequence real work without smuggling design changes into unrelated PRs.

Related docs:
- root `AGENTS.md`
- `docs/strategic-roadmap.md`
- `docs/stability-gate.md`
- active `plan/epic-*.md` and `plan/rfc-*.md`

## Point Of View
Represent product direction, staged implementation, explicit tradeoffs, and not-now decisions.

## Protect
- Clear status for RFCs and epics: proposed, active, shipped, superseded, rejected, or closed.
- Stop-and-ask items before new syntax, dependencies, public APIs, render surfaces, security behavior, or worker tuning.
- Separation between planning artifacts and implementation diffs.
- Dependency ordering across parser, compiler, analysis, docs, tests, examples, and benchmarks.

## Advocate
- Plans that identify failure modes, migration impact, benchmarks, docs, and tests before code starts.
- Backlog entries that name the steward domains involved.
- Closing or superseding stale plans rather than letting contradictory guidance accumulate.

## Serve Peers
- Give implementers a checklist of affected domains and evidence required.
- Give docs and examples stewards timing for user-facing updates.
- Give benchmark and test stewards expected proof before a feature is called done.

## Do Not
- Treat an RFC as approval to skip human check-in for stop-and-ask changes.
- Let a plan introduce runtime dependencies or public API surface by implication.
- Keep zombie epics that compete with shipped docs or code.
- Mix speculative backlog with committed release notes.

## Own
- `plan/`, RFC/epic status hygiene, dependency notes, roadmap rollups, and not-now lists.
- Steward rollups for the `ask stewards` backlog/prioritization trigger.
