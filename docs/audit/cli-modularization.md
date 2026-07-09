# CLI Modularization Evidence

Status: implemented and verified

Tracking: [GitHub issue #147](https://github.com/lbliii/kida/issues/147)

Baseline: `origin/main` at `08fcfb4` on 2026-07-08

## Contract

The public boundary remains `kida.cli:main(argv: list[str] | None = None) -> int`.
The eight subcommands, argparse help, flags, output streams, serialized shapes,
and exit statuses are unchanged. Kida remains argparse-based and adds no runtime
dependency; adopting Milo would create a dependency cycle because Milo depends
on Kida.

The implementation now has three private layers:

1. `kida.cli` is a dependency-light compatibility facade.
2. `kida._cli.parser` owns the public argument tree, while
   `kida._cli.bootstrap` resolves one immutable command-to-module mapping.
3. One command-owned module implements each subcommand. Dispatch imports only
   the selected implementation. Structured commands expose collection or
   comparison facts separately from rendering where that separation is useful.

`kida check` continues to consume the canonical collector and text/JSON/SARIF
renderers introduced by issue #193. No command independently reformats analysis
records.

## Before And After

| Measure | Before | After | Result |
|---|---:|---:|---|
| `src/kida/cli.py` physical lines | 1,123 | 20 | compatibility facade only |
| `main()` span | 352 | 6 | parser/dispatch separated |
| CLI functions over 200 lines | 1 | 0 | outlier removed |
| CLI functions above complexity 25 | 1 | 0 | `_cmd_diff` replaced by compare/render seams |
| Repository functions over 200 lines | 12 | 11 | scorecard ratcheted |
| Repository complexity outliers | 11 | 10 | scorecard ratcheted |
| Focused CLI line/branch coverage | 53.7% | 94.7% | no exclusions added |
| `import kida.cli` median | 119.6 ms | 112.1 ms | 6.3% faster |
| root `--help` median | 120.7 ms | 117.2 ms | 2.9% faster |

Cold measurements use 20 fresh Python 3.14.2t subprocesses on macOS arm64,
with stdout/stderr discarded and the median reported. These are review evidence,
not a timing-based CI gate. P95 values were intentionally not made contractual
because local process scheduling introduced large tails; the approved acceptance
criterion is no more than a 10% median regression.

## Proof Matrix

| Command | Direct owner | Success proof | Failure/edge proof | Presentation proof |
|---|---|---|---|---|
| `check` | `_cli/check.py` | text/JSON/SARIF parity suites | missing roots, partial scans, invalid internal format | canonical diagnostic renderers |
| `render` | `_cli/render.py` | HTML/terminal/Markdown, data and streaming suites | missing file, invalid data, render failure, malformed `--set` | output and optimization explanation |
| `components` | `_cli/components.py` | metadata and filtering suites | missing/empty/malformed templates | direct text/color and JSON assertions |
| `manifest` | `_cli/manifest.py` | capture, search, file output, context data | missing root, template skip/render failures | stable JSON serializer |
| `diff` | `_cli/diff.py` | unchanged and all change families | either manifest missing | immutable comparison plus text renderer |
| `readme` | `_cli/readme.py` | presets, JSON, file output, overrides | missing root, bad override, render failure | existing README renderer |
| `extract` | `_cli/extract.py` | stdout/file POT and extension selection | missing root and malformed template continuation | pure POT formatter |
| `fmt` | `_cli/fmt.py` | check and write modes | missing path and formatter failure | shared stream writer |

The public help snapshot covers the complete subcommand/flag tree. Isolated
subprocess tests prove that importing `kida.cli` loads neither the parser nor a
command implementation, and dispatching `fmt` loads `fmt` without importing the
other seven handlers.

## Deliberate Non-Changes

- no new command, flag, configuration surface, or schema
- no stdout/stderr or exit-code change
- no parser/compiler/render hot-path change
- no shared mutable state or concurrency policy change
- no runtime dependency or Milo integration
- no timing threshold in CI; measurements remain review evidence coordinated
  with cold-start issue #167
