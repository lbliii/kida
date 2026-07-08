# Maintainability Scorecard

Status: active report-only baseline

Scope: production Python under `src/kida`, tests under `tests`, public exports,
import closure, and selected critical-contract coverage

Tracking: [GitHub issue #195](https://github.com/lbliii/kida/issues/195)

## Purpose

Kida needs a repeatable view of semantic concentration and proof ownership before
large compiler, CLI, or Action refactors. The scorecard makes regression visible;
it is intentionally not a CI gate. A reported `regressed` status still exits zero
until the budgets have proved stable enough for a separate policy decision.

Run the text report:

```console
uv run python scripts/maintainability_scorecard.py
```

Emit the complete machine-readable report:

```console
uv run python scripts/maintainability_scorecard.py --json
```

Include critical-contract coverage after a coverage run:

```console
uv run coverage json -o coverage.json
uv run python scripts/maintainability_scorecard.py --coverage-json coverage.json
```

## July 2026 Baseline

Measured from `origin/main` at `5b17831` after issue #196 was merged.

| Metric | Baseline ratchet | Direction | Target |
|---|---:|---|---:|
| Functions over 200 lines | 12 | no increase | 0 |
| Classes over 1,000 lines | 4 | no increase | 0 |
| Functions above decision complexity 25 | 11 | no increase; review each | 11 |
| Top-level exports | 73 | no increase without contract review | 73 |
| Exports absent from public docs/examples | 14 | decrease | 0 |
| Modules loaded by an isolated basic render | 93 | no increase | 93 |
| Source files with a direct test-ownership signal | 63.4% | increase | 100% |
| Selected critical-contract line coverage | 84.5% | increase | 95% |

The source inventory is 145 Python files / 44,731 physical lines. The test
inventory is 150 Python files / 46,677 physical lines. LOC describes scope; it is
not a reduction target.

## Method

- **Definition span** uses Python AST `lineno`/`end_lineno`; decorators are not
  included. Nested functions and methods remain separate definitions.
- **Decision complexity** starts at one and counts conditionals, loops, boolean
  branches, exception handlers, match cases, and comprehension branches. This is
  a deterministic repository metric, not a claim of exact parity with Ruff or
  another McCabe implementation.
- **Public exports** come from the literal `kida.__all__`. An export is considered
  documented when its exact name appears in the README, public site docs, or a
  checked example.
- **Import closure** runs an isolated interpreter with `PYTHONPATH=src`, imports
  `kida`, compiles and renders a minimal string template, and counts loaded
  modules whose files live under `src/kida`.
- **Test ownership** is a conservative signal: a source module is owned when a
  test imports it directly (or a descendant) or has an exact filename match. It
  does not claim behavioral coverage.
- **Critical coverage** aggregates line coverage for the checked-in set of
  escaping, sandbox, resolution, cache, call-validation, and diagnostic modules.
  Missing files are reported explicitly.

## Reconciled Audit Claims

The issue's estimates of 12 functions over 200 lines, four classes over 1,000
lines, roughly 44.7K production lines, roughly 46.6K test lines, and 73 exports
match the executable baseline. The earlier estimate of 12 undocumented exports
does not: the deterministic docs/examples scan finds 14. The scorecard records
14 rather than encoding the stale estimate.

The issue's 211 Ruff complexity findings combined several rule families and
thresholds. The scorecard's 11 outliers are intentionally narrower: functions
whose documented decision count is above 25. These numbers answer different
questions and should not be compared as if they were the same metric.

The current outlier families are CLI orchestration (`_cmd_check`, `_cmd_diff`),
compiler/partial-evaluation traversal and dispatch, region code generation,
test-expression dispatch, lexer state-machine handling, and diagnostic
enhancement. They remain visible in the JSON report. The count target is a cap,
not an assertion that every outlier is desirable or permanently exempt; each
changed outlier still needs a domain explanation and, for hot paths, benchmark
evidence.

## Interpretation And Follow-up

Ratchets prevent a worse baseline from becoming normal while the target records
the intended direction. Natural dispatch code may justify an outlier; a PR can
record that rationale rather than contorting clear code to lower a number.

Before converting any metric into a failing gate, validate it across several
refactor PRs, document accepted exceptions, and obtain explicit approval for the
new CI/configuration policy. The current scorecard makes no runtime, public API,
CLI, release, or dependency change.
