# Epic: Large-App Ergonomics

**Status**: Proposed  
**Created**: 2026-05-10  
**Trigger**: Elbysodic downstream analysis  
**Goal**: Make Kida materially better for large server-rendered applications that use
component libraries, route/page composition, partial updates, safe user markup, and
privacy-sensitive context.

This plan is not approval for new public API, CLI flags, schema versions, runtime
dependencies, syntax, sandbox semantics, or render-surface behavior. Those remain
stop-and-ask items under the root constitution.

## Downstream Signal

Elbysodic is a realistic large-app consumer through Chirp and Chirp-UI:

- 39 `page.html` templates and 44 `page.py` handlers.
- 11 shared `_components/*.html` templates.
- 64 Kida `{% def %}` components in page/layout/component templates.
- Chirp `Page(...)` returns pass broad route context into Kida templates.
- Safe user-authored forum markup is rendered through `kida.template.Markup`.
- HTMX, OOB regions, `page_block_name`, and `render_block` composition are first-class product paths.
- Tests assert many rendered privacy, shell, partial-update, and safe-markup invariants manually.

The opportunity is not more template syntax. The opportunity is app-scale static
confidence: Kida should expose generic facts that frameworks can compose into
route-aware checks without AST spelunking or Kida learning framework semantics.

## Consulted Stewards

- Static Analysis
- Template Runtime
- Environment and Framework Adapter
- Utility/Security
- Docs/Tests/Product
- Planning

## Accepted Direction

### 1. Typed Context Contracts

**Priority**: P1  
**Owner domains**: analysis, template, docs, tests  
**User promise**: A framework or app can compare what a template reads against
what a page handler provides before render.

Build on existing `depends_on()`, `required_context()`, `validate_context()`,
`def_metadata()`, and component-call validation. The first milestone should stay
route-agnostic in Kida core:

- expose required top-level and dotted context paths with stable source locations where available;
- distinguish globals, static context, imports, component params, loop locals, and slot locals;
- support handler/framework-provided context contracts through a generic checker input;
- emit machine-readable diagnostics with code, template, path, line/col where possible, and next action.

Kida core should not match routes, know Chirp `Page`, or inspect framework request objects.
Chirp can consume Kida facts and perform route/page validation.

**Proof**

- Analysis tests for top-level and dotted dependencies.
- Fixtures for missing, extra, optional, and nested context keys.
- Imported component, slot, include, global, and malformed-template coverage.
- CLI JSON snapshot if exposed through `kida check`.
- Docs in `site/content/docs/advanced/analysis.md`,
  `site/content/docs/usage/rendering-contexts.md`, and
  `site/content/docs/troubleshooting/undefined-variable.md`.

### 2. Component Catalog Contracts

**Priority**: P1  
**Owner domains**: analysis, template, docs, tests  
**User promise**: A design-system or app team can inventory Kida components,
their params, defaults, slots, source paths, dependencies, and call sites.

`kida components --json` and `def_metadata()` already point in this direction,
but large apps need the JSON shape and programmatic metadata to become deliberate
contracts.

Required catalog fields should be staged explicitly:

- template name and source location;
- exported def name and import alias where knowable;
- params, defaults, annotations, varargs/kwargs status;
- named/default slots and yielded slots;
- dependency paths read by the def body;
- call sites with unknown/missing/duplicate/extra parameter diagnostics.

**Proof**

- Stable JSON ordering tests.
- Multi-loader and alias fixtures.
- Long-signature component fixture.
- Typed params, defaults, named slots, scoped slots, and imported defs.
- CLI reference update and component-catalog tutorial.

### 3. Escape And Markup Audit

**Priority**: P1  
**Owner domains**: utility/security, analysis, template, docs, tests  
**User promise**: A large app can audit where output is escaped, where safe
markup enters, and where raw/trusted HTML crosses a boundary.

This must not weaken escaping behavior. Start with static and reportable facts:

- output sites and autoescape surface;
- `| safe` use, including `reason=` text where present;
- direct `Markup(...)` provenance where Kida can observe it;
- contexts that need special handling: HTML body, attributes, URL, CSS, JS/JSON,
  markdown, terminal;
- provenance-loss notes where a safe value is coerced to plain string;
- warning codes and suggestions, not vague advice.

Public provenance API shape is a stop-and-ask item. If provenance becomes runtime-visible,
it needs a focused design because `Markup` is currently a `str` subclass.

**Proof**

- Tests for `Markup`, normal strings, `| safe(reason=...)`, `tojson(attr=true)`,
  `xmlattr`, URL helpers, markdown, terminal, and `autoescape=False`.
- Render parity tests proving escaping output does not change accidentally.
- Hostile fixture strings and snapshots that do not leak raw secrets.
- Docs in escaping/security pages, with explicit sandbox caveat.

### 4. Render Packet Inspection

**Priority**: P2  
**Owner domains**: analysis, template, report templates, docs, tests  
**User promise**: Frameworks and CI can produce one structured packet describing
template context, components, fragments, OOB-like regions, safety findings, and
privacy findings.

Start as an internal/example packet, not a new public schema by implication.
Kida should define generic terms:

- template and block/region names;
- required context paths;
- component inventory summary;
- literal attributes and target-like IDs;
- surface mode and render entrypoint;
- diagnostics grouped by severity and action.

