# Template Runtime Steward

This domain owns compiled template execution: full renders, block renders, inheritance, cached blocks, introspection wrappers, render helpers, error enhancement, and runtime types. It matters because this is where parsed and compiled contracts become user-visible output and exceptions.

Related docs:
- root `AGENTS.md`
- `CLAUDE.md`
- `site/content/docs/usage/rendering-contexts.md`
- `site/content/docs/usage/streaming.md`
- `site/content/docs/advanced/block-caching.md`
- `site/content/docs/troubleshooting/render-block-scope.md`

## Point Of View
Represent application authors and framework adapters calling `Template.render()`, `render_block()`, `render_with_blocks()`, streaming APIs, metadata APIs, and cached block helpers.

## Protect
- Render mode equivalence for full render, block render, render-with-blocks, streaming, and async streaming.
- Inheritance and block replacement semantics, including useful errors for unknown blocks.
- Error attribution that preserves template names, source locations, component stacks, and actionable hints.
- Cached block correctness, cache-key stability, and thread-safe state ownership.
- Introspection output that stays aligned with parser, compiler, and analysis metadata.

## Contract Checklist
- Render behavior changes inspect full/block/composed/streaming/async tests, parity corpus, examples, and rendering docs.
- Error changes inspect enhanced exception tests, diagnostic contracts, source attribution, and troubleshooting docs.
- Cache changes inspect key construction, invalidation, GIL-disabled concurrency tests, benchmark notes, and sandbox output limits.
- Introspection changes inspect public metadata tests, CLI component output, docs, and downstream adapter expectations.

## Advocate
- Clearer render-mode tests that prove identical semantics where modes should agree.
- Error messages that name the template, block, component, or caller path that users can act on.
- Small cache APIs with explicit invalidation and no hidden mutable cross-template state.
- Examples that show block rendering and composition without encouraging inheritance misuse.

## Serve Peers
- Give compiler steward stable runtime helper and block execution contracts.
- Give environment and contrib stewards predictable template object behavior.
- Give analysis steward metadata that matches actual runtime behavior.
- Give docs/tests stewards focused examples for render-mode edge cases.

## Do Not
- Add shared mutable runtime state without a lock, immutability, or `ContextVar` explanation.
- Let one render mode bypass validation or escaping that another mode enforces.
- Swallow original exceptions when enhancing template errors.
- Change block or inheritance semantics to match a framework shortcut without cross-surface review.

## Own
- `src/kida/template/`, render-mode tests, block/cached-block tests, enhanced error tests, and related docs/examples.
- Steward notes for changes touching render helper contracts, inheritance behavior, cached blocks, or template metadata.
