# AGENTS.md

Kida sits between an app's data and the bytes its users see. A bug here ends up in someone's published site, a checkout page, a CI report, an SSH session — places where the user can't see Kida and can't defend themselves from what it does. Treat the rules below as safety rules, not style rules.

For tactical syntax/API reference, see `CLAUDE.md`. This file is about *how to make changes well*.

---

## North star

**Bring the component model to pure Python, statically validated, on free-threaded 3.14t.** Typed props, named slots, scoped state, error boundaries — caught at check time, not at the user. Kida is not "Jinja2 but faster"; it's a different shape, and the shape is what justifies the project. If a change blunts the static-validation story, the component-model story, or the free-threading story, it isn't worth shipping.

---

## Design philosophy

- **Pure Python is the deal.** No C extensions. The optional `markupsafe` is a perf accelerant; the project must work without it. Compiling something native dies the moment we say "pure Python."
- **Compile-time over runtime.** AST compilation, dispatch dicts, partial evaluation, the `pure` decorator — the answer is almost always "do it at check time." Runtime branches you didn't have to take are the cheapest branches.
- **Static safety > dynamic flexibility.** `{% set %}` is block-scoped, `{% def %}`/`{% region %}` are top-level only, unknown call params are an error. We chose all of these on purpose. Don't loosen them without a strong reason.
- **Free-threading is real, not aspirational.** `_Py_mod_gil = 0` is declared in `src/kida/__init__.py`. All public APIs are thread-safe by design — `ContextVar` for render state, copy-on-write for env mutations, local StringBuilder per render. Kida is the rendering canary for 3.14t; treat it that way.
- **Render surfaces are first class.** HTML, terminal, markdown, CI reports — parity matters. If you change one, think about the other three. The parity corpus exists for a reason (commit 88758c4).
- **The sandbox is defense-in-depth, not isolation.** Don't ever describe it as a security boundary. See `src/kida/sandbox.py` docstring — combine with OS-level isolation for untrusted input.
- **Sharp edges are bugs.** Silent `except`, `# type: ignore`, ambiguous flags, errors that don't tell the reader what to do — not taste, bugs. CI catches some (S110 is on, `ty` target is zero); the rest is on you. See commits 6bdc245, 618b9ef.

---

## Stakes

When you change something in Kida, the blast radius is:

- **Compiler / codegen bugs** (`src/kida/compiler/`, `src/kida/parser/`, `src/kida/lexer.py`) → silent miscompiles. Bengal renders thousands of static pages; Chirp renders per request. A wrong escape is an XSS in someone's published site or someone's session. Debuggable only by reading generated Python.
- **Render-surface drift** (`src/kida/markdown/`, `src/kida/terminal/`, GitHub Action) → markdown that breaks a CI report, ANSI that corrupts an SSH session, HTML that diverges from terminal in subtle ways. The parity corpus is the canary; if you touched a surface and the corpus didn't change, you probably missed something.
- **Free-threaded races** → no GIL safety net. A race we ship normalizes "no-GIL is flaky" for the whole ecosystem. Caches, env mutation, shared compiled-template state are the hot zones.
- **Sandbox bypass** → don't ever close a sandbox issue without a regression test that *fails* before the fix. Reflection attributes (`__class__`, `__globals__`, `gi_frame`, etc.) are an open category; assume new ones exist.
- **Performance regressions** → README claims (1.81x at 8 workers, etc.) and the partial-evaluator's pure-filter folding are load-bearing for the project's pitch. CI doesn't catch every one — you do.

Kida is shipped (Bengal and Chirp depend on it) and pre-1.0. Calibrate accordingly: real users, but the API can still move.

---

## Who reads your output

- **Framework builders** — Bengal, Chirp. They read `template_metadata()`, `block_metadata()`, tracebacks with line/col, and your error messages when their users misuse a tag.
- **SSG authors** — read `kida check` / `kida format` output. If your error doesn't include the template path and a fix, it's wrong.
- **Agents doing bulk template edits in downstream repos** — the whack-a-mole case. An agent migrating an IA across dozens of `{% call %}`/`{% if %}` nests finds parse errors one rendered route at a time unless we tell them about `kida check <dir> --strict --validate-calls`. Parser errors on unmatched `{% end %}` should surface that tip; agent-facing docs should lead with it.
- **Migrators from Jinja2** — want to be done in five minutes. The `set` vs `let` trap is the #1 thing they hit. Error messages should *catch them*, not let them debug it themselves.
- **Contributors** — know templating, not our internals. They read parser/compiler files; mixin patterns are surprising.
- **Me (Lawrence)** — read diffs. Put the *what* in code, the *why* in the PR.

---

## Escape hatches — stop and ask

Forks where I want a check-in, not a judgment call:

