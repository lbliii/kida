# Downstream Pilot Evidence Policy

Status: validated against historical changes; steward-guidance adoption awaits
explicit constitution review

Tracking: [GitHub issue #245](https://github.com/lbliii/kida/issues/245)

## Purpose

A downstream pilot is change-specific evidence that a proposed Kida contract
works at a real consumer boundary. It is narrower than a downstream canary: a
canary runs a standing consumer suite, while a pilot identifies the fixture
that exercises the new or changed behavior and proves that the candidate Kida
checkout supplied it.

This policy does not create a required CI check, authorize private-repository
access, or make every local change cross-repository. Kida's focused tests,
stability gate, safety tests, and benchmarks remain required when applicable.

## Decision Rule

A pilot is required when a change adds, removes, or changes a
downstream-observable component or runtime contract and a known consumer owns
the corresponding integration seam. This includes changed defaults and
behavior that is source-compatible but semantically different.

Use the smallest consumer set that covers the affected seams. One pilot may
cover several rows below when its fixture proves each contract. Use more than
one consumer only when no single fixture covers all affected surfaces.

| Change category | First-choice consumer | Minimum contract fixture | Rule |
|---|---|---|---|
| Component syntax or semantics: defs, calls, props, named/scoped slots, yield, provide/consume, regions, or component metadata | `chirp-ui`; add Chirp when framework rendering or propagation changes | A consumer-owned component imported, called, rendered, and introspected along the changed path | Pilot required for a new feature, changed semantics, or metadata contract |
| HTML/framework runtime: `Environment`, `Template`, loaders, full/fragment/block/stream rendering, adapters, or framework diagnostics | Chirp; use Bengal only for a current loader, inheritance, or docs-build contract it uniquely owns | A route, adapter, or page fixture exercising each affected render mode or resolution path | Pilot required for changed behavior, signatures, defaults, or lifecycle assumptions |
| Terminal APIs, autoescape, ANSI/width behavior, live output, or CLI-facing templates | Milo | A real command or packaged component asserting semantic output, width/ANSI behavior, and exit status where relevant | Pilot required |
| Markdown, report, AMP, schema, or data surfaces | Purr or another named stable consumer; otherwise the versioned Kida report corpus may support an exemption | A real payload rendered and parsed on every changed surface | Pilot required when a stable consumer exists; otherwise use the exact-fixture exemption below |
| Diagnostic codes, serialized shapes, CLI machine output, exit policy, or framework propagation | Chirp or the consumer that branches on the contract | A consumer assertion against codes/fields/status, not prose snapshots alone | Pilot required; human-readable wording alone normally uses local proof |
| Escaping, sandbox, trust boundaries, packaging, or optional adapters | The direct affected consumer, often Chirp, `chirp-ui`, or Milo | The real value flow or installed-artifact path plus Kida's adversarial or package proof | Pilot required when downstream behavior changes; never replaces stop-and-ask or safety proof |
| Internal refactors, tests, docs, type-only cleanup, or performance work with no observable contract change | None | Focused local tests, docs checks, type checks, or benchmarks | No pilot when the non-observable claim is explicit and proven locally |

A new component or runtime feature with a known consumer cannot use an in-repo
unit test as its only pilot. If no stable, accessible consumer exists, the
change is not downstream-validated; only an additive feature may use the
no-consumer exemption, with the gap and future consumer named explicitly.
Breaking or replacement behavior needs a real affected consumer or an explicit
maintainer exception before merge.

## Adequate Evidence

Pilot evidence is complete only when all of the following are recorded:

1. **Classification and selection** — name the changed contract, the chosen
   consumer, the fixture, and why that is the smallest representative seam.
2. **Pinned provenance** — record the Kida candidate commit, downstream commit,
   Python build, GIL mode when relevant, and the resolved `kida.__file__`.
   The import must resolve below the candidate checkout. The existing
   `scripts/verify_downstream_override.py` proof is sufficient.
3. **Contract fixture** — run the smallest consumer-owned test, command, route,
   component, or corpus slice that exercises the behavior. A full suite is
   useful compatibility breadth but is not a substitute for a sensitive
   fixture.
4. **Sensitivity** — show why the fixture can detect the change. For a new
   feature, it should fail or be unsupported on the Kida base and pass on the
   candidate. For a fix, reproduce the failure on the base and the success on
   the candidate. For a preserved contract, state the assertion whose output
   must remain unchanged.
5. **Result and coordination** — record the exact command and result. Link any
   coordinated consumer branch, issue, migration note, or compatibility range.
   State explicitly when no consumer change is needed.

A standing canary satisfies the pilot only if its pinned run records this
provenance and the identified fixture actually exercises the changed contract.
“The downstream suite was green” alone is not adequate pilot evidence.

## Failure And Coordinated-Change Protocol

1. Confirm source override before classifying a failure as compatibility.
2. Re-run the sensitive fixture against the candidate and Kida base using the
   same pinned downstream commit.
3. Classify the result as Kida regression, intentional contract change,
   downstream baseline failure, infrastructure failure, or flake. Preserve the
   raw assertion and commit provenance.
4. Fix a Kida regression before merge. Never refresh a snapshot merely to make
   a pilot green.
5. For an intentional coordinated change, link both sides, document migration
   and release ordering, and keep a compatible transition when feasible. Do not
   merge Kida into a state that deterministically breaks the pinned consumer
   without explicit maintainer approval.

Private repository access is outside this policy. Use a public consumer or a
versioned public fixture. Lack of private credentials is not evidence that a
known breaking consumer impact is safe.

## Acceptable `No Downstream Pilot` Records

Use this exact shape:

```text
No downstream pilot: <allowed reason>;
replacement proof: <test, fixture, docs check, or benchmark>;
affected contracts: <none, or the bounded contract>.
```

Allowed reasons are:

- no downstream-observable contract changed;
- a versioned Kida fixture is the exact shipped artifact boundary and no
  separate framework, packaging, or lifecycle seam changed;
- no stable accessible consumer exists for an additive feature, with a public
  replacement fixture, the evidence gap, and the intended future consumer
  named;
- documentation or planning changed without changing normative behavior.

“Small change,” “all Kida tests passed,” “the canary is report-only,” “the
consumer is inconvenient or private,” and “the bug was not reproduced” are not
allowed reasons. If a consumer is known to parse output or depend on behavior,
its contract is observable even when Kida considers that usage undesirable.

## Historical Calibration

The rule was applied retrospectively to five merged changes. These are policy
tests, not claims that historical PRs contained evidence that did not yet
exist.

| Historical change | Decision under this policy | Evidence the rule would request | Calibration result |
|---|---|---|---|
| [#61 scoped slots](https://github.com/lbliii/kida/pull/61) | Required: `chirp-ui` | A consumer table/list component passing `let:` values through imported named and default slots; base unsupported, candidate passes | Correct strong signal for new parser/compiler/runtime component semantics |
| [#107 strict-by-default](https://github.com/lbliii/kida/pull/107) | Required: Chirp plus Milo because both HTML/framework and terminal defaults were affected | Pinned full/fragment render fixtures and the terminal component that exposed the shadowed value; base/candidate migration comparison | Correct strong signal for a breaking default; in-repo failures showed that one surface was insufficient |
| [#111 relative and alias resolution](https://github.com/lbliii/kida/pull/111) | Required: `chirp-ui` for component imports and Chirp or Bengal for layout/include resolution | Consumer-owned `from` import plus include/extends fixtures, absolute-path parity, and traversal failure with source override | Correct signal for a loader protocol and multi-statement resolution change without demanding unrelated consumers |
| [#109 warning deduplication and hint wording](https://github.com/lbliii/kida/pull/109) | No pilot acceptable if recorded as bounded warning-frequency and prose behavior | Focused first/repeat/source/environment warning tests and hint assertions; stable exception types and codes | Avoids overreach for locally representable diagnostics while still escalating serialized/code changes |
| [#185 partial-evaluation phase extraction](https://github.com/lbliii/kida/pull/185) | No pilot: no observable contract intended | Existing semantic corpus, compatibility imports, focused optimizer tests, the stability gate, and benchmark evidence | Avoids turning an internal hot-path refactor into cross-repository work |

The calibration separates three genuinely consumer-sensitive changes from two
locally provable changes. It also shows why category alone is insufficient: a
diagnostic wording edit and a diagnostic schema edit do not carry the same
downstream risk.

## Steward Notes Integration — Deferred Constitution Change

This validated policy should be integrated only after explicit review of the
root constitution. The precise proposed addition to the root `AGENTS.md`
**Contract Checklist** is:

> New component/runtime features and downstream-observable contract changes
> classify their pilot requirement under `docs/downstream-pilot-policy.md`.
> Steward Notes record the selected consumer, fixture, provenance, sensitivity,
> result, and coordination evidence, or `No downstream pilot: <allowed reason>`
> with replacement proof.

No root or scoped `AGENTS.md` is changed by this policy-validation work. Scoped
stewards may later link the same policy where their checklist owns a mapped
consumer surface; that adoption is a separate reviewed change, not a condition
that silently expands every local steward consultation.
