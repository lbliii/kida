# Planning Index

`plan/` preserves both active direction and historical design evidence. A
status such as **Implemented**, **Complete**, **Superseded**, **Rejected**, or
**Historical** means the document body is a record, not current operational
guidance. Commands and unchecked task lists inside those documents may describe
the toolchain that existed when the decision was made.

Current contributor commands and invariants live in `AGENTS.md`, `CLAUDE.md`,
`pyproject.toml`, `Makefile`, and the closest scoped `AGENTS.md`.

## Open Kida Work

GitHub sagas and epics are strategic rollups, not direct implementation
tickets. The executable queue is the set of open `task` issues labeled
`status/ready`. Move one epic into execution at a time by marking it
`status/active` and giving it a bounded ready child; preserve approved ideas
outside the current queue as `status/not-now`.

| Work | Status | Tracker |
|---|---|---|
| Pre-1.0 stability rituals | Active upkeep | `plan/epic-pre-1.0-stabilization.md` |
| Bounded execution queue | Active: cold-start boundaries, cache differential proof, and public warning documentation | [#273](https://github.com/lbliii/kida/issues/273), [#274](https://github.com/lbliii/kida/issues/274), [#275](https://github.com/lbliii/kida/issues/275) |
| Downstream canary promotion evidence | Blocked until the fourteen-day observation gate and reverse-canary evidence are available | [#244](https://github.com/lbliii/kida/issues/244) |
| Deferred product epics | Preserved as `status/not-now`; require a new grooming and stop-and-ask decision before implementation | [GitHub backlog](https://github.com/lbliii/kida/issues?q=is%3Aissue%20is%3Aopen%20label%3Astatus%2Fnot-now) |
| Downstream pilot evidence policy | Complete; adopted into root steward guidance | [#245](https://github.com/lbliii/kida/issues/245) |
| Kida/Milo marketplace and external dogfooding | Active; external publication and PR work remains | `plan/epic-kida-milo-integration.md` |
| Large-app ergonomics | Proposed; stop-and-ask items are not approved by the plan | `plan/epic-large-app-ergonomics.md` |
| Runtime-helper `Any` reduction | Complete; tracker closed | [#146](https://github.com/lbliii/kida/issues/146) |

## Historical Type-Checking Sequence

The type-checking plans record three distinct stages:

1. `rfc-type-checking-strategy.md` records the completed Pyright-to-mypy
   migration.
2. `rfc-type-suppression-reduction.md` and
   `rfc-mixin-protocol-typing.md` record the mypy-era cleanup and protocol
   design.
3. Kida later migrated to ty. `pyproject.toml` is authoritative for current
   overrides, and `make ty` is the current verification command.

Do not execute historical mypy/Pyright commands or reopen their unchecked
checklists without first reconciling them with the linked current issue.
