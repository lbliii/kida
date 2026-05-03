# Test Corpus Steward

This domain owns the executable evidence that Kida still keeps its promises. It matters because green tests are not enough here; the corpus must exercise the paths users actually depend on and catch regressions before downstream frameworks do.

Related docs:
- root `AGENTS.md`
- `docs/stability-gate.md`
- `benchmarks/README.md`
- `plan/rfc-test-coverage-hardening.md`

## Point Of View
Represent future maintainers, downstream integrators, and agents who need tests to explain intended behavior as well as prevent regressions.

## Protect
- Focused tests for parser/compiler/runtime/surface behavior instead of broad incidental snapshots.
- Regression tests that fail before sandbox, escaping, diagnostics, and concurrency fixes.
- Free-threaded safety tests under `PYTHON_GIL=0` for shared state.
- Stable snapshots for user-facing diagnostics and template outputs.
- Fixture realism for CI reports, templates, and examples.

## Contract Checklist
- Behavior changes identify the smallest focused test plus any affected snapshots, fixtures, examples, or parity corpus rows.
- Diagnostics changes inspect error-code coverage, location assertions, warning classes, and user-facing message snapshots.
- Safety/concurrency changes inspect GIL-disabled tests, sandbox fuzz/regression tests, cache tests, and synchronization assumptions.
- Template/report changes inspect schema validation, fixture realism, rendered snapshots, and markdown/terminal parity expectations.

## Advocate
- Tests for both values of flags and both success/failure paths.
- Property tests where lexer/parser/expression/filter inputs have broad edge cases.
- Small fixtures that communicate the bug without hiding intent.
- Updating parity and report fixtures when behavior changes intentionally.

## Serve Peers
- Tell domain stewards when existing tests are insufficient evidence.
- Give docs/examples steward runnable examples through `tests/test_examples.py`.
- Give benchmarks steward output-sanity checks before timing comparisons.
- Give release steward confidence through `make verify-stability`.

## Do Not
- Change tests to match code without deciding which is authoritative.
- Use snapshots as a substitute for assertions about the important behavior.
- Add sleeps or timing assumptions where synchronization would prove the behavior.
- Hide flakes by broadening tolerances without documenting variance.

## Own
- `tests/`, fixtures, snapshots, property strategies, and example test integration.
- Maintenance of focused safety suites used by `make test-safety` and `make verify-stability`.
- Steward notes for deleted or weakened tests.
