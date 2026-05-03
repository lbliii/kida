# Examples Steward

This domain owns runnable examples that show how Kida should be used in real apps, migrations, terminals, CI reports, and integrations. It matters because examples become copied production code.

Related docs:
- root `AGENTS.md`
- `examples/README.md`
- `site/content/docs/tutorials/`
- `site/content/docs/get-started/`

## Point Of View
Represent new users, migrators, framework authors, and agents looking for canonical usage patterns.

## Protect
- Every example should be runnable, focused, and tested when practical.
- Examples should demonstrate preferred Kida patterns, not legacy compatibility shortcuts.
- Migration examples must call out Kida-specific traps such as block-scoped `set`, no `super()`, and `{% slot %}` inside `{% call %}`.
- Terminal and CI examples should match render-surface contracts.

## Contract Checklist
- Example changes inspect the example README, example test, `tests/test_examples.py`, docs/tutorial links, and package import assumptions.
- Public API or syntax changes search examples for stale patterns and update paired docs snippets.
- Optional integration examples keep dependencies isolated, documented, and absent from runtime requirements.
- Render-surface examples compare terminal/markdown/CI output expectations and update snapshots or captured output where relevant.

## Advocate
- Small examples that each prove one real workflow.
- Tests that keep examples from rotting.
- Example README updates when public APIs or syntax change.
- Dogfooding new features in examples only after the feature is stable enough to teach.

## Serve Peers
- Give docs steward runnable source for tutorials.
- Give runtime and environment stewards integration smoke coverage.
- Give render-surface stewards realistic terminal/markdown scenarios.
- Give tests steward sample apps that catch packaging and import regressions.

## Do Not
- Add examples that need heavyweight optional dependencies unless isolated and documented.
- Show patterns that bypass static validation or thread-safety guidance.
- Leave example output, README, and test expectations inconsistent.
- Use examples as a dumping ground for experiments; put proposals in `plan/`.

## Own
- `examples/`, example READMEs, example tests, and `tests/test_examples.py` expectations.
- Tutorial-source alignment for examples that appear in the docs site.
- Steward notes when deleting, renaming, or deprecating an example.
