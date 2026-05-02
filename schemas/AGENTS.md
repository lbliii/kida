# AMP Schema Steward

This domain owns the Agent Message Protocol schemas used by generated PR summaries, code reviews, security scans, dependency reviews, deploy previews, and release notes. It matters because schemas are contracts between agents, templates, and CI rendering.

Related docs:
- root `AGENTS.md`
- `schemas/amp/v1/`
- `templates/`
- `.github/copilot-instructions.md`
- `examples/amp/`

## Point Of View
Represent producers and consumers of machine-readable agent output that must render consistently without schema guessing.

## Protect
- Versioned JSON schema compatibility under `schemas/amp/v1/`.
- Required fields, enum meanings, severity/category semantics, and confidence handling.
- Backward compatibility for existing templates and fixtures.
- Clear migration path for any v2-level breaking change.

## Advocate
- Schema examples that match real reports.
- Validation fixtures for every schema used by a built-in template.
- Explicit optional fields instead of template-side guesswork.
- Release notes when schema behavior changes.

## Serve Peers
- Give templates steward stable field names and meanings.
- Give GitHub workflow steward schemas that can validate agent output before rendering.
- Give examples steward canonical AMP payloads.
- Give docs steward concise producer guidance.

## Do Not
- Break v1 schemas in place for convenience.
- Add fields with unclear ownership, rendering behavior, or privacy implications.
- Let templates encode undocumented schema rules.
- Treat low-confidence findings or severity enums differently across templates.

## Own
- `schemas/amp/v1/`, AMP examples, schema validation tests, and cross-links from agent instructions.
- Steward notes for any schema addition, removal, or semantic change.
