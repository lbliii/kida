# Steward Review Protocol

This file is on-demand governance guidance for explicit review, audit, and
steward-network maintenance. It is not part of ordinary implementation context.

## Review flow

1. Read the root map and only scoped maps for affected paths.
2. Identify invariants and exact focused checks before exploring broadly.
3. Trace syntax or rendering findings through only the affected semantic stages.
4. Record findings with evidence, user impact, required fix, proof, collateral,
   confidence, verification status, and downstream-pilot classification.
5. Preserve minority reports when stewards disagree; the implementing agent
   owns synthesis.
6. Human reviewers approve. Stewards advise.

## Finding format

```text
Steward:
Area:
Severity: P0/P1/P2/P3
Invariant:
Evidence: <source-file:line> [-> <doc-file:line>]
User Impact:
Required Fix:
Required Proof:
Collateral:
Downstream Pilot: <consumer evidence or exact no-pilot record>
Confidence:
Verification Status: machine-verified / manual-confirmation-needed / not-machine-verifiable
```

Two independent stewards flagging the same accepted issue promotes it to P0 for
synthesis. Accepted P0s require a bounded sibling-pattern sweep before closure.
Do not infer truth from convergence alone: spot-check the evidence.

Cross-surface changes include steward notes naming consulted maps, accepted and
deferred findings, proof run, collateral updated, unresolved dissent, and any
downstream consumer evidence required by `docs/downstream-pilot-policy.md`.

When an escaped bug shows that applicable guidance was missing, update the
smallest useful invariant, check, routing rule, regression test, or explicit
reason not to encode policy. When guidance repeatedly overreaches or produces
noise, narrow or prune it instead of accumulating more instructions.
