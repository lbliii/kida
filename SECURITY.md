# Security Policy

Kida is a Python template engine designed to be safe by default when rendering
templates authored by trusted developers against untrusted *data*. This document
describes the guarantees we do and do not make, how to report a vulnerability,
and how to deploy Kida safely.

## Supported Versions

Kida follows Semantic Versioning. Security fixes are backported to the latest
minor release line. Pre-1.0 releases receive fixes on a best-effort basis on the
most recent minor line only.

| Version | Supported          |
| ------- | ------------------ |
| 0.6.x   | :white_check_mark: |
| < 0.6   | :x:                |

Upgrade to the latest 0.6.x release to receive security fixes.

## Threat Model

Kida is built for the common web/application case: **template authors are trusted;
template inputs (render context) are not.**

### In scope — Kida will actively defend against

- **XSS via render context.** Autoescape is on by default for HTML surfaces.
  User-supplied strings interpolated into templates are HTML-escaped; JSON
  serialization via `tojson` is context-aware for `<script>` and HTML-attribute
  contexts.
- **Path traversal via `FileSystemLoader`.** Template names containing `..` or
  absolute paths that would escape the loader's base directory are rejected.
- **Accidental unsafe output.** The `safe()` filter is the only way to emit
  pre-escaped markup; there is no `raw` filter. `Markup` follows the
  MarkupSafe `__html__` protocol.
- **Unbounded resource use during rendering from trusted templates** — when
  `SandboxedEnvironment` is used, `max_range` caps loop sizes and
  `max_output_size` caps total output length.

### Out of scope — Kida does NOT defend against

- **Fully untrusted template source executed in the default `Environment`.**
  The default environment allows attribute and call syntax that, combined with
  a rich render context, can reach arbitrary Python. If you render templates
  whose *source* is controlled by a third party, you must use
  `SandboxedEnvironment` and an explicit `SandboxPolicy` — and even then, see
  the next section on sandbox scope.
- **Denial of service from trusted templates.** A trusted author can still
  write a template that loops a long time, allocates a large string, or calls
  an expensive user-provided filter. Enforce wall-clock and memory limits at
  the process level.
- **Information disclosure through render context you provide.** If you pass
  a Django model, ORM session, or request object into the render context, a
  template can read its attributes. Pass only the fields you intend to expose.
- **Side channels.** Timing, cache, and error-message side channels are not
  in scope. The sandbox does not attempt to equalize execution time or
  normalize exception text.
- **Supply-chain integrity of Kida itself.** Verify release artifacts via
  PyPI signatures / `uv lock` hashes as you would any dependency.

### Trust boundaries, plainly

| Scenario                                          | Safe with default `Environment`? | Safe with `SandboxedEnvironment`?    |
| ------------------------------------------------- | :------------------------------: | :----------------------------------: |
| Trusted templates, trusted context                | Yes                              | Yes                                  |
| Trusted templates, untrusted context (web apps)   | Yes                              | Yes                                  |
| Untrusted templates (user-uploaded, LLM-authored) | **No — never**                   | Defense-in-depth only; see below     |

## Sandbox Scope

`kida.SandboxedEnvironment` is **defense-in-depth**, not an isolation boundary.
It reduces the blast radius of a template that attempts to reach out of the
intended context, but it does not replace OS-level isolation (containers,
`seccomp`, separate processes, WASM, etc.) for adversarial workloads.

What the sandbox does:

- Blocks a curated set of dunder and frame attributes
  (`__class__`, `__mro__`, `__globals__`, `__code__`, `f_locals`, etc.) that
  are the classic pivots for server-side template injection.
- Blocks access to `type`, function, and code objects by default.
- Blocks mutating collection methods (`append`, `pop`, `clear`, …) unless
  `allow_mutating_methods=True`.
- Disables `__import__` unless `allow_import=True`.
- Supports an attribute *allowlist* (`SandboxPolicy.allowed_attributes`) for
  strict whitelisting.
- Caps `range()` size (`max_range`, default 10,000) and optionally total
  output length (`max_output_size`).

What the sandbox does **not** do:

