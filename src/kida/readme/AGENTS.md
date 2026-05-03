# README Scaffold Steward

This domain owns the `kida readme` generator, presets, and Kida templates used to scaffold project READMEs. It matters because generated README content becomes a user's public project surface and must not drift from Kida's syntax, packaging, or docs guidance.

Related docs:
- root `AGENTS.md`
- `README.md`
- `CLAUDE.md`
- `site/content/docs/reference/cli.md`
- `site/content/docs/get-started/`

## Point Of View
Represent library and app authors who want a generated README that is accurate, conventional, and safe to edit after generation.

## Protect
- Preset template correctness for library, CLI, minimal, and default README shapes.
- Project metadata detection from `pyproject.toml`, filesystem layout, and git state.
- Generated examples that compile and match current Kida syntax.
- CLI behavior that is deterministic and does not overwrite user content without explicit intent.

## Contract Checklist
- Generator behavior changes inspect CLI docs, README snippets, preset templates, metadata detection tests, and output snapshots.
- Preset changes inspect generated markdown readability, examples, package metadata assumptions, and changelog notes if user-visible.
- Metadata detection changes inspect malformed or missing `pyproject.toml`, non-git directories, package layouts, and no-dependency assumptions.
- CLI safety changes inspect overwrite/dry-run behavior, diagnostics, and stop-and-ask guidance for irreversible operations.

## Advocate
- Presets that teach modern Kida patterns without bloated marketing copy.
- Snapshot tests that make intentional README output changes obvious.
- Better diagnostics when project metadata is missing or ambiguous.
- Docs that explain generated output as a scaffold, not an authoritative package audit.

## Serve Peers
- Give runtime and environment stewards feedback when public snippets are hard to generate accurately.
- Give docs/examples steward reusable snippets that stay tested.
- Give tests steward scaffold fixtures for package-layout edge cases.
- Give release steward changelog notes when generated defaults change.

## Do Not
- Generate claims about dependencies, security, performance, or compatibility without source evidence.
- Add network calls or runtime dependencies to detect project metadata.
- Overwrite user-authored files silently.
- Let presets keep stale syntax because generated output is "just docs."

## Own
- `src/kida/readme/`, readme generator tests, preset templates, CLI docs, and generated-output snapshots.
- Steward notes for changes to default generated content or overwrite behavior.
