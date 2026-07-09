# Jinja Migration Transform Safety Audit

Status: complete research; no codemod approved

Tracking: [GitHub issue #251](https://github.com/lbliii/kida/issues/251), part of
[epic #168](https://github.com/lbliii/kida/issues/168)

Evidence date: 2026-07-09

## Decision

Kida should not add a general Jinja source rewriter yet. Current evidence supports
one narrowly guarded automatic source edit: changing a top-level, otherwise
Kida-compatible `{% macro %}...{% endmacro %}` definition to
`{% def %}...{% enddef %}`. Matching Jinja closers such as `{% endif %}` and
`{% endfor %}` already parse in Kida and should remain unchanged.

Everything else in this audit either needs a diagnostic before an edit, an
application-environment inventory, or manual redesign. In particular, Jinja
assignment scope depends on the enclosing block: an assignment inside `if`
persists, while an assignment inside `for` does not. A blanket `set` rewrite
would therefore change correct templates.

The executable probes are in
`tests/test_jinja_migration_transform_audit.py`. They use the existing development
Jinja dependency for differential evidence; they do not add a runtime or tooling
dependency.

## Safety Matrix

| Candidate | Classification | Current evidence and required guard |
|---|---|---|
| `endif`, `endfor`, `endblock`, and other Kida-owned explicit closers | **Already accepted / no-op** | The parser accepts matching explicit closers. Differential probes render the same nested `if`/`for` source in Jinja and Kida. Do not rewrite these during migration. |
| `macro` / `endmacro` to `def` / `enddef` | **Proven safe automatic edit, restricted subset** | The keyword-only probe preserves comments, trim markers, indentation, and output. Require a top-level definition, a signature and body that parse unchanged in Kida, no macro-object attributes, no unsupported caller behavior, and a known environment. Pair both keyword edits atomically. |
| `fill` / `endfill` to `slot` / `end` | **Advisory-only** | `fill` is not core Jinja syntax, so its source-engine semantics are unknown. Kida's parser hint points to `{% slot name %}` inside `{% call %}`, but that is only equivalent when the enclosing call and slot contract are known. |
| Nested `set` | **Advisory-only** | Jinja and Kida both keep loop-local assignment from escaping, but differ for `if`: the probe renders `2` in Jinja and `1` in Kida. A future analyzer must use block kind, binding origin, reads after the block, and control flow before suggesting `let` or `export`. |
| `super()` | **Unsupported / manual redesign** | Jinja renders parent block content. Kida uses flat block replacement; the same expression reaches runtime as undefined. Use explicit extension blocks or composition. There is no sound local replacement. |
| `namespace()` and attribute mutation | **Unsupported / manual redesign** | Jinja's mutable namespace survives loop scope. Kida rejects the attribute assignment target and has different `let`/`export` semantics. Rewrite the state flow, not the tokens. |
| Implicit Flask/framework context | **Manual environment review** | A macro using a Flask-style `request` global works only after the equivalent Kida global or render context is registered. Source inspection cannot prove framework injection. |
| Dynamic include/import target | **Dynamic / manual review** | Kida can render `{% include template_name %}`, and records `template_name` as a context dependency, but static acquisition cannot know the template graph. Preserve syntax only after loader and runtime-path review; never claim a complete migration. |
| Missing filters, tests, and globals | **Manual environment review** | Unknown filters and tests fail during Kida compilation; missing globals normally fail at render unless covered by declarations/context analysis. Names alone do not prove equivalent semantics, escaping, purity, or render-surface availability. |
| Unsupported macro behavior | **Unsupported / manual review** | Jinja macro-object attributes such as `.arguments` do not exist on Kida defs. Nested definitions, context-sensitive imports, caller arguments, recursion, and extension-provided behavior need individual proof rather than a keyword rewrite. |

Top-level Jinja `{% set %}` is also already accepted by Kida and has template
scope when no block scope exists. It should not be mechanically converted to
`let` merely for style.

## Current Diagnostic Contract

The parser already gives migration hints for `macro`, `endmacro`, `namespace`
as a block keyword, `fill`, and `endfill` in
`src/kida/parser/errors.py`. These are next-action suggestions, not proof that a
rewrite is safe.

`K-WARN-002` (`JINJA2_SET_SCOPING`) is emitted when a Kida `set` in an `if`
branch shadows a name already bound by `let` or `export`. It warns that Kida
creates a block-local shadow while Jinja's non-scoping `if` would update the
outer value, and it carries a suggestion to consider `export`; it has no safe
edit payload. Assignments enclosed by a `for` loop do not warn because both
engines keep those assignments loop-local.

The structured diagnostics service provides immutable spans, confidence, exact
safe edits, JSON/SARIF parity, and stale/overlap protection. Its current strict
closer edit changes Kida's unified `{% end %}` to a matching explicit closer.
That is the reverse of a Jinja migration and confirms that explicit closers
should be left alone. `apply_safe_edits()` also preserves CRLF and comments
outside the exact edited span.

Compiler `TemplateWarning` records, including `K-WARN-002`, are adapted at the
shared collection boundary used by `diagnose_source()`, `diagnose_directory()`,
and `kida check`. Text, diagnostics JSON v1, and SARIF therefore carry the same
code, path, line, suggestion, and proven confidence without an automatic edit.
This integration does not add a diagnostic code or change the warning default.

Two additional gaps matter for follow-up design:

- `super` is treated as a built-in name by declaration checking, so current type
  analysis does not flag the unsupported inheritance behavior before render.
- The parser's `namespace` hint covers a block keyword, while common Jinja uses
  the `namespace()` function plus attribute assignment; that form currently
  fails later as an invalid assignment target.

## Representative Evidence

The focused probe covers:

- a Jinja template whose explicit closers render unchanged in Kida;
- a restricted Flask-style macro rewrite with comments, whitespace, default and
  keyword arguments, and equal rendered output;
- positive loop-local and negative `if`-local assignment cases;
- the existing `K-WARN-002` code, suggestion, and absence of an edit payload;
- a dynamic include that renders in both engines while exposing only the target
  variable, not a static template identity;
- Jinja `super()` and namespace behavior that cannot be preserved locally;
- an implicit Flask `request` global that requires environment registration;
- a Django template using `load`, `url`, and `naturaltime`, which requires
  framework-specific mapping;
- compile-time rejection of missing filters/tests; and
- Jinja macro metadata that a Kida def does not expose.

Existing diagnostic proof remains authoritative in:

- `tests/test_kida_error_handling.py::TestJinja2TrapHints` for parser suggestions;
- `tests/test_kida_statements.py::TestMigrationWarnings` for `K-WARN-002`;
- `tests/test_check_diagnostic_formats.py::test_strict_safe_edit_has_json_sarif_and_text_parity`;
- `tests/test_public_diagnostics.py` for exact edit validation, multiple edits,
  CRLF preservation, and unsaved-source diagnostics; and
- `docs/audit/diagnostics-inventory.md` for producer and surface boundaries.

## Recommended Source Strategy

Use a conservative, dependency-free staged design if implementation is later
approved:

1. **Acquire explicit source only.** Read user-supplied files or loader results;
   preserve the original text, line endings, path, and source-engine label. Do
   not discover packages over the network or import application modules.
2. **Scan delimiters without claiming a Jinja AST.** Recognize data, comments,
   raw blocks, trim markers, strings, and `{% ... %}` / `{{ ... }}` envelopes.
   Record exact spans for statement heads and matching end tags. Unsupported or
   unbalanced constructs become manual findings.
3. **Emit candidates, not mutations.** A candidate is safe only when it changes
   exact keyword spans, has a complete paired edit, and is outside every manual
   category in the matrix.
4. **Validate with Kida's configured environment.** Parse the proposed source
   using the real loader, filters, tests, globals, and extensions; require a
   non-partial structured diagnostic result. Parsing proves Kida acceptance,
   not source-engine equivalence.
5. **Require application proof.** Use source-engine and Kida render-equivalence
   tests for declared safe transforms and preserve ambiguous findings as
   advisory. The Kida repository may continue using its development Jinja
   dependency for fixtures; a shipped base-runtime dependency is not justified.

Reusing Kida's lexer may help with positions after a separate audit, but the
migration scanner must not assume the Kida parser can consume Django tags,
Jinja extensions, or other source dialects. Adding a Jinja parser dependency,
CLI command, flag, schema, or public edit API remains stop-and-ask work.

## Follow-up Decomposition

1. **Block-sensitive assignment diagnostic:** detect a Jinja assignment whose
   value is read after an `if`-like block; distinguish loop-local behavior;
   advisory first, with positive and negative control-flow fixtures.
2. **Migration finding inventory:** add structured, location-bearing advisory
   findings for `super()`, namespace mutation, dynamic template targets,
   unsupported macro metadata/caller behavior, and missing environment
   vocabulary. Reuse the #193 model and expose no edits initially.
3. **Restricted macro edit RFC:** specify top-level/signature/body/context
   preconditions, atomic paired edits, formatting preservation, idempotence, and
   differential corpus requirements before producing an edit.
4. **Environment inventory research:** define how Flask, Django, and other
   adapters report filters, tests, globals, extensions, loaders, and implicit
   request context without importing untrusted application code.
5. **Published-doc collateral when behavior ships:** reconcile `CLAUDE.md`, the
   Jinja migration tutorial, the quick-reference page, framework tutorials, and
   the runnable migration example. In particular, stop instructing users to
   rewrite already accepted explicit closers.

## Non-Impact Notes

- No runtime, parser, compiler, analyzer, formatter, CLI, schema, or public API
  behavior changes.
- No dependency, render-surface, concurrency, cache, sandbox, or benchmark
  impact; benchmark and free-threaded proof are not applicable to a research
  artifact and focused semantic probes.
- Published docs remain unchanged until a diagnostic or edit ships, as required
  by #251. The internal audit records the current documentation mismatch for
  that later collateral change.
