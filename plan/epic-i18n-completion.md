# Epic: Complete i18n — Extraction Tooling, Analysis Integration & Hardening

**Status**: Complete
**Created**: 2026-04-10
**Target**: v0.4.0
**Estimated Effort**: 14–20 hours
**Dependencies**: None — core i18n pipeline (nodes, parser, compiler, environment, tests) already ships in v0.3.4
**Source**: RFC `plan/rfc-i18n.md`, codebase audit of existing implementation gaps

---

## Why This Matters

The core `{% trans %}` pipeline is 75% complete — parsing, compilation, environment
wiring, and 230 lines of tests all ship today. But without extraction tooling,
analysis integration, and parser hardening, i18n is a runtime-only feature.
Developers can render translated templates but cannot:

1. **Extract translatable strings** from templates for translator handoff — every
   project must manually maintain `.po` files, defeating the purpose of structured
   `{% trans %}` blocks
2. **Integrate with Babel/pybabel** — the standard Python i18n workflow is broken;
   no entry point exists
3. **Detect i18n-related bugs statically** — dependency analysis skips `Trans` nodes
   entirely, so `kida check` cannot warn about undefined variables inside trans blocks
4. **Prevent nested `{% trans %}` blocks** — parser accepts `{% trans %}{% trans %}...{% end %}{% end %}`
   silently, producing undefined behavior
5. **Optimize constant translations** — no compile-time folding for trans blocks with
   no variables, leaving performance on the table

### Evidence Table

| Source | Finding | Proposal Impact |
|--------|---------|-----------------|
| `src/kida/analysis/` | No `i18n.py` — no `ExtractMessagesVisitor`, no `ExtractedMessage` | FIXES (Sprint 1) |
| `src/kida/cli.py` | No `extract` subcommand | FIXES (Sprint 2) |
| `pyproject.toml` | No `babel.extractors` entry point | FIXES (Sprint 2) |
| `src/kida/analysis/dependencies.py` | No `visit_Trans` or `visit_TransVar` — Trans nodes invisible to dep analysis | FIXES (Sprint 3) |
| `src/kida/analysis/purity.py` | No Trans handling — purity analyzer ignores i18n | FIXES (Sprint 3) |
| `src/kida/parser/blocks/i18n.py` | `_parse_trans()` does not check block stack for nested trans | FIXES (Sprint 1) |
| RFC `rfc-i18n.md` | `optimize_translations` flag specified but not implemented | FIXES (Sprint 3) |

---

### Invariants

These must remain true throughout or we stop and reassess:

1. **Zero runtime dependencies**: All new code uses stdlib only (`gettext`, `ast`, `dataclasses`). No new packages in `[project.dependencies]`.
2. **Existing tests stay green**: Every sprint passes the full `pytest` suite before merge — the 230 existing i18n tests and all 3,264 other tests.
3. **Extraction round-trips**: Any message extracted by `ExtractMessagesVisitor` from a parsed AST must, when translated and installed, produce the same interpolation pattern at render time. No message ID drift.

---

## Target Architecture

After this epic, the i18n workflow is complete:

```
Template Source
    │
    ▼
  Lexer → Parser → Kida AST ──────────────────────┐
                       │                            │
                       ▼                            ▼
                   Compiler                  ExtractMessagesVisitor
                       │                            │
                       ▼                            ▼
                  Python AST               list[ExtractedMessage]
                       │                            │
                       ▼                            ▼
                   render()               POT file / Babel output
                       │
            ┌──────────┴──────────┐
            ▼                     ▼
      _gettext(msg)        _ngettext(s,p,n)
      (from env)           (from env)
```

New files:
- `src/kida/analysis/i18n.py` — `ExtractedMessage` + `ExtractMessagesVisitor`
- `src/kida/babel.py` — Babel extractor entry point
- `tests/test_i18n_extraction.py` — Extraction-specific tests

Modified files:
- `src/kida/cli.py` — `extract` subcommand
- `src/kida/analysis/dependencies.py` — `visit_Trans`, `visit_TransVar`
- `src/kida/analysis/purity.py` — Trans node handling
- `src/kida/parser/blocks/i18n.py` — Nested trans validation
- `pyproject.toml` — Babel entry point registration

---

## Sprint Structure

| Sprint | Focus | Effort | Risk | Ships Independently? |
|--------|-------|--------|------|---------------------|
| 0 | Design: validate extraction round-trip | 2h | Low | Yes (RFC validation only) |
| 1 | Message extraction visitor + parser hardening | 4–6h | Low | Yes |
| 2 | CLI extract command + Babel plugin | 4–6h | Medium | Yes |
| 3 | Analysis integration + compile-time optimization | 4–6h | Medium | Yes |

---

## Sprint 0: Design & Validate

**Goal**: Confirm the extraction data model round-trips correctly before writing production code.

### Task 0.1 — Validate ExtractedMessage schema against POT format

