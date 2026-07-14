# Basic-Render Import Boundary Audit

Status: complete measurement and design audit; no import behavior changed

Tracking: [GitHub issue #273](https://github.com/lbliii/kida/issues/273),
part of [epic #167](https://github.com/lbliii/kida/issues/167)

Evidence: [`cold-start-phase-contract.md`](cold-start-phase-contract.md),
[`public-api-classification.md`](public-api-classification.md),
[`src/kida/__init__.py`](../../src/kida/__init__.py), and
[`src/kida/environment/core.py`](../../src/kida/environment/core.py)

## Purpose And Boundary

This audit defines the smallest currently coherent import and first-render path
before any lazy-import implementation. It covers these public operations:

1. `import kida`;
2. `from kida import Environment`;
3. `Environment()`; and
4. `Environment().from_string("Hello").render()`.

The audit classifies every Kida module loaded by that path, reconciles the
static module-level import graph with issue #247's Linux 3.14t phase capture,
and orders possible implementation slices. It does not change eager
availability, object identity, public exports, cache behavior, failure timing,
or type-checker behavior.

## Evidence And Method

The authoritative timing and closure evidence remains issue #247's guarded
Linux CPython 3.14t capture at commit `79b5586`. Its environment, raw samples,
and limitations are recorded in the cold-start phase contract. This audit uses
module and physical-source-line closure as diagnostic evidence only; it makes
no timing or competitive-performance claim.

A bounded AST traversal started at `src/kida/__init__.py`, followed repository-
local module-level imports and ancestor package initializers, and stopped at
function and class bodies, `TYPE_CHECKING` blocks, and external dependencies.
The resulting 43-module static closure exactly matches the 43-module
`import_kida` runtime sample. Function-local imports on the named path were then
reconciled against the later phase samples.

A development-only one-sample run on current `main` at `5e6919a` used:

```console
uv run python benchmarks/benchmark_cold_start_phases.py \
  --warmups 0 --samples 1 --memory-samples 1 \
  --output /tmp/kida-273-current.json
```

Every current phase had the same module set as the authoritative capture. The
development run is graph confirmation, not replacement timing evidence.

| Phase | #247 modules / LOC | Current modules | Set difference |
|---|---:|---:|---:|
| `import kida` | 43 / 15,426 | 43 | 0 |
| `from kida import Environment` | 43 / 15,426 | 43 | 0 |
| `Environment()` | 45 / 16,165 | 45 | 0 |
| First source compile + render | 93 / 33,841 | 93 | 0 |
| First bytecode-cache render | 53 / 17,263 | 53 | 0 |
| Warm render | 93 / 33,841 | 93 | 0 |

These phases are isolated and are not additive.

## Static Frontier

The root module directly imports 13 Kida targets:

- `_types`, `coverage`, `environment`, `extensions`, `render_accumulator`,
  `render_capture`, `render_context`, `render_manifest`, `sandbox`, `template`,
  `tstring`, `utils.html`, and `utils.workers`.

Repository-local package initializers and their module-level imports expand
that frontier to 43 modules:

- `kida.environment` loads `core`, all default filter implementations,
  `loaders`, `protocols`, `registry`, `tests`, exceptions, the lexer, the
  template package, and cache/template-key utilities.
- `kida.template` loads the compiled-template core, cached-block, loop,
  inheritance, introspection, error-enhancement, helper, and render-helper
  modules.
- importing any `kida.utils.*` module executes `kida.utils.__init__`, which
  eagerly re-exports both `LRUCache` and the worker-planning family. Removing
  only the root `utils.workers` import therefore cannot reduce closure.

The named execution path then crosses these function-local boundaries:

- `Environment.__post_init__()` imports `bytecode_cache`; default HTMX globals
  add `environment.globals`.
- `Environment._compile()` imports the parser, dead-code partial evaluator, and
  compiler. Their package initializers expand to 25 compiler, eight node, and
  15 parser modules.
- `Template.__init__()` imports sandbox support before executing the compiled
  namespace. A basic source render therefore needs `kida.sandbox` even if its
  root re-export becomes lazy.
- warm rendering adds no Kida module beyond the 93-module source path.
- the default bytecode-cache path loads the two construction modules plus the
  eight node modules because preserved AST introspection is enabled by default.

There is no unresolved repository-local import on the named default path.
Conditional terminal, Markdown, extension, static-context, validation, and
pre-3.14 t-string branches are deliberately outside this frontier. They must
be exercised by a later implementation's surface-specific tests rather than
silently counted as basic-render requirements.

## Complete Module Classification

The categories are exclusive for this audit:

- **required runtime** means the current default basic-render path needs the
  module to define, construct, compile, or render while preserving current
  behavior;
- **public re-export compatibility** means the module is eager only to preserve
  a public package/root import that the default path does not execute; and
- **authoring/tooling-only candidate** means the module serves opt-in tooling
  and is not otherwise pulled into the default path.

### Required runtime — 87 modules

The 37 import-time modules are:

`kida`, `kida._types`, `kida.environment`, `kida.environment.core`,
`kida.environment.filters`, `kida.environment.filters._collections`,
`kida.environment.filters._debug`,
`kida.environment.filters._html_security`,
`kida.environment.filters._impl`, `kida.environment.filters._misc`,
`kida.environment.filters._numbers`,
`kida.environment.filters._string`,
`kida.environment.filters._type_conversion`,
`kida.environment.filters._validation`, `kida.environment.loaders`,
`kida.environment.registry`, `kida.environment.tests`, `kida.exceptions`,
`kida.lexer`, `kida.render_accumulator`, `kida.render_capture`,
`kida.render_context`, `kida.sandbox`, `kida.template`,
`kida.template.cached_blocks`, `kida.template.core`,
`kida.template.error_enhancement`, `kida.template.helpers`,
`kida.template.inheritance`, `kida.template.introspection`,
`kida.template.loop_context`, `kida.template.render_helpers`, `kida.utils`,
`kida.utils.constants`, `kida.utils.html`, `kida.utils.lru_cache`, and
`kida.utils.template_keys`.

Construction adds `kida.bytecode_cache` and `kida.environment.globals`.

Source compilation adds these 25 compiler modules:

`kida.compiler`, `kida.compiler.analysis_phases`,
`kida.compiler.coalescing`, `kida.compiler.core`,
`kida.compiler.expressions`, `kida.compiler.partial_eval`,
`kida.compiler.partial_eval_constants`,
`kida.compiler.partial_eval_dead_code`,
`kida.compiler.partial_eval_expressions`,
`kida.compiler.partial_eval_inlining`, `kida.compiler.partial_eval_loops`,
`kida.compiler.partial_eval_nodes`, `kida.compiler.statements`,
`kida.compiler.statements.basic`, `kida.compiler.statements.caching`,
`kida.compiler.statements.control_flow`,
`kida.compiler.statements.error_handling`,
`kida.compiler.statements.functions`, `kida.compiler.statements.i18n`,
`kida.compiler.statements.pattern_matching`,
`kida.compiler.statements.special_blocks`,
`kida.compiler.statements.template_structure`,
`kida.compiler.statements.variables`, `kida.compiler.statements.with_blocks`,
and `kida.compiler.utils`.

It also adds eight node modules:

`kida.nodes`, `kida.nodes.base`, `kida.nodes.control_flow`,
`kida.nodes.expressions`, `kida.nodes.functions`, `kida.nodes.output`,
`kida.nodes.structure`, and `kida.nodes.variables`.

Finally, it adds 15 parser modules:

`kida.parser`, `kida.parser.blocks`, `kida.parser.blocks.control_flow`,
`kida.parser.blocks.core`, `kida.parser.blocks.error_handling`,
`kida.parser.blocks.functions`, `kida.parser.blocks.i18n`,
`kida.parser.blocks.special_blocks`,
`kida.parser.blocks.template_structure`, `kida.parser.blocks.variables`,
`kida.parser.core`, `kida.parser.errors`, `kida.parser.expressions`,
`kida.parser.statements`, and `kida.parser.tokens`.

The parser/compiler/node families cannot be removed from a first source
compile by changing root re-exports. Avoiding them requires a separately
designed AOT or compatible bytecode-cache path.

### Public re-export compatibility — 3 modules

- `kida.environment.protocols` preserves `Filter`, `Loader`, and `Test` from
  `kida.environment`; postponed annotations keep it off the default runtime
  path otherwise.
- `kida.extensions` preserves root `Extension`; the default environment has no
  registered extension.
- `kida.tstring` preserves root `k` and `plain`. Its current guarded eager
  import also determines whether those names are callables or `None` on a
  pre-3.14 interpreter.

These modules are not tooling, and changing their eager availability needs
stronger public-compatibility proof than the first implementation slice below.

### Authoring/tooling-only candidates — 3 modules

- `kida.coverage` supplies root `CoverageCollector` and `CoverageResult`.
- `kida.render_manifest` supplies root `FreezeCache`, `FreezeCacheStats`,
  `ManifestDiff`, `RenderManifest`, `SearchEntry`, `SearchManifestBuilder`, and
  `default_field_extractor`.
- `kida.utils.workers` supplies root and `kida.utils` exports
  `WorkerEnvironment`, `WorkloadProfile`, `WorkloadType`,
  `get_optimal_workers`, `get_profile`, `is_free_threading_enabled`, and
  `should_parallelize`.

`render_accumulator` and `render_capture` are classified as required despite
their tooling-oriented APIs: current template helpers import them and generated
render paths consult their ContextVars. Moving them is an internal render-path
redesign, not a root-only lazy import.

## Ordered Implementation Slices

### 1. Root-only coverage and manifest exports

This is the smallest coherent first slice. Replace only the eager root imports
of `kida.coverage` and `kida.render_manifest` with typed, cached module
`__getattr__` resolution. Keep every name in `kida.__all__`.

The affected exports are `CoverageCollector`, `CoverageResult`, `FreezeCache`,
`FreezeCacheStats`, `ManifestDiff`, `RenderManifest`, `SearchEntry`,
`SearchManifestBuilder`, and `default_field_extractor`.

Expected closure, before measurement, is two fewer modules and 680 fewer
physical source lines for every phase: 43 → 41 for `import kida`, 45 → 43 for
construction, 93 → 91 for source/warm render, and 53 → 51 for cached render.
These are graph predictions, not timing claims or approved thresholds.

Required proof:

- `kida.X is origin_module.X` for all nine exports, including repeated access;
- `from kida import X`, `from kida import *`, `kida.__all__`, and `dir(kida)`
  remain compatible;
- subprocess tests prove no import cycle and show that failures are attributed
  to explicit export access, not silently swallowed;
- type checking sees the same root names without runtime eager imports;
- public API snapshots and classification remain unchanged; and
- the phase runner proves the predicted module-set change before any timing
  interpretation.

This slice changes eager import timing and therefore remains a separate
stop-and-ask implementation task.

### 2. Worker-planning package boundary

Lazy root worker exports alone save nothing because `kida.utils.__init__`
eagerly imports `utils.workers` whenever `utils.html` is imported. A coherent
slice must preserve both root and `kida.utils` re-exports, identity, star
imports, and type checking. Its graph prediction is one module and 490 physical
source lines. It has a wider compatibility surface than slice 1.

### 3. Specialized public compatibility imports

Evaluate `extensions`, `environment.protocols`, and `tstring` separately.
The t-string slice is highest risk because current import-time `ImportError`
handling and pre-3.14 `None` values are observable. No grouping or lazy policy
is approved by this audit.

### 4. Path-coupled observability and compilation

`render_accumulator`, `render_capture`, sandbox setup, parser/compiler/nodes,
and preserved cached ASTs require render-surface, hot-path, introspection,
sandbox, and error-attribution design. They are not candidates for a root-only
import change.

## Benchmark And Regression Plan For Any Slice

Capture distinct before and after reports on the documented Linux 3.14t host:

```console
PYTHON_GIL=0 uv run python benchmarks/benchmark_cold_start_phases.py \
  --require-linux-3-14t --warmups 3 --samples 20 --memory-samples 5 \
  --output /tmp/kida-cold-start-before.json

PYTHON_GIL=0 uv run python benchmarks/benchmark_cold_start_phases.py \
  --require-linux-3-14t --warmups 3 --samples 20 --memory-samples 5 \
  --output /tmp/kida-cold-start-after.json
```

Compare phase with phase, require identical preflight output, inspect every raw
sample and module set, and reject warm-render, type-checking, public API, or
failure-attribution regressions. Do not infer causality by subtracting
independently sampled totals.

The minimum repository proof for slice 1 is:

```console
uv run pytest tests/test_public_api_snapshot.py \
  tests/test_public_api_classification.py \
  tests/test_cold_start_phase_benchmark.py -q
make lint
make format-check
make ty
```

Because an implementation changes public import timing, it must also run
`make verify-stability` and record the exact no-pilot or downstream-pilot
classification required by the downstream policy.

## Decision

The basic source path is already a coherent 87-module runtime, not a wholesale
tooling import accident. Six modules sit outside it: three public-compatibility
imports and three tooling-only candidates. The only bounded next implementation
recommended without broader architecture work is slice 1, covering the two
standalone tooling modules and nine existing root exports. This audit does not
approve that behavior change.

## Steward Notes

- Consulted: public, environment, template, benchmarks, docs, and tests.
- Risks: public eager availability and identity, import cycles, failure timing,
  type-checker visibility, star imports, pre-3.14 t-string behavior, and
  misleading timing attribution.
- Evidence: #247 guarded Linux 3.14t artifact, current development-only graph
  reproduction, bounded static traversal, public API classification, and source
  call-path inspection.
- Collateral: this internal audit only; no site, example, schema, changelog,
  migration, or generated-site change because runtime behavior is unchanged.
- No downstream pilot: documentation or planning changed without changing
  normative behavior;
  replacement proof: focused public-contract and cold-start phase tests, lint,
  formatting, and type checks;
  affected contracts: none; the audit changes no import or render behavior.
- Unresolved tradeoff: whether a one- or two-module closure reduction is worth
  changing public import timing remains a separate product decision.
