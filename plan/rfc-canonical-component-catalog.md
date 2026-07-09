# RFC: Canonical Component Catalog Contract

**Status**: Proposed internal contract; design-only v1 fixture

**Tracking**: [Kida #252](https://github.com/lbliii/kida/issues/252), part of
[Kida #173](https://github.com/lbliii/kida/issues/173)

**Consumers**: [#172](https://github.com/lbliii/kida/issues/172),
[#171](https://github.com/lbliii/kida/issues/171), and
[#157](https://github.com/lbliii/kida/issues/157)

**Evidence date**: 2026-07-09

## Decision

Kida should have one presentation-neutral component catalog service. The
existing `kida components --json`, future human/JSON/llms-style renderers, MCP
tools, LSP features, component diffing, and vendoring must project from that
same service rather than maintain parallel serializers.

This RFC defines the service's design contract as `kida.component-catalog`
version `1`. It does not publish a schema or Python type and does not change the
existing CLI. The deterministic fixture at
`tests/fixtures/component_catalog/v1-design.json` is explicitly marked
`design-only`; the private probe in
`tests/test_component_catalog_contract_design.py` proves it can be derived from
and projected back to today's `ComponentRow` without losing current fields.

Unknown evidence is a first-class result. The contract must never turn a
missing annotation, unavailable default expression, unresolved import, or
uninspected provider chain into an empty value that consumers might interpret
as proof.

## Current Contract And Gaps

`Template.def_metadata()` returns immutable `DefMetadata`; the
`kida components` collector projects it into `ComponentRow`.

| Current fact | Current source | v1 treatment | Known gap |
|---|---|---|---|
| Component name | `DefMetadata.name` / `ComponentRow.name` | Required identity field | No package/catalog namespace |
| Template path | `template_name` / `template` | POSIX `source.path` | No source digest or package version |
| Definition line | `lineno` | One-based `source.line` | Column/end span unavailable |
| Parameter order/name | `params` | Preserved declaration order | None for the names themselves |
| Required/default presence | `is_required`, `has_default` | Preserved | Default expression/value unavailable |
| Declared type text | `annotation` | Known declared fact or explicit `type-not-declared` | Not resolved or inferred; #194 owns deeper type proof |
| Variadic names | `vararg`, `kwarg` | Known value; `null` means known absence | Variadic element/value types unavailable |
| Named/default slots | `slots`, `has_default_slot` | Normalized records; default is named `default` | Scoped params, fallback body, requiredness declaration, and direct-slot versus `yield` origin are unavailable |
| Context dependencies | `depends_on` | Known conservative sorted fact | A context read is not automatically a `consume` fact |
| Template imports | `Template.dependencies()` only at template scope | Explicitly unknown per component | Dynamic targets and component ownership unresolved |
| Provide/consume | AST/runtime support exists | Explicitly unknown | Not exposed by `DefMetadata`; call arguments must not be guessed from `depends_on` |
| Description/examples | Comments are not in `DefMetadata` | Explicitly unknown until a documentation provider supplies evidence | No Kida doc-block syntax exists |
| Collection completeness | CLI skips templates that raise `TemplateSyntaxError` | Explicitly unknown for legacy rows | Canonical collection needs partial/diagnostic reporting before claiming completeness |

The current CLI scans `*.html` paths, renders text or an unversioned JSON list,
and silently skips syntax failures. Those are existing presentation behaviors,
not the canonical service contract.

## Design Contract v1

The top-level record contains:

- `contract`: exactly `kida.component-catalog`;
- `contract_version`: integer `1`;
- `catalog_identity`: a fact carrying a caller/package namespace when known;
- `completeness`: a fact proving complete/partial collection, or explaining why
  the legacy collector cannot know;
- `components`: canonical component records; and
- `fixture_status`: present only in design fixtures, never a proposed runtime
  field.

Each component contains:

- `component_id`: normalized `source.path + "#" + name` within the catalog
  namespace;
- `name` and `source` (`path`, one-based `line`, column fact);
- ordered `props` with requiredness, default evidence, declared type evidence,
  and inferred type evidence;
- known variadic names or known `null` absence;
- normalized slot records;
- context dependency evidence;
- per-component import, provide, and consume evidence;
- documentation evidence;
- an `extensions` object for package-owned facts.

The path-based ID is deterministic, not permanently stable across moves or
renames. #172 must treat a changed ID as removal/addition unless an explicit
rename mapping is supplied; neither names nor fuzzy source similarity can prove
identity.

### Fact states

Evidence-bearing values use one of these states:

- `known`: the `value` is proven by the named evidence source. `null` is valid
  only here and means known absence.
- `absent`: the contract proves the optional construct is not declared, such as
  a parameter with no default.
- `unknown`: no claim is made; `reason` is required and `evidence` may identify
  the boundary that exposed the gap.

An unknown value is not an empty list, `false`, `null`, or a compatibility
success. Consumers must propagate it as review-required or feature-unavailable.

### Slot policy

The default slot is represented as `name: "default", kind: "default"`; named
slots use their source name. Slots are optional under current Kida runtime
semantics, so v1 records `required: false`. The design fixture marks these facts
unknown until metadata grows:

- scoped parameters/bindings;
- fallback content;
- direct `{% slot %}` versus forwarded `{% yield %}` origin.

This is deliberate. The parser currently lowers `yield` to the same `Slot` node
shape used by introspection, so `DefMetadata.slots` cannot prove provenance.

### Documentation provider policy

v1 reserves `documentation.description` and `documentation.examples` as
evidence-bearing facts but standardizes no template syntax. A future provider
may supply text plus its provider name and source span. Kida core must return
unknown when no provider is configured.

chirp-ui's existing leading `{#- chirp-ui: ... -#}` block remains valid
package-owned prior art. Its current extractor returns one file-level block,
including embedded usage text, for every component in that file. A chirp-ui
adapter may report that as provider evidence; Kida must not silently promote it
to a universal per-component doc-block or split examples without an explicit
package rule. Standardizing doc syntax remains stop-and-ask work.

## Version And Unknown-Field Policy

- Readers must reject unsupported `contract_version` values rather than guess.
- Core fields cannot be removed, renamed, or reinterpreted without version `2`.
- Readers should ignore unrecognized object members so additive producers can
  be inspected, but compatibility hashes must use an explicitly versioned field
  selection rather than arbitrary JSON bytes.
- Package-specific facts belong under `extensions` with a stable namespace.
  They are excluded from Kida compatibility claims unless a consumer explicitly
  opts into that namespace.
- Producers must emit explicit unknown facts for required v1 concepts they
  cannot prove. Omitting a required concept is malformed; `null` never means
  unknown.

This policy is internal design guidance, not a published JSON schema guarantee.

## Determinism

A future serializer must produce identical bytes for identical evidence:

1. Normalize template paths to POSIX relative paths.
2. Sort components by `component_id`.
3. Preserve parameter declaration order and record `position`.
4. Emit the default slot first and named slots lexicographically.
5. Sort dependency and other set-like values lexicographically.
6. Sort JSON object keys, encode UTF-8 with LF, and end with one newline.
7. Do not include timestamps, absolute roots, process state, or runtime object
   representations.

The design probe reverses the input `ComponentRow` order and requires the same
catalog, checks canonical JSON bytes, and round-trips every existing CLI field.

## Presentation Separation

The service owns facts and evidence only. Presentations own formatting:

| Presentation | Projection rule |
|---|---|
| Existing `kida components` text | Render known name/signature/slots/dependencies in the current format; do not print design-only fields. |
| Existing `kida components --json` | Project the current `ComponentRow` keys exactly until a separately approved versioned CLI contract replaces it. |
| llms-style Markdown | Render known facts and visibly label unknown limitations; never hide incomplete collection. |
| MCP lookup | Return the same canonical component record through a separate adapter package; transport metadata is not catalog data. |
| LSP | Convert source/type/slot/documentation facts to hover, completion, and navigation capabilities only when evidence is sufficient. |
| Diff/CI | Classify known contract changes; any relevant unknown input is `review-required`. |

No renderer may reinterpret an empty legacy list as proof for a v1 unknown fact.

## Consumer Rules

### #172 component API diff

The diff may mechanically compare component identity, prop order/name,
requiredness, default presence, declared types, and slot names. It must not:

- claim type compatibility from a missing annotation or unavailable inference;
- classify scoped-slot compatibility until scoped params are known;
- infer a move/rename; or
- hash documentation, source lines, or package extensions as core API.

Unknown compatibility-relevant evidence yields `review-required`. The API hash
field and exact compatibility field set remain a separate stop-and-ask contract.

### #171 component vendoring

Vendoring may use component/source identity and known import/provide/consume
edges. It must refuse to claim a complete closure while any required edge is
unknown. CSS tokens, assets, maturity, categories, and package acquisition are
package/tooling extension concerns, not Kida core catalog facts.

### #157 LSP

The LSP may use the source path/line, declared prop text, requiredness, known
slot names, and provider-supplied documentation. Column navigation, scoped-slot
completion, inferred types, and descriptions must degrade explicitly while
their facts are unknown.

### #173 catalog and MCP

Human, JSON, Markdown, component lookup, and MCP tools must share the same
collection result. MCP packaging and transport belong outside the base Kida
runtime. A `kida catalog` alias/new command is not approved by this RFC.

## chirp-ui Prior-Art Reconciliation

GitHub evidence from chirp-ui's current
[`chirpui-manifest@5`](https://github.com/lbliii/chirp-ui/blob/main/src/chirp_ui/manifest.json),
[`_macro_introspect.py`](https://github.com/lbliii/chirp-ui/blob/main/src/chirp_ui/_macro_introspect.py),
[manifest builder](https://github.com/lbliii/chirp-ui/blob/main/src/chirp_ui/manifest.py),
and [signature-extraction decision](https://github.com/lbliii/chirp-ui/blob/main/docs/decisions/manifest-signature-extraction.md)
shows a mature hybrid catalog:

| chirp-ui fact | v1 relationship |
|---|---|
| `macro`, `template`, `lineno` | Direct mapping to name/source identity |
| `params` name/default/requiredness | Direct mapping; chirp-ui @5 omits Kida's annotation text |
| `slots_extracted` | Maps direct/default names, with `""` normalized to `default` |
| merged `slots`, `slots_yielded`, `slot_forwards`, `composes` | Package-owned composition overlay; do not collapse into proven direct slots |
| `provides`, `consumes` | Compatible concepts, currently derived by chirp-ui source inspection and nearest-def line attribution |
| `description` | Provider evidence from one leading file-level chirp-ui block; not universal Kida syntax |
| `block`, variants, appearances, tones, sizes, modifiers, elements, tokens, emits, category, maturity, role, authoring, requires | chirp-ui design-system/package extension fields |
| proposed manifest@6 type and API hash work in chirp-ui #370 | Consumers for Kida declared types and future versioned compatibility hashing |

Important gaps in chirp-ui @5 are evidence for, not objections to, v1:

- empty params/slots can mean known empty or extraction failure;
- types, default expressions, source columns, and scoped-slot parameters are
  absent;
- merged direct/hand-authored/forwarded facts need provenance;
- imports are not a per-component closure contract; and
- package API hashes are proposed, not yet a Kida compatibility contract.

Kida should let chirp-ui retire duplicate AST signature extraction while
preserving chirp-ui's hand-authored judgment and package-specific vocabulary.

## Contract Parity Matrix

| Contract | API/CLI | Programmatic | Protocol | Schema/Types | Docs | Examples | Tests |
|---|---|---|---|---|---|---|---|
| Internal v1 facts | No change | Design only | None | Design fixture, not public schema | This RFC | No public example | Deterministic private probe |
| Existing component inventory | Unchanged | `DefMetadata` unchanged | None | `ComponentRow` unchanged | Existing docs unchanged | Existing examples unchanged | Round-trip proof |
| Future presentations | Stop-and-ask | Stop-and-ask | Separate adapter | Versioned approval required | Ship together | Runnable consumer example | Shared golden fixture |

## Stop-And-Ask Follow-ups

1. Publish or alter a Python catalog model, JSON schema, CLI command/flag, or
   existing `components --json` contract.
2. Expand public `DefMetadata` with default expressions, source columns, scoped
   slots, import edges, provide/consume facts, or documentation.
3. Standardize any Kida doc-block or example syntax.
4. Define the #172 compatibility classifier, rename map, or API hash field set.
5. Create `kida-mcp` or add MCP/LSP/tooling dependencies.
6. Add package acquisition, token closure, assets, or write behavior for #171.

## Proof And Non-Impact

- The design fixture includes declared and undeclared types, present and absent
  defaults, known-null variadics, named/default scoped-slot gaps, conservative
  context dependencies, and every required unknown evidence family.
- The private adapter projects from current `ComponentRow`, reproduces the
  fixture independent of input order, and round-trips to the exact legacy row
  shape.
- No base dependency, import path, runtime state, cache, concurrency,
  parser/compiler/analyzer behavior, render surface, public API/CLI, schema, or
  published documentation changes.
- Benchmark, GIL-disabled, render-parity, changelog, site-doc, and example
  collateral are not applicable to this design-only artifact. They become
  required when an approved service or presentation ships.
