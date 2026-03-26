"""Smoke tests for examples/ — ensures each example runs without error.

These are intentionally lightweight: they call each example's main() and
assert it completes without raising.  Output correctness is not checked;
the goal is to catch API breakage early.
"""

import importlib
import sys
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"

# Examples that are safe to run as simple smoke tests (no blocking I/O, no sleeps).
SMOKE_EXAMPLES = [
    "content_stacks",
    "coverage",
    "extensions",
    "sandbox",
    "terminal_basic",
    "terminal_dashboard",
    "terminal_deploy",
    "terminal_gitlog",
    "terminal_layout",
    "terminal_monitor",
    "terminal_render",
    "terminal_report",
    "terminal_table",
]

# terminal_live uses LiveRenderer + time.sleep — excluded from smoke tests.


def _load_example(name: str):
    """Import an example's run module by path."""
    run_path = EXAMPLES_DIR / name / "run.py"
    spec = importlib.util.spec_from_file_location(f"examples.{name}.run", run_path)
    mod = importlib.util.module_from_spec(spec)
    # Temporarily add src/ to path so `import kida` resolves
    src = str(EXAMPLES_DIR.parent / "src")
    old_path = sys.path[:]
    if src not in sys.path:
        sys.path.insert(0, src)
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path[:] = old_path
    return mod


@pytest.mark.parametrize("example", SMOKE_EXAMPLES)
def test_example_runs(example, capsys):
    """Each example's main() should complete without raising."""
    mod = _load_example(example)
    mod.main()
    # Sanity check: most examples produce some output
    captured = capsys.readouterr()
    assert len(captured.out) > 0, f"Example {example!r} produced no output"