Write a throwaway script that creates `ExtractedMessage` instances by hand, formats
them as POT entries, and verifies the output matches GNU gettext expectations. Confirm:
- Singular messages produce `msgid` + `msgstr ""`
- Plural messages produce `msgid` + `msgid_plural` + `msgstr[0]` + `msgstr[1]`
- Line numbers and filenames appear in `#:` comments
- `%(name)s` placeholders survive round-trip

**Acceptance**: Script runs, output matches `xgettext`-produced POT for equivalent C strings.

### Task 0.2 — Validate FuncCall extraction for `_()` and `_n()`

Confirm that `FuncCall` nodes for `_("literal")` and `_n("s", "p", n)` carry enough
information (func name, args as `Const` nodes) for extraction. Read the expression
parser to verify string literals in function calls produce `Const` nodes.

**Acceptance**: Manual AST dump of `{{ _("hello") }}` shows `FuncCall(func=Name(name="_"), args=[Const(value="hello")])`.

---

## Sprint 1: Message Extraction Visitor + Parser Hardening

**Goal**: Templates can be parsed and their translatable strings extracted programmatically.

### Task 1.1 — Create `src/kida/analysis/i18n.py`

Implement `ExtractedMessage` dataclass and `ExtractMessagesVisitor` class per the RFC
(lines 652–751). The visitor must handle:

