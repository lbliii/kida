# Adapter Advice Context Contract

Status: accepted public integration contract for #286 under the encapsulation
advisor initiative in #282. This contract extends the opt-in multi-root advice
entry point; it does not change template syntax, rendering, or default checks.

## Public Record And Entry Point

`kida.analysis.AdviceContext` is a frozen, slotted record with exactly two
fields: an exact public `SourceSpan` and a tuple of `(name, scalar)` facts.
Scalar values are `str`, `int`, `float`, `bool`, or `None`; float values must be
finite. Fact names are non-empty and unique. Construction sorts facts by name,
so equivalent inputs have one deterministic representation.

Adapters pass records through the keyword-only `context` parameter on
`kida.inspection.advise_encapsulation_roots()`. Context is invocation-local;
Kida does not register, cache, discover, or mutate adapter facts.

## Generic Fact Vocabulary

Kida recognizes only these framework-neutral names:

| Fact | Recognized values | Advice effect |
|---|---|---|
| `consumer_context` | `"iterated"`, `"repeated"` | Lets extraction analysis inspect inside the exact existing boundary. |
| `preserve_boundary` | `True` | Preserves an exact flattening candidate. |
| `response_boundary` | `True` | Preserves an exact response boundary. |
| `role` | any scalar | Adds explanatory metadata without assigning framework semantics. |
| `visibility` | `"package"`, `"public"` | Preserves an exact externally owned flattening candidate. |

Unknown fact names and unrecognized values are ignored. A context containing
only unknown facts must produce exactly the no-adapter report. This is the
forward-compatibility rule: adapters can retain private facts without Kida
learning their names or meanings.

## Span Matching And Boundary Semantics

Every context is scoped to one exact profile span and logical template path.
Flatten preservation requires an exact span match; containment is not enough.
Diagnostic enrichment applies when a recognized context span contains the
candidate span in the same logical template.

An iterated or repeated existing block or fragment becomes transparent only to
the nested extraction search. If it is also a preserved response boundary, the
outer boundary is never suggested for removal.

Only a nested candidate may be reported. The diagnostic records the recognized
adapter facts and explains that the response boundary remains intact.

## Determinism And Degraded Operation

Context records, recognized facts, matching, diagnostics, notes, and JSON
metadata are sorted deterministically. Input order does not affect the report.
No adapter and an adapter supplying only unknown facts are equivalent. Invalid
records fail at the public boundary rather than being partially interpreted.

All state is immutable or local to one advice call. The implementation adds no
shared mutable state, cache, singleton, lock, `ContextVar`, or environment
mutation, so concurrent free-threaded calls cannot share adapter context.

## Compatibility Boundaries

Kida does not import or name Chirp, HTMX, OOB, swap modes, routes, or response
classes. A framework adapter may translate its own block modifiers and response
knowledge into the generic fact vocabulary. Kida continues to assign no
semantics to arbitrary `BlockModifierMetadata` names.

The extension is programmatic and opt-in. It adds no CLI flag, config surface,
syntax, AST node, runtime dependency, diagnostic code, schema version, default
check, suppression form, render behavior, or GitHub Action behavior. Existing
diagnostic JSON and SARIF carry the context through ordinary metadata.

## Required Proof And Collateral

Kida proof must cover canonical construction, invalid input rejection, unknown
fact equivalence, input-order determinism, exact visibility preservation, and a
preserved response boundary exposing only a nested extraction candidate.
Scaling evidence must exercise a large context set on the existing multi-root
benchmark graph.

Downstream proof belongs in Chirp: a named swap or OOB response block must stay
the route/page response boundary while Kida reports the nested repeated-region
candidate after Chirp translates its own semantics to `AdviceContext`. The
same fixture without translated context must remain deterministic and safe.
