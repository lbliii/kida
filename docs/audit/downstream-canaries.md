# Downstream Canary Contract

Status: report-only Phase 1

Tracking: [GitHub issue #164](https://github.com/lbliii/kida/issues/164)

## Purpose

Kida's internal suite proves isolated compiler and runtime contracts. Downstream
canaries prove that a proposed Kida checkout still composes with real template
corpora and non-HTML consumers before high-risk work is merged. They are
necessary evidence, not a replacement for Kida's own tests, differential checks,
or benchmarks.

Canaries are standing regression signals; pilots are change-specific contract
proof. A canary run satisfies a required pilot only when the identified fixture
exercises the new or changed behavior and records the evidence defined by the
[downstream pilot policy](../downstream-pilot-policy.md). A broadly green suite
without a sensitive fixture is not pilot evidence.

## Phase 1 Matrix

| Consumer | Surface | Command | Contracts covered |
|---|---|---|---|
| `lbliii/chirp-ui` | HTML/components | `pytest tests/ -x -q` | defs, calls, named/scoped slots, provide/consume, regions, filters, metadata, packaged templates |
| `lbliii/milo-cli` | terminal/CLI | `pytest -q` | terminal autoescape, ANSI/width helpers, template-driven CLI output, packaged `.kida` components |
| `lbliii/chirp` | framework/multi-root pilot | `pytest tests/templating/test_kida_multi_root_pilot.py -q` | explicit framework/app roots, CLI validation, deterministic component discovery, ownership diagnostics, adapter rendering without `chirp-ui` |

The workflow runs on pull requests, pushes to `main`, a weekly schedule, and
manual dispatch. All jobs are report-only (`continue-on-error: true`) and use
only `contents: read`; they do not consume secrets, so public-fork pull requests
exercise the same public repositories safely.

Every downstream checkout uses an immutable commit SHA from the workflow
matrix. Pin refreshes are reviewed changes, so a consumer moving independently
cannot make an otherwise identical Kida candidate pass or fail.

## Source Override Proof

Each job checks out Kida and the downstream repository into separate paths,
creates the downstream's own development environment, and then installs the
current Kida checkout editable with `--no-deps`. All test commands use
`uv run --no-sync`, preventing a later dependency sync from silently restoring
the released `kida-templates` wheel.

Before tests run, `scripts/verify_downstream_override.py` imports Kida with the
downstream interpreter and requires `kida.__file__` to resolve below the checked
out `kida/src/kida` directory. A PyPI or unrelated workspace import fails with a
direct provenance error. The job summary records both repository commits and
the Python/GIL mode.

The Chirp multi-root pilot uses a minimal environment: Chirp and the candidate
Kida checkout are installed editable with `--no-deps`, then only pytest and its
asyncio plugin are added. The consumer fixture makes `chirp-ui` importability a
hard failure in pilot mode. This proves the explicit-root contract rather than
accidentally relying on Chirp's full development extras.

## Failure Protocol

1. Re-run the failed downstream job and inspect the raw pytest output.
2. Verify the source-override step passed; a wrong import is infrastructure
   failure, not downstream incompatibility.
3. Reproduce against Kida `main` and the downstream's recorded commit.
4. If only the proposed Kida change fails, fix Kida or explicitly coordinate an
   intentional downstream change before merging. Never refresh snapshots merely
   to make the canary green.
5. Record genuine downstream flakiness separately; report-only status must not
   become a reason to ignore a deterministic regression.

High-risk compiler issue #144 requires all Phase 1 canaries green before and
after each slice even while the GitHub check remains technically non-required.

## Promotion And Known Gaps

Promotion to a required check is a separate CI-policy decision. Consider it
only after at least ten consecutive relevant green runs spanning fourteen days,
with documented runtime and flake behavior.

### Promotion evidence snapshot: 2026-07-09

This historical snapshot predates the narrow Chirp multi-root pilot, so its
counts and tables cover only the original `chirp-ui` and Milo jobs.

The observation window currently available starts with the workflow's first PR
run at 2026-07-08 22:23 UTC and ends at 2026-07-09 20:57 UTC. GitHub reported
60 workflow runs in that window: 50 `success` and 10 `cancelled`, split evenly
between 30 pull-request and 30 `main` push events. There are no scheduled or
manual runs yet, so the evidence spans less than 23 hours rather than the
required fourteen days.

The table below samples ten completed runs across both triggers and the full
available time range. The Kida SHA is the commit actually checked out by the
job (`github.sha`), which is a merge commit for pull-request events. The
downstream SHA comes from the downstream checkout log. In every listed job the
source-override step succeeded, logged `verified Kida source override` below
the checked-out `kida/src/kida` tree, and the consumer test step succeeded.
Runtime is the complete GitHub job duration, including checkout and setup.

| Started (UTC) | Trigger | Exact run / tested Kida | `chirp-ui` SHA / runtime | `milo-cli` SHA / runtime | Classification |
|---|---|---|---|---|---|
| 2026-07-08 22:23 | PR | [28979900529](https://github.com/lbliii/kida/actions/runs/28979900529) / [`7a71b9e`](https://github.com/lbliii/kida/commit/7a71b9ede90e88f401838d455df594a650577c4e) | [`639c273`](https://github.com/lbliii/chirp-ui/commit/639c273ad13467182f40b55a32c67e19977af08c), 117s | [`218b8a6`](https://github.com/lbliii/milo-cli/commit/218b8a66a6b4d00c033f674d980154a66d9f80fd), 60s | green; no flake |
| 2026-07-08 22:25 | `main` | [28980022206](https://github.com/lbliii/kida/actions/runs/28980022206) / [`e0838c1`](https://github.com/lbliii/kida/commit/e0838c133aa1e5a346564a78a9385b83dbfe1c6f) | [`639c273`](https://github.com/lbliii/chirp-ui/commit/639c273ad13467182f40b55a32c67e19977af08c), 110s | [`218b8a6`](https://github.com/lbliii/milo-cli/commit/218b8a66a6b4d00c033f674d980154a66d9f80fd), 61s | green; no flake |
| 2026-07-09 01:41 | PR | [28988074955](https://github.com/lbliii/kida/actions/runs/28988074955) / [`ce16b42`](https://github.com/lbliii/kida/commit/ce16b42147ce449a2bfca391f6ae99adbe4e3d0a) | [`639c273`](https://github.com/lbliii/chirp-ui/commit/639c273ad13467182f40b55a32c67e19977af08c), 114s | [`218b8a6`](https://github.com/lbliii/milo-cli/commit/218b8a66a6b4d00c033f674d980154a66d9f80fd), 64s | green; no flake |
| 2026-07-09 01:43 | `main` | [28988161580](https://github.com/lbliii/kida/actions/runs/28988161580) / [`3d50398`](https://github.com/lbliii/kida/commit/3d50398bdf02f369c6f2f9ec781824b922a658ea) | [`639c273`](https://github.com/lbliii/chirp-ui/commit/639c273ad13467182f40b55a32c67e19977af08c), 112s | [`218b8a6`](https://github.com/lbliii/milo-cli/commit/218b8a66a6b4d00c033f674d980154a66d9f80fd), 56s | green; no flake |
| 2026-07-09 02:42 | PR | [28990294998](https://github.com/lbliii/kida/actions/runs/28990294998) / [`8ddce5a`](https://github.com/lbliii/kida/commit/8ddce5a405b92bb5e82bf237f6a8a340125b63b7) | [`639c273`](https://github.com/lbliii/chirp-ui/commit/639c273ad13467182f40b55a32c67e19977af08c), 112s | [`c85917c`](https://github.com/lbliii/milo-cli/commit/c85917c5266d4720cb8dcbd1b3b3306f055e962e), 64s | green; no flake |
| 2026-07-09 02:45 | `main` | [28990379359](https://github.com/lbliii/kida/actions/runs/28990379359) / [`97c9403`](https://github.com/lbliii/kida/commit/97c9403363f6c9b823131e52e3d8dfdd27916cd9) | [`639c273`](https://github.com/lbliii/chirp-ui/commit/639c273ad13467182f40b55a32c67e19977af08c), 113s | [`c85917c`](https://github.com/lbliii/milo-cli/commit/c85917c5266d4720cb8dcbd1b3b3306f055e962e), 61s | green; no flake |
| 2026-07-09 16:52 | PR | [29035016099](https://github.com/lbliii/kida/actions/runs/29035016099) / [`536cd8f`](https://github.com/lbliii/kida/commit/536cd8f955762ee84ff815699ce0b30b69e99f63) | [`4809419`](https://github.com/lbliii/chirp-ui/commit/48094197784f0665bc07bb49a03c72ca8fc411c0), 112s | [`c85917c`](https://github.com/lbliii/milo-cli/commit/c85917c5266d4720cb8dcbd1b3b3306f055e962e), 61s | green; no flake |
| 2026-07-09 16:55 | `main` | [29035155664](https://github.com/lbliii/kida/actions/runs/29035155664) / [`ae89283`](https://github.com/lbliii/kida/commit/ae89283d6fb0cfe64a4f38e0afba5eb403d7e5cc) | [`4809419`](https://github.com/lbliii/chirp-ui/commit/48094197784f0665bc07bb49a03c72ca8fc411c0), 109s | [`c85917c`](https://github.com/lbliii/milo-cli/commit/c85917c5266d4720cb8dcbd1b3b3306f055e962e), 66s | green; no flake |
| 2026-07-09 20:51 | PR | [29049352391](https://github.com/lbliii/kida/actions/runs/29049352391) / [`427bd9b`](https://github.com/lbliii/kida/commit/427bd9b7d3f2df7c432f3bede93ba5e7f5d736e2) | [`4809419`](https://github.com/lbliii/chirp-ui/commit/48094197784f0665bc07bb49a03c72ca8fc411c0), 116s | [`c85917c`](https://github.com/lbliii/milo-cli/commit/c85917c5266d4720cb8dcbd1b3b3306f055e962e), 64s | green; no flake |
| 2026-07-09 20:55 | `main` | [29049574094](https://github.com/lbliii/kida/actions/runs/29049574094) / [`e0cdd65`](https://github.com/lbliii/kida/commit/e0cdd6578b97522e397846b354de711c60282459) | [`4809419`](https://github.com/lbliii/chirp-ui/commit/48094197784f0665bc07bb49a03c72ca8fc411c0), 114s | [`c85917c`](https://github.com/lbliii/milo-cli/commit/c85917c5266d4720cb8dcbd1b3b3306f055e962e), 66s | green; no flake |

Across this sample, `chirp-ui` jobs ranged from 109s to 117s (median
112.5s), while `milo-cli` jobs ranged from 56s to 66s (median 62.5s). No
consumer failure or retry-derived flake appears in the selected job steps.

#### Non-green workflow outcomes

No workflow run concluded `failure`. All ten non-success outcomes were rapid
`main`-push cancellations caused by the workflow's `cancel-in-progress`
concurrency policy. They produced no valid consumer result and therefore do not
count as green evidence:

| Exact run / Kida head SHA | Observed jobs | Classification |
|---|---|---|
| [29046906464](https://github.com/lbliii/kida/actions/runs/29046906464) / [`628382f`](https://github.com/lbliii/kida/commit/628382f5b8775ee57b3713d3eeb4223f15f7ad5a) | both cancelled after about 4s | CI concurrency cancellation; no consumer result |
| [29046910183](https://github.com/lbliii/kida/actions/runs/29046910183) / [`a9d99a5`](https://github.com/lbliii/kida/commit/a9d99a530f44b4e5746174fc9d810cf91878cf34) | both cancelled after about 1s | CI concurrency cancellation; no consumer result |
| [29046913378](https://github.com/lbliii/kida/actions/runs/29046913378) / [`d697871`](https://github.com/lbliii/kida/commit/d697871f2eef895eebc56c313d39834def84e9f2) | both cancelled after about 4s | CI concurrency cancellation; no consumer result |
| [29046917171](https://github.com/lbliii/kida/actions/runs/29046917171) / [`38d736d`](https://github.com/lbliii/kida/commit/38d736d50f8e6b61fe9cb7561c989216b69e7cc9) | both cancelled after about 1s | CI concurrency cancellation; no consumer result |
| [29049536264](https://github.com/lbliii/kida/actions/runs/29049536264) / [`ce256a1`](https://github.com/lbliii/kida/commit/ce256a15d4c4a4fe78dda908005ecb1fcc6e2b9e) | both cancelled after about 3s | CI concurrency cancellation; no consumer result |
| [29049539780](https://github.com/lbliii/kida/actions/runs/29049539780) / [`d94b02c`](https://github.com/lbliii/kida/commit/d94b02ca0a43055788058c014e24dc50a69f0373) | both cancelled after about 33s | CI concurrency cancellation; no consumer result |
| [29049560534](https://github.com/lbliii/kida/actions/runs/29049560534) / [`bc51602`](https://github.com/lbliii/kida/commit/bc51602d0f99beb6a6f16e189be20543d76066a1) | no job started | CI concurrency cancellation; no consumer result |
| [29049563592](https://github.com/lbliii/kida/actions/runs/29049563592) / [`2d27feb`](https://github.com/lbliii/kida/commit/2d27feb44f836de118a5d56b3f6f064e0d105540) | no job started | CI concurrency cancellation; no consumer result |
| [29049567565](https://github.com/lbliii/kida/actions/runs/29049567565) / [`8552d91`](https://github.com/lbliii/kida/commit/8552d911a393e4b2d6e80ece4f3378460090e446) | no job started | CI concurrency cancellation; no consumer result |
| [29049570972](https://github.com/lbliii/kida/actions/runs/29049570972) / [`23763de`](https://github.com/lbliii/kida/commit/23763de8c36b539057a5f5e0a1db7856347ddb14) | no job started | CI concurrency cancellation; no consumer result |

#### Reverse canary and decision

The requested `chirp-ui` reverse-canary evidence is not available. As of this
snapshot, [lbliii/chirp-ui#372](https://github.com/lbliii/chirp-ui/issues/372)
remains open and the repository exposes no scheduled mirror-canary workflow or
run against Kida `main`.

- `lbliii/chirp-ui`: **extend observation**, and therefore remain report-only.
  The representative jobs are green and stable at 109–117s, but the evidence
  does not span fourteen days, has no scheduled run, and lacks the planned
  reverse canary.
- `lbliii/milo-cli`: **extend observation**, and therefore remain report-only.
  The representative jobs are green and stable at 56–66s, but the evidence
  does not span fourteen days and has no scheduled run.

Revisit promotion only after the ledger contains at least ten consecutive
relevant green runs spanning fourteen days, includes scheduled as well as PR
and `main` evidence, classifies every intervening failure or cancellation, and
includes the reverse `chirp-ui` result when #372 provides one. This audit makes
no required-check or workflow-policy change.

Deferred work:

- private Furatena checks follow the proposed
  [private downstream canary trust model](private-downstream-canary-trust-model.md)
  and still need explicit owner/authorization decisions before implementation;
- the narrow Chirp multi-root fixture does not replace a future broad framework
  canary; Purr still adds Markdown breadth after the first matrix is stable;
- reverse scheduled canaries belong in downstream repositories and require
  separate repository authorization;
- no single consumer covers source mapping, every render mode, sandbox policy,
  or performance, so Kida's internal gates remain authoritative.
