# Research: Kida Playground Feasibility

**Status**: Recommendation complete

**Decision date**: 2026-07-07

**Issue**: [#170](https://github.com/lbliii/kida/issues/170)

**Decision**: Build a Pyodide-first static playground; retain Chirp on Railway as
the fallback if the browser compatibility gate fails.

This document is research, not approval for a new public API, runtime dependency,
configuration surface, or deployment. Those remain stop-and-ask items under the
root constitution.

## Recommendation

The original risk behind the browser option has expired. Pyodide 314.0 shipped in
June 2026 with CPython 3.14.2, including the language version Kida requires. Kida
0.10.0 is a dependency-free, pure-Python `py3-none-any` wheel, and Pyodide supports
installing such wheels from PyPI with `micropip`. A browser implementation can run
Kida in a module Web Worker, keeping compilation and rendering off the UI thread.

Choose the browser path for the first public playground because it removes Python
installation without introducing a public execution service, account state, or
per-request infrastructure cost. It should accept Kida template source plus JSON
context only; it should not expose an arbitrary Python REPL.

| Criterion | Pyodide / static site | Chirp / Railway |
|---|---|---|
| Python 3.14 | Shipped in Pyodide 314.x | Supported by a Python 3.14 image; Railpack supports maintained Python versions |
| Kida packaging | Pure wheel, zero runtime dependencies | Normal `pip`/`uv` install |
| First useful version | 2–3 engineer-days after the compatibility gate | 1–2 days for a prototype; 4–7 days for a hardened public service |
| Operations | Static hosting and CDN caching | Builds, deploys, monitoring, abuse controls, and capacity |
| Untrusted work | Runs on the visitor's device | Runs beside service resources and needs real isolation/limits |
| Free-threading proof | No—Pyodide does not provide pthreads | Possible only with an explicitly provisioned 3.14t image |
| Collaboration/persistence | Follow-up feature | Natural future extension |

## Browser MVP

Use a pinned Pyodide 314.x release in a module Web Worker. At worker startup,
install a pinned Kida wheel with `micropip`, construct a `SandboxedEnvironment`,
and expose two message operations:

1. **Check** template source and return structured syntax/static diagnostics.
2. **Render** the same source with JSON-only context and return escaped HTML or
   a structured error.

The page needs three panes: template editor, JSON context editor, and output with
an adjacent diagnostics list. Ship a few curated examples covering typed defs,
slots, scoped state, and an intentional error. Keep rendering in an iframe or
escaped source view until the follow-up threat model decides what preview
capabilities the hosted origin may allow.

Terminate and recreate the worker when a run exceeds a short deadline. Do not
depend on `SharedArrayBuffer` interrupts in the first version because they require
cross-origin isolation headers. Pyodide cannot start Python threads, subprocesses,
or multiprocessing workers; this is acceptable for Kida's compile/check/render
playground but means the playground is not evidence for Kida's free-threading
claims.

`SandboxedEnvironment` remains defense-in-depth, not an isolation boundary. The
worker protects UI responsiveness and makes recovery cheap; it must not be
described as a security sandbox. Do not pass browser credentials, privileged
JavaScript objects, filesystem handles, or network helpers into Python context.

## Effort and gates

### Phase 0: compatibility gate — half a day

- Load pinned Pyodide 314.x in a module worker.
- Install `kida-templates==0.10.0` from its published wheel.
- Prove `SandboxedEnvironment.from_string()`, static diagnostics, rendering,
  typed defs/slots, and one Python 3.14 t-string example.
- Record cold and warm startup, wheel download, and render latency in Chromium,
  Firefox, and Safari.
- Prove a non-terminating or expensive template can be recovered by replacing the
  worker.

The audit environment could not complete this end-to-end probe because outbound
npm and CDN requests timed out. That transport failure is not compatibility
evidence, so the probe remains the first implementation gate rather than a claim
that Kida already runs unmodified in Pyodide.

### Phase 1: static MVP — 2–3 engineer-days

- Worker protocol, editors, diagnostics, output preview, curated examples, and
  accessible loading/error states.
- Pin Pyodide and Kida versions; prefer a repository-hosted Kida wheel for
  deterministic startup, while leaving the Pyodide runtime on its cacheable CDN.
- Add browser smoke tests for successful render, malformed source, invalid JSON,
  timeout recovery, and offline/error states.
- Publish as static files only after a CSP and iframe-preview review.

### Follow-up, not MVP

Add sharing, saved snippets, collaborative sessions, or server-side package
selection only after usage proves demand. Those features are where a small Chirp
service becomes useful. The existing chirp-ui component showcase demonstrates the
deployment recipe: a Python 3.14 Docker image, a `$PORT`-aware Chirp entrypoint,
`railway.json`, and post-deploy smoke tests. Reuse that shape rather than inventing
a second deployment convention.

## Evidence

- [Pyodide 314.0 release](https://blog.pyodide.org/posts/314-release/) — ships
  CPython 3.14.2 and aligns Pyodide versions with Python versions.
- [Pyodide deployment guide](https://pyodide.org/en/stable/usage/downloading-and-deploying.html)
  — versioned CDN distribution and static-hosting requirements.
- [Pyodide Web Worker guide](https://pyodide.org/en/stable/usage/webworker.html)
  — supported module-worker execution pattern.
- [Pyodide package loading](https://pyodide.org/en/stable/usage/loading-packages.html)
  and [compatibility FAQ](https://pyodide.org/en/stable/usage/faq.html) — pure-wheel
  installation and the no-pthreads/subprocess limitation.
- [Kida on PyPI](https://pypi.org/project/kida-templates/) — 0.10.0 publishes a
  `py3-none-any` wheel, requires Python 3.14+, and declares no runtime dependencies.
- [Railway Railpack](https://docs.railway.com/builds/railpack) and
  [Railpack Python support](https://railpack.com/languages/python/) — Python build,
  version-selection, and deployment support.
- [chirp-ui showcase deployment](https://github.com/lbliii/chirp-ui/tree/main/examples/component-showcase)
  and [Railway configuration](https://github.com/lbliii/chirp-ui/blob/main/railway.json)
  — the server-side fallback precedent.
