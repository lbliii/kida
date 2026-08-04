# Kida Product Positioning

This brief keeps Kida's README, package metadata, documentation site, and
release copy centered on one product story. It is a messaging guide, not a
public API contract.

## Category

Kida is a **server-side component system for Python**.

"Template engine" is accurate but too broad to lead. "Component framework" can
sound like a client-side JavaScript framework. The preferred category names the
job, the execution model, and the ecosystem in one phrase.

## Audience

Lead for Python developers who:

- render web pages, fragments, static content, terminal interfaces, or reports;
- want reusable components without adding a JavaScript toolchain;
- have outgrown implicit macro contracts and runtime-only template errors;
- build frameworks or tools that need structured template metadata; or
- care about Python 3.14t and free-threaded execution.

## Problem

Templates often become application architecture without gaining architectural
contracts. Inputs remain implicit, composition becomes ad hoc, tooling cannot
reliably discover components, and bad calls appear only when a render reaches
the affected path.

## Promise

> Server-side components for Python—typed, composable, and checked before
> render.

The short supporting line is:

> Typed props, named slots, and static validation, with no npm, no build step,
> and no runtime dependencies.

## Message Pillars

### 1. Components with contracts

Typed props, defaults, named slots, scoped slots, and structured metadata turn a
macro convention into a component model.

**Proof:** component definitions and calls use checked syntax; introspection
exposes component parameters and slots.

### 2. Mistakes fail before render

Static call-site validation catches unknown parameters, missing required
parameters, and literal type mismatches in local checks or CI.

**Proof:** `kida check templates/ --strict --validate-calls` emits stable,
source-located diagnostics.

### 3. One model across render surfaces

The same component semantics serve HTML, Markdown, terminal output, CI reports,
streamed responses, and partial rendering.

**Proof:** the public APIs and bundled environments cover each advertised
surface; the GitHub Action turns common tool output into summaries and comments.

### 4. Pure Python all the way down

Kida needs no npm toolchain, build step, or runtime package dependency. Its
sharing contract is tested on free-threaded Python 3.14t.

**Proof:** `project.dependencies` is empty, and the required 3.14t CI lane runs
with the GIL disabled.

## Boundaries

- Kida is not a browser UI runtime or a replacement for client-side
  interactivity.
- Kida does not claim that type annotations make arbitrary template values fully
  statically typed.
- Free-threading claims cover Kida's documented sharing contract, not
  unsynchronized application objects or custom callables.
- Bengal is a supported integration, not Kida's product identity.
- The project is pre-1.0; stable design commitments should not be described as a
  frozen API.

## Message Hierarchy

Use this order on landing surfaces:

1. Category and outcome.
2. Typed props, named slots, and validation proof.
3. No npm, no build step, and zero runtime dependencies.
4. Multi-surface rendering and framework fit.
5. Free-threading as engineering proof, not the opening category.
6. Advanced syntax, compiler features, and ecosystem context.

## Preferred Terms

| Prefer | Avoid as the lead | Reason |
|---|---|---|
| server-side component system | modern template engine | Names the differentiated job |
| checked before render | compile-time safe | Precise without overstating the type system |
| pure Python | Python-native | Concrete and verifiable |
| no runtime dependencies | lightweight | Stronger proof |
| free-threading tested | no-GIL magic | Bounded, evidence-backed claim |
| render surfaces | every frontend | Includes non-web output accurately |

## Reusable Descriptions

**One sentence**

Kida is a pure-Python server-side component system with typed props, named
slots, and static validation—no npm, build step, or runtime dependencies.

**Short paragraph**

Kida gives Python applications a real component model: typed props, named and
scoped slots, static call-site validation, and structured metadata. Use one
pure-Python engine for HTML, Markdown, terminal output, and CI reports, including
free-threaded Python 3.14t.

## Hero Direction

The hero depicts Kida—the real cross-eyed snow-lynx Bengal cat—actively
assembling rosette-shaped and striped component pieces in a jungle workshop.
Her paws seat tiles and connectors while her ringed tail routes a finished
piece toward web, terminal, document, and checked-report artifacts. The scene
communicates composition and multi-surface output without turning Kida into a
literal product screenshot or a generic software mascot.

The visual belongs to the same personal-project family as Chirp, Bengal, and
Murlocs: tactile screen-print texture, limited ink colors, confident shapes, and
no corporate-dashboard gloss. Snow cream, jungle teal, lichen, coral, and
parchment give Kida a distinct identity within that system. Her Bengal rosettes
and stripes provide the repeating visual grammar for components and connections.

## Editorial Standard

Prefer short sentences, concrete nouns, and proof near the claim. Cut throat-
clearing, repeated feature inventories, and adjectives that the reader cannot
verify. The README should orient and persuade; the published docs should teach;
internal documents should preserve decisions and evidence.
