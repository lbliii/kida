# Private Downstream Canary Trust Model

Status: research recommendation; no workflow or permission change authorized

Tracking: [GitHub issue #246](https://github.com/lbliii/kida/issues/246)

## Decision Summary

Use a **downstream-owned workflow triggered through a narrow repository-dispatch
boundary** for any future private Furatena or other private-consumer canary.
Kida owns candidate classification and a non-sensitive public result; the
private repository owner owns authorization, private checkout, execution,
detailed logs, retention, and the final decision to expose its code to a Kida
candidate.

The first safe policy is deliberately main-only:

- external-fork pull requests: always skip;
- same-repository pull requests: skip until an immutable-SHA approval mechanism
  is separately chosen;
- pushes to `main` and schedules: run and fail visibly on any authorization,
  dispatch, provenance, setup, test, timeout, or reporting error;
- manual runs: originate from the private repository's default-branch workflow;
  `main` is the default candidate, and any non-main SHA needs a separate,
  SHA-bound authorization record.

"Report-only" means that the check is not a required branch-protection check.
It must not mean `continue-on-error`, a green result after a test failure, or a
silent skip on a trusted trigger.

This note does not authorize a secret, GitHub App, private checkout, permission
change, environment, required check, or workflow implementation.

## Security Boundary

Checking out a candidate is not the dangerous step by itself. Editable install,
build-backend hooks, imports, test discovery, pytest plugins, repository scripts,
and the tests execute candidate-controlled Python. Once that happens on a
runner that also contains private downstream source, malicious candidate code
can read and exfiltrate that source even if no long-lived secret is present.
GitHub's secure-use guidance likewise treats arbitrary runner code as able to
exfiltrate credentials or repository data and warns against persistent
self-hosted runners for untrusted code ([secure-use reference](https://docs.github.com/en/actions/reference/security/secure-use)).

Therefore:

1. Private source confidentiality depends on **candidate authorization**, not
   merely on token scoping.
2. Branch location is not authorization. A same-repository PR branch can still
   contain malicious code and can modify a `pull_request` workflow.
3. A review or label that applies to a PR number is insufficient after the head
   changes. Authorization must bind the exact 40-hex commit SHA.
4. No job may combine unreviewed Kida code with a private checkout, dispatch
   credential, result-reporting credential, environment secret, self-hosted
   runner, internal network, or writable shared cache.
5. `pull_request_target` may classify or request approval using the trusted base
   workflow, but it must never check out and execute the PR head. GitHub documents
   that combination as unsafe ([secure `pull_request_target` use](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target)).

## Trigger Threat And Permission Matrix

The current public canary workflow explicitly sets `contents: read`. The table
below describes the future private canary boundary, not a request to change that
workflow. GitHub withholds Actions secrets and downgrades `GITHUB_TOKEN` to read
for fork PRs; Dependabot PRs receive the same treatment. Same-repository PRs do
not receive that fork protection, so their workflow code must be treated as able
to request any repository secret that is not independently protected
([event rules](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows),
[fork settings](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository)).

| Trigger | Workflow/candidate provenance | Token and secret posture | Principal attack surface | Recommended result |
|---|---|---|---|---|
| Same-repository `pull_request` | PR merge ref and exact head SHA; candidate and PR workflow can be changed by the branch author | Current `GITHUB_TOKEN` can remain `contents: read`, but ordinary Actions secrets are normally available unless protected by an environment/policy | Workflow edits, build/install hooks, imports, tests, stale approval after a new push | `SKIP_UNAUTHORIZED_PR` by default. No private dispatch or checkout. A future opt-in path must approve the exact head SHA from trusted workflow code and re-authorize every new head. |
| External-fork `pull_request` (including Dependabot posture) | Untrusted fork head/merge ref | Read-only `GITHUB_TOKEN`; Actions secrets withheld; run may await maintainer approval | Arbitrary code, workflow changes, script injection, compute abuse; approval to use compute does not make code safe for private data | Always `SKIP_UNTRUSTED_FORK`. Never offer a private-canary approval button and never substitute `pull_request_target` execution. |
| `push` to protected `main` | Exact pushed SHA, verified reachable from Kida `main`; workflow is merged code | Trusted-trigger credential may be released only through a separately approved, main-restricted mechanism; Kida `GITHUB_TOKEN` alone cannot access another repository | Compromised maintainer/branch protection, malicious merged code, mutable action dependencies | Run. Any non-pass is a visible failure; missing credential/configuration is `FAIL_AUTHORIZATION`, not a skip. |
| `schedule` | GitHub uses the latest default-branch commit and default-branch workflow | Same as trusted `main`; schedules can be delayed or dropped | Dependency drift, private downstream drift, delayed/dropped schedule, stale baseline | Run against recorded Kida and downstream SHAs. Any started-run error fails. Absence of an expected run is an operational alert, not a synthetic pass. |
| `workflow_dispatch` | GitHub lets an operator select a workflow ref and inputs; triggering requires write access | Secrets are available according to the selected workflow/environment, so an arbitrary selected branch is a credential footgun | Modified workflow on selected ref, unvalidated SHA input, operator mistake, replay | Prefer dispatch from the private repo's default-branch workflow. Default candidate is Kida `main`. Non-default workflow ref or unauthorized candidate SHA is `FAIL_AUTHORIZATION`; never fall back to latest or a branch name. |

GitHub documents that schedules run only on the latest default-branch commit,
while `workflow_dispatch` can select a branch or tag and uses that ref's last
commit ([event provenance](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)).
It also requires write access for manual runs
([manual workflows](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)).
Those facts make a private-repository default-branch manual workflow safer than
placing a broadly usable manual secret in the public Kida repository.

## Exact Outcome Contract

Classification must be a secretless job that always runs and records one of
the following outcomes. A skipped private job must not be labeled "passed."

| Outcome | When | Check/summary behavior |
|---|---|---|
| `SKIP_UNTRUSTED_FORK` | Head repository identity differs from Kida's immutable repository ID, or actor is handled with fork restrictions | Neutral/skipped private job plus public summary: "private canary not authorized for external-fork code." No secret lookup, dispatch, private repository metadata, or approval prompt. |
| `SKIP_UNAUTHORIZED_PR` | Same-repository PR has no exact-SHA authorization facility under the first policy | Neutral/skipped private job plus the candidate SHA and bounded reason. Public canaries still run normally. |
| `PASS` | Authorization, request provenance, both immutable checkouts, source override, setup, sensitive fixture/suite, and result reporting all succeed | Successful non-required check with sanitized provenance. |
| `FAIL_AUTHORIZATION` | A trusted trigger lacks required credential/configuration, selects a non-default workflow ref, supplies an ineligible SHA, or fails receiver-side policy | Failed non-required check. Do not silently degrade to skip on `main`, schedule, or an explicitly requested manual run. |
| `FAIL_DISPATCH` | Request is rejected, times out before acceptance, or correlation cannot be established | Failed non-required check. HTTP `204` means only that `repository_dispatch` was accepted, not that the canary passed. |
| `FAIL_PROVENANCE` | Payload identity/SHA does not verify, checkout HEAD differs, source override imports another Kida, or result refers to another request | Failed check; stop before tests when possible. |
| `FAIL_SETUP` | Private checkout, dependency setup, interpreter creation, or install fails after provenance is accepted | Failed check, classified as infrastructure/setup rather than compatibility. |
| `FAIL_TEST` | The sensitive fixture or downstream suite fails against the authorized candidate | Failed check with a sanitized classification; detailed output remains private. Follow the existing downstream failure protocol. |
| `FAIL_TIMEOUT` | No terminal result is received within the agreed service window | Failed check. A later result may supersede only through an explicit rerun/attempt record. |
| `FAIL_REPORTING` | Private run completes but the public coarse result cannot be recorded or its correlation is invalid | Failed private result and an operational alert; never infer pass from the downstream test exit alone. |

Cancellation must be recorded as cancelled, not skipped or passed. A rerun keeps
the candidate SHA and correlation ID and increments `run_attempt`; it must not
silently pick up a newer Kida or downstream commit.

## Required Provenance

### Request envelope

Treat `repository_dispatch.client_payload` as untrusted input. GitHub runs a
`repository_dispatch` workflow from the receiver's default branch and exposes
the payload in the event context
([dispatch events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#repository_dispatch)).
The receiver must validate rather than trust these fields:

- schema version and a fixed event type;
- correlation ID/nonce;
- Kida immutable repository ID and expected `owner/name`;
- candidate full commit SHA (never a branch, tag, PR merge ref, or abbreviated
  SHA);
- trigger class: `main`, `schedule`, or `manual`;
- for PR research extensions only: PR number, base SHA, head repository ID, and
  exact head SHA;
- source workflow path/ref/SHA (`workflow_ref`/`workflow_sha`), run ID, run
  attempt, actor ID, and triggering actor ID;
- authorization class and an immutable authorization-record identifier.

Receiver-side validation must resolve the SHA in Kida through GitHub, verify
that `main`/schedule candidates are reachable from the protected default branch,
verify the authenticated dispatch sender/App installation, reject replays, and
fail closed on missing or contradictory fields. Do not interpolate payload data
directly into shell; GitHub calls event-derived fields potentially untrusted
([script-injection guidance](https://docs.github.com/en/actions/concepts/security/script-injections)).

### Execution record

The private record must contain:

- request correlation ID, authorization record, and received payload digest;
- exact Kida SHA and `git rev-parse HEAD` after checkout;
- exact downstream SHA and default-branch provenance;
- private workflow path, workflow SHA, run ID, run attempt, event, and actor;
- Python build, GIL mode, resolved `kida.__file__`, and source-override proof;
- exact command identifiers (the detailed commands may remain private), start
  and finish timestamps, and terminal outcome code;
- action/reusable-workflow commit SHAs and cache policy.

Use `persist-credentials: false`, immutable checkout refs, GitHub-hosted
ephemeral runners without private-network attachment, no writable cache shared
with more-trusted jobs, and no unrelated credentials. Pin third-party actions
and reusable workflows to full commit SHAs; GitHub identifies a full SHA as the
only immutable action release reference
([secure-use reference](https://docs.github.com/en/actions/reference/security/secure-use)).

### Public result

The Kida-visible result should disclose only:

- outcome code and `pass`/`fail`/`skip`/`cancelled`;
- Kida SHA, correlation ID, run attempt, and timestamps;
- a generic consumer identifier approved for public disclosure;
- downstream SHA only if the private owner approves disclosing it;
- a private details URL only when the viewer's authorization is enforced by
  GitHub.

Do not copy private repository paths, test names, diffs, dependency names, logs,
or secret-adjacent exception text into a public check. GitHub log redaction is
not a security boundary and is not guaranteed for transformed secrets
([secrets guidance](https://docs.github.com/en/actions/concepts/security/secrets)).

## Architecture Comparison

| Approach | Trust/permission shape | Strengths | Blocking risks | Verdict |
|---|---|---|---|---|
| Kida-owned workflow checks out private consumer | A credential and private source enter a runner controlled by a public-repo workflow; candidate Kida then executes there | Native Kida check/run context; direct use of existing source-override script | Same-repo PR workflow edits can target any repository-level secret; fork support is unsafe; Kida maintainers become custodians of private source and logs; a candidate can exfiltrate the checkout | Reject. Do not put private checkout or test execution in Kida's public-repository workflow. |
| Downstream-owned `repository_dispatch` | A narrow trusted dispatcher sends immutable public provenance; the private default-branch workflow owns checkout and execution | Private owner controls exposure, runner, logs, retention, downstream pin, and revocation; receiver can independently validate provenance; natural home for scheduled/manual reverse canaries | Cross-repository dispatch needs a separate credential; API acceptance is asynchronous; candidate code can still read private source, so authorization remains mandatory; public callback needs another narrow permission | Recommend as the ownership boundary, subject to explicit owner/App/reporting decisions. |
| Reusable workflow (`workflow_call`) | The called workflow uses the caller's event context, runner, token ceiling, and explicitly passed secrets | Good for sharing a pinned, reviewed harness inside a downstream-owned caller; permissions cannot be elevated by the called workflow | A public Kida caller cannot call a private reusable workflow; a private caller can call public only after its own trigger exists; it does not solve dispatch, authorization, or result correlation; untrusted called code executes in private caller context | Complement only. A private downstream may call a SHA-pinned public harness, but `workflow_call` is not the cross-repository trigger or security boundary. |

GitHub's accessibility matrix permits public callers to use only public reusable
workflows, while private callers can use public or authorized private workflows.
Called workflows inherit the caller event and cannot elevate the caller's
`GITHUB_TOKEN` permissions
([reusable workflow reference](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations)).

The normal Kida `GITHUB_TOKEN` is limited to Kida and cannot dispatch another
repository. GitHub's repository-dispatch endpoint accepts GitHub App,
fine-grained PAT, or App user tokens and currently requires receiver `Contents:
write`; classic PATs require `repo`
([repository-dispatch REST endpoint](https://docs.github.com/en/rest/repos/repos#create-a-repository-dispatch-event)).
If an integration is approved, prefer a GitHub App installed only on the named
repositories over a personal classic PAT: App installation tokens are
repository-scoped, permission-scoped, attributed to the App, and expire after
one hour
([App installation authentication](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation)).
The App private key or broker that mints those tokens remains a high-value
credential and requires a separate ownership decision.

## Recommended Ownership And Flow

1. **Kida maintainers** own the documented candidate policy and a secretless
   classifier. First policy: only protected `main` and schedules are automatic;
   same-repository and fork PRs receive explicit skip codes.
2. **Integration/App owner** owns the cross-repository credential, correlation,
   replay prevention, dispatch availability, callback, rotation, and audit log.
   Any Kida-side credential must be inaccessible to PR refs (for example, an
   environment restricted to the protected default branch) or live in an
   external App service. This is a future stop-and-ask choice, not approval here.
3. **Private repository owner** owns the default-branch receiver, independent
   SHA validation, authorization decision, private checkout, isolated runner,
   downstream commit pin, commands, detailed artifacts, retention, sanitization,
   and revocation. That owner can veto a candidate even if Kida classifies it as
   eligible.
4. **Kida's public result reporter** owns only the coarse outcome contract. A
   failed private run must remain red but non-required until a separate
   promotion decision. Detailed triage stays in the private repository.

The downstream receiver should create a pending coarse check before execution,
then publish exactly one correlated terminal result. If the owner does not
approve a callback credential with narrowly scoped checks/status permission,
the safe fallback is a private-only scheduled/manual result—not a misleading
green Kida check. `repository_dispatch` HTTP success alone is never sufficient.

## Unresolved Owner Decisions

Implementation must stop and ask for all of these:

1. Who is the accountable owner for Furatena (or another private consumer), and
   do they accept that authorized Kida code can read/exfiltrate the private
   checkout on a networked runner?
2. Is main-only evidence sufficient for Phase 1, or is pre-merge coverage for
   same-repository PRs required? If pre-merge is required, who may approve, and
   what system binds approval to the exact SHA and invalidates it on every push?
3. Is Kida `main` protected strongly enough to be the trust root (required
   review, workflow-file review, force-push policy, and administrator bypass),
   and who audits changes to that policy?
4. Will the dispatcher use an external GitHub App service, a main-restricted
   Kida environment, or another broker? Who owns the App, installations,
   private key, rotation, incident response, and the endpoint's `Contents:
   write` grant?
5. May the private repository publish its identity, commit SHA, workflow URL, or
   sanitized failure category on a public Kida commit? Who approves the
   redaction contract?
6. What is the terminal-result transport, timeout/SLA, retry/replay policy, and
   behavior when dispatch succeeds but callback fails?
7. Which downstream branch/SHA, sensitive fixture, Python/GIL modes, network
   policy, action pins, cache policy, and retention window does the private owner
   commit to maintain?
8. Who may run manual candidates, and how is execution forced to the private
   default-branch workflow rather than an operator-selected modified branch?
9. Whether and when the coarse check becomes required remains a separate
   branch-protection and flake-evidence decision.

## Scope And Closure

This research closes issue #246's design acceptance: it supplies the trigger
matrix, exact skip/fail/provenance contract, architecture comparison, ownership
recommendation, and named authorization/repository-owner decisions. It does not
make the private canary operational. Any implementation issue must cite the
selected answers above and separately authorize credentials, permissions,
private checkout, workflow changes, and reporting integration.
