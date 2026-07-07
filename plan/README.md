# Planning Index

`plan/` preserves both active direction and historical design evidence. A
status such as **Implemented**, **Complete**, **Superseded**, **Rejected**, or
**Historical** means the document body is a record, not current operational
guidance. Commands and unchecked task lists inside those documents may describe
the toolchain that existed when the decision was made.

Current contributor commands and invariants live in `AGENTS.md`, `CLAUDE.md`,
`pyproject.toml`, `Makefile`, and the closest scoped `AGENTS.md`.

## Open Kida Work

| Work | Status | Tracker |
|---|---|---|
| Pre-1.0 stability rituals | Active upkeep | `plan/epic-pre-1.0-stabilization.md` |
| Kida/Milo marketplace and external dogfooding | Active; external publication and PR work remains | `plan/epic-kida-milo-integration.md` |
| Large-app ergonomics | Proposed; stop-and-ask items are not approved by the plan | `plan/epic-large-app-ergonomics.md` |
| Parser/compiler/analysis ty override debt | Active issue | [#142](https://github.com/lbliii/kida/issues/142) |
| Runtime-helper `Any` reduction | Active; baseline refreshed and first bounded slice implemented | [#146](https://github.com/lbliii/kida/issues/146) |

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
