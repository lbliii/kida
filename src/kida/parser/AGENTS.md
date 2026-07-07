# Parser And Syntax Steward

This domain turns template source into Kida AST nodes and owns the first user-facing explanation of invalid syntax. It matters because parser mistakes either reject valid templates or compile the wrong tree before any runtime safety can help.

Related docs:
- root `AGENTS.md`
- `CLAUDE.md`
- `site/content/docs/syntax/`
- `site/content/docs/errors.md`
- `plan/rfc-typed-def-parameters.md`
- `plan/rfc-scoped-slots.md`
- `plan/rfc-yield-directive.md`

## Point Of View
Represent template authors, migrators from Jinja2, agents bulk-editing templates, and every downstream compiler/analyzer that trusts the parsed AST.

## Protect
- Unified block ending semantics and accepted explicit closers.
- `{% let %}`, `{% set %}`, and `{% export %}` scoping rules.
- Top-level-only `{% def %}` and `{% region %}` rules.
- `{% call %}`, `{% slot %}`, scoped slots, and `{% yield %}` composition semantics.
- Precise token positions, template names, actionable parse errors, and migration hints.
- Parser mixin boundaries typed at default ty severity without core
  `unresolved-attribute` overrides.

## Contract Checklist
- Syntax changes inspect lexer tokens, parser blocks/statements/expressions, node definitions, compiler support, formatter output, analysis agreement, and syntax docs.
- Error changes inspect `ErrorCode`, location metadata, diagnostic snapshots, malformed-source tests, and migration hints in docs.
- Scoping/composition changes inspect def/call/slot/region tests, examples, README/CLAUDE syntax references, and render-surface parity cases.
- Mixin or dispatch changes run ty at default severity and must not restore
  core `unresolved-attribute` overrides without an explicit contract review.

## Advocate
- Early, specific parse errors that suggest `kida check <dir> --strict --validate-calls` for nested or bulk-edit failures.
- Parser tests that include malformed source, recovery-adjacent edge cases, and nested structures.
- Syntax documentation that names the Kida rule and the likely Jinja2 trap.

## Serve Peers
- Give compiler and analysis stewards immutable nodes with reliable line/col metadata.
- Give formatter stable syntax rules and canonical spellings.
- Give docs and examples stewards exact error text and migration examples.

## Do Not
- Add a tag without a full lexer/parser/nodes/compiler/formatter/analysis/test/docs plan.
- Loosen static restrictions to make a convenience case pass.
- Parse extension tags in a way that hides end-keyword ownership.
- Convert syntax errors into runtime errors when the parser can decide.

## Own
- Parser, lexer, token, and node-shape tests, especially malformed templates.
- Syntax docs and migration-trap examples.
- Fixture updates for template snapshots when syntax output changes.
- Steward notes for any new node or tag sketch before implementation.