- It does not inspect or restrict the Python objects *you* put in the render
  context. If you pass an object with a method that calls `subprocess.run`,
  a template that can reach that method can run subprocesses. Curate your
  context.
- It does not provide CPU, memory, wall-clock, or syscall limits. Enforce
  those at the process or container layer.
- It does not sanitize output *content* beyond autoescape. If you emit
  `Markup(...)`, you are asserting the string is safe for its output
  surface.
- It has not been formally verified against a complete capability model, and
  the Python object model is large. Treat a sandbox escape the same way you
  would treat an RCE in any other library: file a report (see below).

The blocklist, allowlist, `max_range`, and `max_output_size` invariants
described above are verified under hypothesis-generated input by the property
tests in [`tests/test_sandbox_fuzz.py`](./tests/test_sandbox_fuzz.py). A
property failure on shrunken input is treated as a security finding, not a
flaky test — see the reporting protocol below.

### Recommended configuration for adversarial templates

If you must evaluate templates from untrusted authors:

```python
from kida import SandboxedEnvironment
from kida.sandbox import SandboxPolicy

policy = SandboxPolicy(
    allowed_attributes=frozenset({"name", "title", "items", "keys", "values"}),
    allow_import=False,
    allow_mutating_methods=False,
    max_range=1000,
    max_output_size=1_000_000,
)
env = SandboxedEnvironment(sandbox_policy=policy, autoescape=True)
```

Run the rendering process with:

- a wall-clock timeout (seconds, not minutes),
- a memory ceiling (`RLIMIT_AS` / cgroup / container memory),
- no network access and no filesystem write access,
- a minimal render context containing only primitive types and plain dicts.

## Hardening Recommendations (All Users)

Even with fully trusted templates, we recommend:

1. Keep `autoescape=True` (the default). Disable only per-call with explicit
   intent and a code review comment.
2. Use `tojson(attr=true)` when embedding JSON in double-quoted HTML
   attributes. Use default `tojson` only inside `<script type="application/json">`.
3. Pin your Kida version and enable GitHub Dependabot or the equivalent for
   security updates.
4. Avoid `safe()` on any string derived from user input. When you must, pass
   the `reason=` argument documenting the audit.
5. Scope `FileSystemLoader` to a dedicated templates directory. Do not point
   it at a directory that also contains user uploads.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues,
discussions, or pull requests.**

Report privately using one of the following:

1. **Preferred — GitHub private security advisories.** Open a draft advisory
   at https://github.com/lbliii/kida/security/advisories/new. This channel is
   end-to-end private between the reporter and maintainers and is the fastest
   path to a CVE.
2. **Email fallback.** If GitHub advisories are unavailable, contact the
   maintainer listed in `pyproject.toml` or open a minimal public issue
   requesting a private disclosure channel (do **not** include vulnerability
   details in the public issue).

Please include:

- A description of the issue and its impact.
- A minimal reproducer (template source, render context, expected vs. actual
  behavior).
- The Kida version, Python version, and OS.
- Any known mitigations or affected configurations.

### What to expect

| Stage                        | Target                                    |
| ---------------------------- | ----------------------------------------- |
| Acknowledgement of report    | Within 3 business days                    |
| Initial severity assessment  | Within 7 business days                    |
| Fix or mitigation plan       | Within 30 days for High/Critical          |
| Public disclosure            | Coordinated; typically 90 days from report |

We follow coordinated disclosure. Once a fix is available, we will:

- Publish a GitHub security advisory with CVSS score and affected versions.
- Release a patched version on PyPI.
- Credit the reporter in the advisory (unless you prefer to remain anonymous).

### Safe harbor

We will not pursue legal action against researchers who:

- Make a good-faith effort to avoid privacy violations, data destruction, and
  service disruption.
- Report vulnerabilities through the channels above and give us reasonable
  time to respond before public disclosure.
- Do not exploit the issue beyond what is necessary to demonstrate it.

## Security-Relevant Changelog

Security fixes are marked with a `security` fragment in the changelog. See
[CHANGELOG.md](./CHANGELOG.md) for the full history.
