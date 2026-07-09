# Research: Declarative Shadow DOM / Custom-Element Output

**Status**: Research complete; implementation recommendation is conditional

**Decision date**: 2026-07-09

**Issue**: [#174](https://github.com/lbliii/kida/issues/174)

**Prerequisites**: [#160](https://github.com/lbliii/kida/issues/160) (open),
[component ecosystem saga #166](https://github.com/lbliii/kida/issues/166)

**Decision**: Declarative Shadow DOM is feasible as an opt-in export of a
*server-rendered component instance*, but it is not a semantics-preserving
general output target for every Kida `{% def %}`. Prototype a restricted,
out-of-tree exporter only after #160 defines the style artifact and ownership
boundary. Do not add a Kida runtime, public API, CLI flag, syntax, or render
surface from this research alone.

This document is research, not approval for a public contract. A custom-element
target would be a new render surface and remains a stop-and-ask change under the
root constitution.

## Executive answer

The browser can parse this server response without running JavaScript:

```html
<kida-card>
  <template shadowrootmode="open">
    <style>/* component CSS */</style>
    <article class="card">
      <h2>Settings</h2>
      <div class="card__actions"><slot name="actions"></slot></div>
      <div class="card__body"><slot></slot></div>
    </article>
  </template>
  <button slot="actions" type="submit">Save</button>
  <p>Preferences go here.</p>
</kida-card>
```

The HTML parser attaches the `<template>` contents as the parent's shadow root;
the remaining children are light-DOM content distributed into `<slot>`
positions. The custom element does not have to be registered for this static
rendering path. The host name must nevertheless be a valid custom-element name,
including a hyphen, and the original semantic element should remain inside the
shadow tree because an autonomous custom element has no implicit `article`,
`button`, or other built-in semantics.

This is a useful interop artifact for documentation, read-only cards, badges,
navigation, and other server-rendered islands. It is not a portable component
implementation in the React/Svelte sense. Without client JavaScript, attributes
cannot cause Kida expressions to rerun, props cannot update the shadow tree,
lifecycle callbacks and custom events do not exist, and behavior cannot hydrate.
Every prop-dependent instance must be rendered by Kida at build or request time.

## 1. Proposed `{% def %}` lowering

Given the existing Kida component:

```kida
{% def card(title: str) %}
<article class="card">
  <h2>{{ title }}</h2>
  <div class="card__actions">{% slot actions %}</div>
  <div class="card__body">{% slot %}</div>
</article>
{% end %}

{% call card("Settings") %}
  {% slot actions %}<button type="submit">Save</button>{% end %}
  <p>Preferences go here.</p>
{% end %}
```

a restricted exporter would reorganize one rendered call into four parts:

1. A statically validated host name, such as `kida-card`.
2. One direct child `<template shadowrootmode="open">` containing the
   prop-rendered internal skeleton.
3. Def-side slot placeholders lowered to `<slot>` elements in that skeleton.
4. Call-side content retained as light-DOM children of the host, with `slot="…"`
   added to each top-level element assigned to a named slot.

`open` should be the first target. It supports inspection, testing, and later
progressive enhancement through `host.shadowRoot`. `closed` does not provide a
security boundary and would make integration and diagnostics harder.

This is an *instance lowering*. The rendered `Settings` title is already in the
shadow tree. Emitting only a reusable definition is impossible without also
shipping an evaluator for Kida props and expressions, which would be a client
runtime and is explicitly out of scope.

### Eligibility contract for a first prototype

An initial prototype should reject, with a reason, any def that does not meet all
of these constraints:

- HTML output only; no terminal, Markdown, or CI-report interpretation.
- An explicit, package-qualified, valid custom-element name. Do not derive a
  globally collision-free name from `card` by convention alone.
- A declared host display contract (`block`, `inline`, or another reviewed
  choice); custom hosts do not inherit the box semantics of the def's root tag.
- Only unscoped `{% slot %}` placeholders, with each slot name occurring once in
  the rendered shadow tree.
- Named call-site slot content that is structurally assignable: top-level
  elements may receive `slot="name"`; bare text or mixed fragments require an
  explicit wrapper, and an exporter must not invent one silently.
- No direct `caller()` use, `{% yield %}` forwarding, scoped `let:` slots, manual
  slot assignment, or consumer-controlled shadow markup in version one.
- A style artifact that #160 has classified as safe for shadow-tree lowering.

Current `DefMetadata` exposes parameters, named slot names, default-slot
presence, and dependencies, but not slot occurrence counts, slot placement,
scoped-binding contracts, call-site root shape, host naming, or host display.
The preserved AST contains more of the needed structure, but it is internal.
Therefore the current public metadata API is insufficient for a third-party
exporter, and this research does not propose expanding it before #160 and the
component-contract work settle the shared schema.

## 2. Scoped styles: Shadow DOM versus `@scope`

`@scope` and Shadow DOM solve related but different problems:

| Property | `@scope` | Shadow DOM |
|---|---|---|
| Boundary | Selector/cascade scope in one tree | Separate shadow tree attached to one host |
| Outside selectors | Can still match scoped descendants unless otherwise constrained | Cannot normally select shadow internals |
| Component selectors | Limited to a selected subtree and optional lower bound | Naturally limited to that shadow tree |
| Consumer customization | Ordinary cascade/selectors | Host selectors, inherited properties/custom properties, `::part`, and shallow `::slotted` hooks |
| DOM encapsulation | None | Yes |
| Per-instance stylesheet | Not required | Inline DSD normally repeats the style payload per instance |

The #160 proposal's generated `@scope (.card) to (.card .card)` envelope should
*not* be copied mechanically into a shadow root. Shadow encapsulation already
prevents the component stylesheet from leaking into sibling trees. For the
least surprising first lowering, preserve the existing semantic root
(`<article class="card">`) inside the shadow tree and emit its validated inner
rules without the generated `@scope` envelope.

That simple rule has three important exceptions:

1. Rules intended for the host require an explicit `:host` lowering. A `.card`
   selector still selects the preserved inner article; it does not select
   `<kida-card>`.
2. Ordinary descendant selectors do not cross from the shadow tree into slotted
   light DOM. A rule like `.card__actions button` that works after Kida's current
   direct slot substitution will not style a light-DOM button. The closest
   shadow rule is `.card__actions ::slotted(button)`, and `::slotted` only
   exposes assigned elements, not arbitrary descendants inside them.
3. App-level overrides that currently reach BEM internals stop working. A
   component must deliberately expose customization through custom properties,
   `part`/`::part`, or documented slotted-content ownership.

Consequently #160 must classify at least four categories in its eventual style
contract: internal rules, host rules, slot-owned rules, and intentionally public
customization hooks. Class/selector agreement alone is not enough for a shadow
target. Asset deduplication and ordering also remain Furatena concerns under the
existing architecture boundary; Kida should not become a stylesheet bundler by
implication.

### Recommended two-lowering model after #160

Store one validated component-style representation, then lower it differently:

- Normal HTML: #160's accepted `@scope` envelope or external-CSS contract.
- DSD export: an encapsulated shadow stylesheet, with reviewed `:host`,
  `::slotted`, custom-property, and `part` mappings and no redundant outer
  `@scope` envelope.

Do not make DSD consume generated CSS text and try to reverse the envelope. Both
lowerings should consume the same analyzed representation so diagnostics can
name the original selector and source location.

## 3. Slot semantics: only a restricted subset is 1:1

The platform's simple case is close to Kida's:

| Kida def-side placeholder | Shadow-tree placeholder | Call-site payload |
|---|---|---|
| `{% slot %}` | `<slot></slot>` | Direct host text/elements without `slot` |
| `{% slot actions %}` | `<slot name="actions"></slot>` | Direct host elements with `slot="actions"` |

The general case is not 1:1:

| Kida behavior | Native-slot behavior | Result |
|---|---|---|
| Slot callback can receive `let:` values from def scope | Slots project nodes; they do not pass template values to consumer code | Scoped slots cannot be lowered without pre-rendering/wrapping or a client runtime |
| A slot placeholder can execute repeatedly in a loop | Named assignment selects the first matching slot in tree order | Repeated scoped/table-row slots are not equivalent |
| Kida renders call-site content at the placeholder | Native content remains a direct host child and is projected in the flat tree | DOM ownership, selectors, event paths, and form/ID relationships differ |
| Named content may be bare text or an arbitrary fragment | Only direct host children are considered; named text cannot carry a `slot` attribute | Some payloads require an author-supplied wrapper |
| Kida's scoped-slot body is fallback only when there is no caller at all; an existing caller with no matching named slot renders empty | `<slot>` children are fallback whenever no nodes are assigned to that slot | Fallback semantics differ |
| `{% yield %}` and nested calls forward callback output | Nested native slots forward nodes according to shadow-tree slot assignment | Requires separate composition analysis |

Kida's own implementation confirms these distinctions: `Slot` carries bindings
and a body, `SlotBlock` carries received parameters, and the compiler invokes a
Python callback with keyword arguments. Native slotting instead selects
slottable *direct children of the host*. See the current
[slot nodes](../src/kida/nodes/functions.py),
[callback lowering](../src/kida/compiler/statements/functions.py), and
[metadata collector](../src/kida/template/introspection.py). A future eligibility
diagnostic must inspect these semantics, not merely map slot names from
`DefMetadata`.

## 4. Does no-JavaScript SSR cover real interop use cases?

### Covered well

- Static sites and server responses that need encapsulated, fully rendered
  cards, badges, navigation, documentation examples, and other read-only UI.
- Progressive enhancement: meaningful native links, buttons, disclosure
  elements, and forms can exist in the rendered shadow content before an
  optional custom-element definition loads, subject to normal shadow-boundary
  semantics.
- Non-Python hosts that can include trusted Kida-rendered HTML during their
  server/build pipeline.
- CSS isolation for internal component markup, with explicit theme tokens and
  parts where consumer customization is required.

### Not covered without JavaScript or a Kida-serving boundary

- Arbitrary props supplied by React/HTML consumers after export. Attributes do
  not evaluate Kida expressions or update already-rendered shadow content.
- Client-side state, lifecycle, property reflection, custom events, validation,
  form-associated custom-element behavior, or hydration.
- Client-side insertion via ordinary `innerHTML`/`DOMParser`. Declarative shadow
  roots are parser-sensitive; the safe/unsafe HTML parsing APIs must be chosen
  deliberately, and trusted-markup handling becomes a consumer responsibility.
- A component fetched as an HTML string and dropped into an existing SPA with
  zero glue code.
- Exact DOM/CSS compatibility with current Kida direct slot substitution.

### Consumer matrix

| Consumer | Works with zero Kida client runtime? | Constraint |
|---|---|---|
| Plain server/static HTML | Yes | Kida-produced instance must be present in the parsed document response |
| React SSR/static output outside a hydrated subtree | Yes | Pass through trusted HTML and let the browser's document parser create the shadow root |
| React-rendered dashed host with light children | Partly | React supports custom tags, but Kida must already have supplied the DSD instance; JSX alone cannot evaluate Kida props |
| Hydrated React ownership of the same subtree | Unproven | Browser parsing removes the declarative template into a shadow root; reconciliation needs a framework-specific compatibility probe |
| Client-rendered React SPA consuming an HTML string | No, not automatically | Ordinary string insertion does not activate DSD; parsing/glue and a trust policy are required |
| Dynamic component with changing props/state | No | Requires behavior code or a server round trip |

The practical product claim should therefore be: **Kida can export encapsulated
standards-based HTML instances that non-Python applications can embed.** It
should not claim that Kida exports behavior-complete reusable custom elements or
that DSD alone makes a Kida component framework-agnostic.

## Recommended proof sequence

### Gate 0: wait for #160

Do not implement until #160 chooses syntax/ownership and defines the analyzed
style artifact. Revisit this document if #160 chooses external CSS plus a plugin
contract rather than Kida-owned style syntax.

### Gate 1: out-of-tree static prototype

Use three components with increasingly difficult shapes:

1. A no-slot badge.
2. A card with one default and one named, element-rooted slot.
3. A negative fixture using a repeated scoped slot, which the exporter must
   reject with an actionable reason.

Emit complete HTML documents and verify in current Chromium, Firefox, and Safari:

- shadow root exists during initial parse with JavaScript disabled;
- internal CSS does not leak and page CSS does not reach unexposed internals;
- named/default projection and absence behavior match the declared restricted
  contract;
- native semantics and keyboard behavior survive;
- a static React SSR pass-through works when excluded from hydration;
- ordinary client string insertion is rejected/documented rather than silently
  producing an inert `<template>`.

Record serialized output size for 1, 10, and 100 instances to quantify repeated
style cost before choosing inline styles, shadow-local links, or a Furatena-owned
asset strategy.

### Gate 2: stop and ask

If the prototype passes, request approval for the exact owner and contract. Any
Kida-owned implementation needs a parity matrix across compiler/analysis,
metadata/schema, diagnostics, HTML API/CLI, docs, examples, tests, benchmarks,
and changelog. Terminal, Markdown, and CI-report surfaces should explicitly
reject the target rather than acquire accidental custom-element semantics.

## Acceptance mapping

| Issue research deliverable | Result |
|---|---|
| `{% def %}` to DSD/custom-element compilation shape | Defined as a restricted per-instance lowering, with eligibility constraints |
| #160 scoped styles versus Shadow DOM/`@scope` | Defined conditionally; requires shared analyzed style representation and separate lowerings |
| Verify `{% slot %}` to `<slot>` semantics | Verified: simple slots are close; scoped, repeated, fallback, text-fragment, and forwarded slots are not equivalent |
| Determine whether no-JS SSR covers real interop | Yes for embedded static instances and progressive enhancement; no for reusable prop-driven or behavioral components |

The research questions are answered, but #174's stated sequencing condition is
not yet met because #160 remains open. Treat this as the decision artifact for
the later gate, not as authorization to close the implementation question or add
a public target today.

## Primary evidence

- [WHATWG HTML: `template` and declarative-shadow attributes](https://html.spec.whatwg.org/dev/scripting.html#the-template-element)
  defines `shadowrootmode`, named/manual slot assignment, and template behavior.
- [WHATWG HTML parsing algorithm](https://html.spec.whatwg.org/multipage/parsing.html)
  defines parser attachment of a declarative shadow root to the current host.
- [WHATWG DOM: shadow trees and `attachShadow`](https://dom.spec.whatwg.org/#shadow-trees)
  defines valid shadow hosts, open/closed roots, named assignment, and direct-host-child slotting.
- [WHATWG HTML: the `slot` element](https://html.spec.whatwg.org/dev/scripting.html#the-slot-element)
  defines named assignment and fallback to slot contents.
- [WHATWG HTML: custom elements](https://html.spec.whatwg.org/dev/custom-elements.html)
  defines valid custom-element names and the lack of implicit built-in semantics
  for autonomous custom elements.
- [CSS Cascading and Inheritance Level 6: `@scope`](https://www.w3.org/TR/css-cascade-6/#scoped-styles)
  distinguishes selector scopes from persistent shadow encapsulation.
- [CSS Shadow Module Level 1](https://drafts.csswg.org/css-shadow-1/)
  defines shadow selector/cascade behavior, `:host`, `::slotted`, and `::part`.
- [WHATWG HTML: dynamic markup insertion](https://html.spec.whatwg.org/multipage/dynamic-markup-insertion.html#html-parsing-methods)
  defines the parsing APIs that opt into declarative shadow-root processing and
  their trust/sanitization considerations.
- [React DOM: custom HTML elements](https://react.dev/reference/react-dom/components#custom-html-elements)
  documents React's handling of dashed custom tags and attribute/property values.
- [Web Platform Baseline: Declarative Shadow DOM](https://web-platform-dx.github.io/web-features-explorer/features/declarative-shadow-dom/)
  records cross-engine availability; the feature reached Baseline Newly
  available in February 2024.
- [WebKit: Declarative Shadow DOM](https://webkit.org/blog/13851/declarative-shadow-dom/)
  documents WebKit's server-rendering use case and the deliberate absence of DSD
  processing from ordinary `innerHTML` and `DOMParser` paths.

## Verification performed

- Inspected the current `Slot`, `SlotBlock`, compiler callback lowering, metadata
  collector, and scoped-slot regression tests.
- Ran an executable Kida probe covering simple named/default slots, repeated
  scoped-slot callbacks, metadata visibility, and the missing-named-slot case.
- Opened the linked WHATWG, DOM, CSSWG, React, Web Platform Baseline, and WebKit
  sources and checked each claim against the cited primary or vendor material.
- `make lint` passed.
- `make ty` passed.
- `git diff --check -- plan/research-declarative-shadow-dom.md` passed, along
  with Markdown fence and local-link target checks.

## Collateral and non-impact

- No runtime or public API change.
- No parser, AST, compiler, analyzer, formatter, schema, CLI, or render-surface change.
- No dependency, configuration, example, scaffold, or benchmark change.
- No tests added because this issue's deliverable is a standards/design decision;
  browser conformance probes belong to the gated prototype above.
- No changelog entry because no user-visible behavior shipped.
