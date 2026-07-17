# Encapsulation Loop Calibration

Status: accepted reproducible proof for #285 and completion evidence for the
encapsulation-advisor epic #282.

## Supported Consumer Loop

The replay in `examples/encapsulation_loop/` consumes only public
`advise_encapsulation_roots()`, `AdviceContext`, `diagnose_roots()`,
`inspect_components()`, template render, and named-block render behavior. It
uses no custom agent runtime, Kida-specific prompt, MCP/catalog package, hidden
score, browser, source history, or auto-edit protocol.

The same five steps apply to a human or coding agent: inspect structured advice,
choose extraction/inlining/preservation, validate calls and slots, compare
rendered surfaces, and re-run advice. Committed before/after source makes the
decision replayable without claiming that Kida made the architectural choice.

## Calibration Matrix

| Case | Expected before | Decision | Expected after | Boundary proof |
|---|---|---|---|---|
| Growing route | one `K-MOD-102` | Extract `message_row`. | none | Render parity and inferred `current_user`/`message` props. |
| Healthy large layout | none | Keep intact. | none | Protects against size, loop, and landmark false positives. |
| Pass-through micro-component | one `K-MOD-103` | Inline `save_button`. | none | Exact prop forwarding and render parity. |
| Framework response boundary | no advice without context; one nested `K-MOD-102` with context | Preserve `messages_oob`; extract its row. | none | Full-page and named-block parity; outer span is not the candidate. |
| Multiple explicit roots | one raw `K-MOD-103`; none with public visibility context | Preserve the public app wrapper. | none | Exact context suppression with both `app` and `framework` roots inspected. |

`calibration.json` records exact diagnostic codes, spans, confidence, selected
metadata, component inventories, call-validation results, and behavior parity.
The committed result has zero false positives, false negatives, validation
failures, and behavior-parity failures. Candidate-boundary mismatches count as
both a false positive and false negative through the exact expected payload.

## Cost Evidence

On macOS with free-threaded Python 3.14.2, five rounds over every before/after
case performed 50 end-to-end advice calls in 248.832 ms, or 4.977 ms per call.
The runnable `--measure` mode reproduces local timing while deliberately keeping
nondeterministic duration out of the committed JSON snapshot. A broad 500 ms
per-call regression guard protects pathological CI behavior without treating
one workstation measurement as a universal performance promise.

## Downstream Evidence

Kida #286 and Chirp PR
[lbliii/chirp#869](https://github.com/lbliii/chirp/pull/869) prove the response
case with Chirp's real adapter metadata and OOB registry. Pinned Kida downstream
canary [run 29607236065](https://github.com/lbliii/kida/actions/runs/29607236065)
installs Kida main over the released package and runs the exact Chirp pilot
fail-loud. The core replay stays framework-neutral and carries only generic
adapter facts.

## Compatibility And Concurrency

This proof adds no public API, CLI/config surface, schema, diagnostic code,
syntax, runtime dependency, default check, or auto-edit. It changes no compiler
or render hot path. Replay state is local, environments are per call, and all
adapter context remains immutable; no shared state, cache, lock, or `ContextVar`
is introduced.