- **New runtime dependency.** Default is no. Optional groups are fine; `dependencies = []` in `pyproject.toml` is a contract.
- **Touching a hot path** — `src/kida/compiler/core.py`, `compiler/partial_eval.py`, `parser/`, `lexer.py`, `render_accumulator.py`. Show before/after benchmarks. Can't measure → don't change.
- **New AST node or tag.** Touches lexer, parser, compiler, formatter, analysis, *and* the parity corpus. Sketch first.
- **Public API change** — anything in `__all__` in `src/kida/__init__.py`, the `Environment` constructor, `Template` methods, the `kida` CLI. Ask whether the break is worth it.
- **New top-level filter / test / global.** Reshape an existing one or put it in contrib first. The default surface is curated.
- **New `ServerConfig`-shaped option** (`Environment(...)` kwarg, sandbox policy field). If no one asked for it, don't add it.
- **Sandbox semantic change.** Even tightening. Sandboxed templates exist in someone's tree; loosening can introduce CVE-class bugs, tightening can break renders.
- **Worker / parallelism tuning** (`src/kida/utils/workers.py`). The profiles are calibrated; changing them shifts everyone's perf curve.
- **Free-threaded shared state.** Adding any module-level mutable state, any shared cache, any singleton. Sketch the locking story before implementing.
- **Test disagrees with code.** Ask which is authoritative before "fixing" either.
- **Can't reproduce a reported bug.** Stop. Ask for a minimal template + render context.
- **Adjacent issues found mid-task.** List in the PR description; don't fold them in. Exception: refactors, where one bundled PR beats churn.

---

## Anti-patterns

Things that look reasonable and are wrong here:

- **C extensions or new runtime deps "just for the hot path."** No. Pure Python is the project.
- **`try: ... except Exception: pass`.** S110 is on for a reason. If you must swallow, log what and why.
- **`# type: ignore`.** Target is zero. Narrow the type or fix the code. The compiler/parser mixin overrides in `pyproject.toml` are the existing exceptions; don't grow the list silently.
- **Speculative config options** for "future flexibility." The Environment surface is already wide. Easier to add later than to remove.
- **Defensive validation inside internal code.** Validate at the boundary (parser, public API). Internal code trusts its callers.
- **A new tag when composition would do.** `{% def %}` + `{% slot %}` + `{% call %}` cover most of what people reach for. Adding `{% fill %}` was the *wrong* answer; we chose `{% slot %}`-inside-`{% call %}` instead. Apply the same pressure to new ideas.
- **Loosening static checks** to make a test pass. Top-level-only defs/regions, block-scoped `set`, unknown-param errors — these are features.
- **Touching one render surface without checking the others.** HTML, terminal, markdown, CI-reports parity is a project invariant.
- **Refactoring during a bug fix.** Separate PR. Exception: the refactor *is* the fix.
- **Closing a sandbox issue without a regression test.** Don't.

---

## Done criteria

A change is done when all of these hold:

- [ ] `make lint` and `make ty` clean. No new `# type: ignore`, no new `noqa: S110`/`S112`, no new per-file ignores.
- [ ] Tests exercise the *interesting* path: both values of a flag, malformed source for parser changes, the failure path for sandbox/error-boundary work, parity corpus updates for render-surface changes.
- [ ] Hot-path or compiler change → benchmark in the PR. "Didn't benchmark" is OK only if you say why.
- [ ] Free-threaded touch → note what you thought about. Shared mutable state, cache eviction races, ContextVar propagation first.
- [ ] Public API changed → CHANGELOG entry, migration note if breaking, docs updated under `site/content/docs/`.
- [ ] New error or warning → carries an `ErrorCode`, names the template/line, and tells the reader what to do next.
- [ ] PR description explains *why*. The diff explains *what*.

"Tests pass" is not "done." Tests pass on broken code all the time — see commit 5462c83's CoercionWarning gap as an example.

---

## Review and assimilation

- **I read diff-first, description-second.** Tight diff + clear *why* merges fast; sprawling diff gets questions.
- **One concern per PR.** If the diff needs section headers, it's two PRs. Exception: refactors renaming a concept across many files (e.g., 4faa27c, dfb48ab) — one bundled PR beats review churn.
- **Commit style:** see `git log`. `feat:` / `fix:` / `refactor:` / `docs:` / `release:` prefixes, imperative subject, body = motivation. PR number in the subject (`(#123)`) — `gh` adds it on merge; don't write it yourself.
- **Don't trailing-summary me.** If the diff is readable, I can read it.
- **Flag surprises.** Weird test, dead branch, an analysis pass that disagrees with the parser — put it in the PR description. Don't fix silently, don't ignore.

---

## When this file is wrong

It will be. Tell me. The worst outcome is that it sits here for a year contradicting how the project actually works. Updates to AGENTS.md are a first-class PR — short, focused, and welcome.
