# Downstream Canary Contract

Status: report-only Phase 1

Tracking: [GitHub issue #164](https://github.com/lbliii/kida/issues/164)

## Purpose

Kida's internal suite proves isolated compiler and runtime contracts. Downstream
canaries prove that a proposed Kida checkout still composes with real template
corpora and non-HTML consumers before high-risk work is merged. They are
necessary evidence, not a replacement for Kida's own tests, differential checks,
or benchmarks.

## Phase 1 Matrix

| Consumer | Surface | Command | Contracts covered |
|---|---|---|---|
| `lbliii/chirp-ui` | HTML/components | `pytest tests/ -x -q` | defs, calls, named/scoped slots, provide/consume, regions, filters, metadata, packaged templates |
| `lbliii/milo-cli` | terminal/CLI | `pytest -q` | terminal autoescape, ANSI/width helpers, template-driven CLI output, packaged `.kida` components |

The workflow runs on pull requests, pushes to `main`, a weekly schedule, and
manual dispatch. Both jobs are report-only (`continue-on-error: true`) and use
only `contents: read`; they do not consume secrets, so public-fork pull requests
exercise the same public repositories safely.

## Source Override Proof

Each job checks out Kida and the downstream repository into separate paths,
creates the downstream's own development environment, and then installs the
current Kida checkout editable with `--no-deps`. All test commands use
`uv run --no-sync`, preventing a later dependency sync from silently restoring
the released `kida-templates` wheel.

Before tests run, `scripts/verify_downstream_override.py` imports Kida with the
downstream interpreter and requires `kida.__file__` to resolve below the checked
out `kida/src/kida` directory. A PyPI or unrelated workspace import fails with a
direct provenance error. The job summary records both repository commits and
the Python/GIL mode.

## Failure Protocol

1. Re-run the failed downstream job and inspect the raw pytest output.
2. Verify the source-override step passed; a wrong import is infrastructure
   failure, not downstream incompatibility.
3. Reproduce against Kida `main` and the downstream's recorded commit.
4. If only the proposed Kida change fails, fix Kida or explicitly coordinate an
   intentional downstream change before merging. Never refresh snapshots merely
   to make the canary green.
5. Record genuine downstream flakiness separately; report-only status must not
   become a reason to ignore a deterministic regression.

High-risk compiler issue #144 requires both Phase 1 canaries green before and
after each slice even while the GitHub check remains technically non-required.

## Promotion And Known Gaps

Promotion to a required check is a separate CI-policy decision. Consider it
only after at least ten consecutive relevant green runs spanning fourteen days,
with documented runtime and flake behavior.

Deferred work:

- private Furatena checks need trusted-branch credentials and explicit
  skip-safe behavior;
- Chirp and Purr add framework/Markdown breadth after the first matrix is stable;
- reverse scheduled canaries belong in downstream repositories and require
  separate repository authorization;
- no single consumer covers source mapping, every render mode, sandbox policy,
  or performance, so Kida's internal gates remain authoritative.
