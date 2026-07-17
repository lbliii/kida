# Encapsulation Advisor Contract

Status: accepted evidence contract for #284 under the component-authoring
contract in #281 and the advisor initiative in #282. `K-MOD-102` was
implemented by #287 and `K-MOD-103` by #283; the labeled corpus remains the
calibration source for both opt-in analyzers.

## Evidence Corpus

The durable corpus lives in `tests/fixtures/encapsulation_advisor/`. Its manifest hand-labels seven intentionally different shapes:

| Case | Label | Protected decision |
|---|---|---|
| `healthy-component` | keep component | A typed product concept with slots is already a useful boundary. |
| `healthy-layout` | keep inline | A large document shell with loops is not automatically under-encapsulated. |
| `message-row-candidate` | extract candidate | A substantial iterated product pattern with a narrow input boundary should remain detectable. |
| `monolithic-report` | keep inline | Branch-heavy, one-off tabular presentation is not automatically a component. |
| `pass-through-component` | flatten candidate | A wrapper that only mirrors another call is counterproductive encapsulation. |
| `repeated-actions-candidate` | extract candidate | Repeated accessible interaction structure is meaningful evidence. |
| `route-composition` | keep inline | A route arranging existing components is healthy page composition. |

The committed profiles are measurements, not golden advice produced by a hidden heuristic. A private test probe parses the templates with Kida's real lexer and parser, walks the real AST, and checks the measurements deterministically. The hand labels remain separately reviewable in `manifest.json`.

## Independent Shape Facts

The evidence records these policy-neutral facts independently:

- volume: AST node count and source line count;
- nesting: maximum AST depth;
- control flow: branch and loop counts;
- dynamic work: dynamic expression count and density in basis points (`dynamic expressions / nodes * 10,000`);
- repetition: repeated AST subtree-shape groups and repeated markup-shape groups;
- coupling: sorted conservative context dependencies from `DependencyWalker`;
- component structure: definition, call, and slot counts; and
- interaction: count of link, button, input, select, and textarea start tags.

No opaque aggregate score is part of the contract. In particular, no fact is a proxy for quality by itself. The healthy layout is longer in source than the message-row candidate while having fewer AST nodes, and the monolithic report has more branches than that candidate. Those contrasts are deliberate threshold traps.

Kida's AST treats static HTML as `Data`; it does not expose an HTML element tree. The fixture probe's regular-expression markup signature exists only to test whether markup repetition adds discriminating evidence. It is not an approved production parser, and an implementation must either use an established bounded structural source analysis or omit that fact.

## Advisory Diagnostic Contract

Profiles are facts and never diagnostics. Advice is a separate opt-in interpretation that must cite multiple contributing facts and the evidence that connects them to a candidate boundary. A node-count, depth, branch, loop, density, repetition, coupling, call, slot, or interaction threshold alone cannot create advice.

The extraction diagnostic is `K-MOD-102`; the pass-through diagnostic is
`K-MOD-103`. Both use the existing immutable `Diagnostic` model with:

- `DiagnosticSeverity.INFO`;
- `DiagnosticConfidence.CONSERVATIVE`;
- non-failing by default;
- contributing facts in stable metadata or notes;
- related locations for repeated sibling evidence; and
- no safe edit, because extracting or flattening a component requires naming and interface judgment.

The advisor must not imply that a component is reusable merely because it is large, nested, dynamic, or repeated. It should describe the observed shape, the candidate boundary, and why that boundary could improve typed props, named slots, or product-concept ownership.

## Candidate And Suppression Semantics

Extraction advice requires an exact contiguous candidate source span, including a reliable end location. Existing AST start locations are insufficient on their own. When the analyzer cannot prove the end span, it may report profile facts but must not emit candidate advice. Repetition advice attaches the primary location to the proposed boundary and uses related locations for the other matching shapes.

No source-level suppression syntax is introduced. There are no magic comments, template tags, or new configuration keys in this contract. An opt-in caller may filter findings by exact diagnostic code, normalized template path, and candidate span. Broad path or category suppression is outside this version and requires separate review.

## Output And Compatibility Decision

The implementation surface is opt-in and programmatic: `kida.analysis`
provides policy-neutral profiles and single-source extraction advice, while
`kida.inspection.advise_encapsulation_roots()` evaluates extraction and inverse
flattening advice across explicitly owned roots. Default `kida check` behavior
does not change under this contract.

If advice later reaches machine output, it reuses existing diagnostic JSON v1 and SARIF rendering. Contributing facts belong in diagnostic metadata and repeated evidence in related locations; this design requires no new schema. Human output must preserve the same code, severity, confidence, candidate location, related locations, and rationale.

Framework adapters may later provide generic component-role hints, such as known route shells or existing component calls. Advice must remain useful when no adapter is installed, and adapter absence cannot change parser semantics or create a runtime dependency.

Compatibility classification: this PR changes documentation and deterministic test evidence without changing normative runtime or public behavior. No downstream pilot: documentation or planning changed without changing normative behavior; replacement proof: deterministic labeled corpus and design-contract tests; affected contracts: none. A future implementation must make its own downstream-pilot decision.

## Calibration Gate

Before implementation advice can be enabled, calibration must demonstrate all of the following without a weighted score:

1. Protected negative fixtures produce zero extraction or flatten findings.
2. Each extraction-positive fixture produces exactly the hand-labeled candidate span and no extra candidate.
3. The pass-through fixture produces the inverse flatten advice and no extraction advice.
4. False positives and false negatives are reported independently by corpus category.
5. Every finding exposes the contributing facts so a reviewer can reproduce the decision.
6. Removing any one fact does not silently change an undocumented aggregate score; rule changes require fixture and decision-record review.

False positive means advice on a protected keep-inline or keep-component case, advice outside the hand-labeled span, or extraction advice on the flatten case. False negative means missing the exact extraction candidates or the flatten candidate. Candidate-boundary mismatch counts as both a false positive and a false negative.

## Signal Failure Modes

| Signal | Useful evidence | Known failure mode |
|---|---|---|
| Node/line volume | Review cost and boundary size | Healthy layouts and reports can be intentionally large. |
| Maximum depth | Deeply nested ownership | Layout shells and accessibility wrappers add legitimate depth. |
| Branches | Multiple presentation states | A local status cell can have many valid states. |
| Loops | Repeated runtime structure | Navigation, tables, and lists are not automatically components. |
| Dynamic density | Context-heavy regions | Small wrappers and route composition can be highly dynamic. |
| AST repetition | Repeated template-language structure | Similar control flow can represent unrelated product concepts. |
| Markup repetition | Repeated accessible interaction shapes | Static HTML is opaque `Data`; regex parsing is not production-safe. |
| Free-variable coupling | Candidate prop-surface size | Conservative dependency walking can include component names and broad roots. |
| Calls | Existing composition boundaries | Route templates legitimately coordinate several calls. |
| Slots | Extension points and ownership | A slot can be speculative or a component can be valid without one. |
| Interaction count | Behavioral/accessibility responsibility | A page-level form or navigation can remain a healthy single boundary. |

This contract changes neither a compiler nor a render hot path, so benchmark evidence is not applicable. It adds no shared state, cache, lock, `ContextVar`, or runtime execution, so free-threading analysis is not applicable. A future implementation must include bounded pathological fixtures and performance evidence before entering analysis or CLI paths.