- `Trans` nodes → extract singular (and plural if present)
- `FuncCall` nodes for `_("literal")` → extract gettext message
- `FuncCall` nodes for `_n("s", "p", n)` → extract ngettext message
- Non-constant arguments to `_()` / `_n()` → skip silently (can't extract runtime values)

**Files**: `src/kida/analysis/i18n.py` (new, ~100 lines)
**Acceptance**:
- `rg 'class ExtractMessagesVisitor' src/kida/analysis/i18n.py` returns 1 hit
- `rg 'class ExtractedMessage' src/kida/analysis/i18n.py` returns 1 hit
- Unit tests pass (Task 1.3)

### Task 1.2 — Add nested `{% trans %}` validation to parser

In `src/kida/parser/blocks/i18n.py`, add a check at the start of `_parse_trans()` that
inspects the block stack. If a `"trans"` block is already open, raise `TemplateSyntaxError`.

**Files**: `src/kida/parser/blocks/i18n.py` (~5 lines added)
**Acceptance**:
- `{% trans %}{% trans %}Hello{% end %}{% end %}` raises `TemplateSyntaxError` with message containing "nested"
- Existing trans tests still pass

### Task 1.3 — Write extraction tests

Create `tests/test_i18n_extraction.py` covering:

1. Extract singular `{% trans %}` message
2. Extract plural `{% trans %}...{% plural %}` message
3. Extract `_("literal")` from expression
4. Extract `_n("s", "p", n)` from expression
5. Skip `_(variable)` (non-constant argument)
6. Multiple messages from one template
7. Correct line numbers in extracted messages
8. Whitespace normalization in extracted messages
9. Nested trans raises error (parser hardening)

**Files**: `tests/test_i18n_extraction.py` (new, ~120 lines)
**Acceptance**: `pytest tests/test_i18n_extraction.py -v` — all tests pass

---

## Sprint 2: CLI Extract Command + Babel Plugin

**Goal**: Developers can extract messages from the command line and integrate with pybabel.

### Task 2.1 — Add `kida extract` CLI subcommand

Add an `extract` subcommand to `src/kida/cli.py` that:
- Accepts a directory path and optional `-o` output file (default: stdout)
- Loads templates via `FileSystemLoader`
- Parses each `.html` / `.txt` / `.xml` template to AST
- Runs `ExtractMessagesVisitor` on each
- Outputs standard POT format

**Files**: `src/kida/cli.py` (~60–80 lines added)
**Acceptance**:
- `kida extract tests/templates/ 2>/dev/null | head -20` produces valid POT header
- `kida extract tests/templates/ -o /tmp/test.pot && test -f /tmp/test.pot` succeeds

### Task 2.2 — Create `src/kida/babel.py` Babel extractor

Implement the Babel extraction interface per RFC (lines 784–809):
- Function signature: `extract(fileobj, keywords, comment_tags, options)`
- Yields `(lineno, function, message, comments)` tuples
- Uses `ExtractMessagesVisitor` internally

**Files**: `src/kida/babel.py` (new, ~30 lines)
**Acceptance**:
- `python -c "from kida.babel import extract; print(extract)"` succeeds
- Integration test with `babel.messages.extract.extract` works (if Babel installed)

### Task 2.3 — Register Babel entry point

Add to `pyproject.toml`:
```toml
[project.entry-points."babel.extractors"]
kida = "kida.babel:extract"
```

**Files**: `pyproject.toml` (2 lines added)
**Acceptance**: `python -c "from importlib.metadata import entry_points; eps = entry_points(group='babel.extractors'); print([e for e in eps if e.name == 'kida'])"` returns the entry point

### Task 2.4 — Write CLI and Babel tests

Tests for:
1. `kida extract` produces valid POT output
2. `kida extract -o file.pot` writes to file
3. `kida extract` on empty directory produces header only
4. Babel extractor yields correct tuples
5. Babel extractor handles encoding option

**Files**: `tests/test_i18n_extraction.py` (extend, ~60 lines added)
**Acceptance**: `pytest tests/test_i18n_extraction.py -v` — all tests pass

---

## Sprint 3: Analysis Integration + Compile-Time Optimization

**Goal**: `kida check` understands trans blocks; constant translations fold at compile time.

### Task 3.1 — Add `visit_Trans` to dependency analysis

In `src/kida/analysis/dependencies.py`, add:
- `visit_Trans`: walk `node.variables` expressions and `node.count_expr`
- `visit_TransVar`: walk `node.expr`

This ensures `kida check` reports undefined variables used inside trans blocks.

**Files**: `src/kida/analysis/dependencies.py` (~15 lines added)
**Acceptance**:
- `{% trans name=undefined_var %}Hello, {{ name }}!{% end %}` triggers undefined variable warning in `kida check`

### Task 3.2 — Add Trans handling to purity analysis

In `src/kida/analysis/purity.py`:
- Trans nodes are **impure** by default (gettext calls have side effects — locale state)
- When `optimize_translations` is enabled, Trans nodes with no variables and constant messages are **pure** (foldable)

**Files**: `src/kida/analysis/purity.py` (~10 lines added)
**Acceptance**:
- Purity analyzer marks `Trans` nodes as impure
- With `optimize_translations=True`, constant trans blocks are marked pure

### Task 3.3 — Add `optimize_translations` environment flag

Add `optimize_translations: bool = False` to `Environment`. When enabled, the compiler
can fold `{% trans %}Hello{% end %}` (no variables, no plural) to a direct string append
at compile time, bypassing the gettext call.

**Files**: `src/kida/environment/core.py` (~5 lines), `src/kida/compiler/statements/i18n.py` (~15 lines)
**Acceptance**:
- `Environment(optimize_translations=True)` compiles `{% trans %}Hello{% end %}` to `_append("Hello")` (no gettext call) when the identity gettext is installed
- `Environment(optimize_translations=False)` still emits the gettext call

### Task 3.4 — Write analysis integration tests

Tests for:
1. Dependency walker finds variables in trans blocks
2. Dependency walker finds variables in count_expr
3. Purity analyzer marks trans as impure
4. Purity analyzer + optimize_translations marks constant trans as pure
5. optimize_translations compiles to direct append

**Files**: `tests/test_i18n_extraction.py` or `tests/analysis/` (~40 lines)
**Acceptance**: `pytest tests/test_i18n_extraction.py tests/analysis/ -v -k i18n` — all pass

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| POT format edge cases (encodings, multiline messages) | Medium | Medium | Sprint 0 validates format before any code; test against `xgettext` output |
| Babel API contract changes between versions | Low | Low | Babel extractor is optional; import guarded; tested only when Babel installed |
| Nested trans validation breaks edge case in existing templates | Low | High | Sprint 1 adds validation behind the existing block stack mechanism; full test suite gates |
| `optimize_translations` folds away a message that should be translated | Medium | High | Off by default; only folds when identity gettext is confirmed; Sprint 3 tests verify |
| CLI `extract` performance on large template directories | Low | Low | Extraction is parse-only (no compilation); parse is already fast; defer optimization |

---

## Success Metrics

| Metric | Current | After Sprint 1 | After Sprint 3 |
|--------|---------|-----------------|-----------------|
| Extractable message types | 0 (no extraction) | Trans + _() + _n() from AST | Same + compile-time fold |
| CLI extraction support | None | None | `kida extract` command |
| Babel integration | None | None | Entry point registered |
| Trans nodes in dep analysis | Invisible | Invisible | Full variable tracking |
| Nested trans detection | Silent | Error raised | Error raised |
| i18n test count | 23 (test_i18n.py) | ~35 | ~50 |

---

## Relationship to Existing Work

- **RFC `rfc-i18n.md`** — this epic implements the remaining ~25% of that RFC (extraction, analysis, optimization)
- **Epic: Template Framework Gaps** — i18n is Sprint 3 of that epic; scoped slots (Sprint 1) and error boundaries (Sprint 2) are independent and already partially shipped
- **RFC `rfc-markup-security.md`** — the escaping strategy in `_compile_trans` (Markup wrapping for `%`-formatting) is already correct per the security RFC; no changes needed

---

## Changelog

- **2026-04-10**: All sprints (0–3) implemented and verified. 3299 tests pass (42 new i18n tests).
- **2026-04-10**: Initial draft based on codebase audit + RFC analysis
