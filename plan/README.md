# Planning Policy

GitHub is Kida's source of truth for planning. The repository keeps only this
policy, scoped instructions, and durable technical records needed to understand
or maintain shipped behavior.

## Hierarchy and execution

- A **saga** states a cross-cutting strategic thesis and links its epics.
- An **epic** owns one bounded outcome, its decisions, risks, evidence, and
  child tasks.
- A **task** is PR-sized work with explicit scope, proof, collateral, and
  downstream-pilot classification where applicable.
- Only one epic enters the active queue at a time. Its next child is labeled
  `status/ready`; deferred work is `status/not-now`; a named external or
  product gate is `status/blocked`.

## Plan end state

A task closes with its implementation or research result, verification,
collateral, and linked PR—or an explicit `not planned` decision. An epic closes
when its child tasks are resolved and its issue records the outcome, evidence,
remaining risks, and any follow-up. A saga closes or is superseded when its
strategic thesis is resolved.

Do not leave evolving backlogs, unchecked implementation lists, or active
roadmaps in the repository. Move a record into `docs/design/` or `docs/audit/`
only when it explains maintained behavior or durable evidence; otherwise retain
its history in Git and its decision trail in GitHub.

## Open Kida Work

Inspect the [GitHub issue backlog](https://github.com/lbliii/kida/issues) for
the active saga, `status/ready` task, deferred ideas, and named blockers. This
repository deliberately does not duplicate that queue.

Current work: [GitHub issues](https://github.com/lbliii/kida/issues).