Chirp owns HTMX/OOB wrapping, target registration, and route semantics. Kida should
only expose blocks, regions, literal attributes, IDs, and metadata.

**Proof**

- One packet fixture rendered to markdown and terminal.
- Snapshot tests for empty states, dedupe markers, escaping, and action-first sections.
- Parity matrix before any public schema or GitHub Action contract changes.
- Extend review-packet examples only when behavior is shipped.

### 5. Privacy Linting

**Priority**: P2, with P1 safety posture  
**Owner domains**: utility/security, analysis, docs, tests  
**User promise**: Teams can catch likely private data exposure in templates and
report packets before publishing output.

Scope the first version narrowly:

- suspicious dependency paths such as password, token, secret, session, cookie,
  private, staff, email, api_key;
- secret-like literals in templates/report fixtures;
- `| safe` applied to sensitive-looking values;
- debug dumps of broad context values;
- dynamic includes where a policy requires static template names.

Any allowlist/suppression/config surface is stop-and-ask. Diagnostics must not
echo secrets.

**Proof**

- CLI tests with line/col diagnostics.
- Denylist fixture tests and false-positive fixtures.
- Tests that diagnostics redact secret-like values.
- Security, sandbox, CLI, and GitHub Action docs caveats if surfaced in reports.

## Runtime Contract Hardening

The runtime steward found a few enabling fixes that should come before or beside
the app-scale work:

- Mirror sync render metadata inheritance in async render scaffolds.
- Treat `render_with_blocks` as a first-class composition surface with tests for
  inherited layouts, unknown blocks, sibling blocks, OOB-like regions, Markup
  overrides, and block/page naming.
- Standardize missing-block failures on a Kida diagnostic/error code with template,
  requested block, available blocks, and close-match suggestion.
- Document `render_with_blocks` override values as trusted pre-rendered HTML.
- Fix render-block-scope docs drift around top-level defs/imports/lets/regions.

These are good first PRs because they reduce downstream ambiguity without adding
new public policy surfaces.

## Framework Boundary

Kida core should expose route-agnostic facts. Optional adapters can wire those
facts into framework lifecycle conventions. Chirp/Chirp-UI should own:

- route registry matching;
- `url_for` and route-name policy;
- Chirp `Page`, `Fragment`, OOB, and shell semantics;
- Chirp-UI loader defaults and component package composition;
- app-specific privacy policy.

Kida core may own:

- loader, alias, and template-key behavior;
- generic literal attribute extraction with source locations;
- metadata dataclasses and analysis APIs;
- render-mode parity and diagnostics;
- safe-string and escaping facts.

No Chirp, Chirp-UI, Flask, Django, Starlette, or routing package may become a
runtime dependency of Kida core.

## Parity Matrix

| Contract | API/CLI | Programmatic | Protocol | Schema/Types | Docs | Examples | Tests |
|---|---|---|---|---|---|---|---|
| Context contracts | `kida check` opt-in only after approval | metadata/check helper | none in core | diagnostic dataclasses | analysis/rendering context | large-app fixture | analysis + CLI JSON |
| Component catalog | `kida components --json` | `def_metadata()`/catalog API | none | stable catalog fields | CLI/components | design-system tree | metadata snapshots |
| Escape audit | check/report opt-in | analyzer findings | none | warning dataclasses | escaping/security | hostile strings | render-surface parity |
| Render packet | example first | packet builder only if approved | no public schema yet | internal fixture | agent/templates docs later | review packet | markdown/terminal snapshots |
| Privacy lint | opt-in only | analyzer findings | none | redacted diagnostics | security/sandbox/CLI | redacted fixture | false-positive/redaction |

## Dependencies And Sequencing

1. Runtime contract hardening.
2. Stable component catalog fields.
3. Typed context contract checker.
4. Literal attribute extraction API.
5. Escape audit findings.
6. Privacy lint findings.
7. Render packet example that combines the above.

Context contracts and component catalogs are the most adoption-relevant first
wave. Escape/privacy work is equally important, but it is safety-sensitive and
needs tighter wording and proof before public positioning.

## Not Now

- No new template syntax for context declarations unless a separate RFC proves
  existing metadata/checker inputs are insufficient.
- No Chirp-specific behavior in Kida core.
- No `Environment(validate_routes=...)`, `Environment(chirp_mode=...)`, or other
  framework-policy flags.
- No runtime safe-string provenance API until the public shape is reviewed.
- No public render packet schema until examples and snapshots stabilize.
- No async `render_with_blocks` until sync composition semantics are specified.
- No privacy-lint suppression/config surface without stop-and-ask approval.

## Open Questions

- Should context contracts be declared in Python, template comments, external JSON,
  or only provided by framework adapters?
- What catalog fields are stable enough for `kida components --json` consumers?
- Should `autoescape="html"` become a supported alias, or should docs use `True`
  exclusively?
- How much provenance can be static-only before users expect runtime guarantees?
- Should privacy lint ship in Kida, or should Kida expose facts and let frameworks
  define policy?

## Release Gate

Each implementation PR should include:

- affected steward notes;
- focused tests plus docs/examples collateral;
- machine-readable diagnostics with stable codes when adding findings;
- `make lint` and `make ty`;
- `make verify-stability` for public-contract, safety, render-surface, or
  concurrency-sensitive milestones.
