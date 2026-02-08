#!/usr/bin/env bash
# Save a clean benchmark baseline snapshot.
#
# Usage:
#   ./scripts/benchmark_baseline.sh              # save as "baseline"
#   ./scripts/benchmark_baseline.sh my-branch    # save as "my-branch"
#
# To compare against baseline later:
#   pytest benchmarks/test_benchmark_render.py --benchmark-only \
#     --benchmark-save=current --benchmark-compare=baseline
#
# The results are stored in .benchmarks/ (gitignored).

set -euo pipefail

NAME="${1:-baseline}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Kida Benchmark Baseline ==="
echo "Name:    $NAME"
echo "Python:  $(python --version 2>&1)"
echo "Date:    $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo ""

# Clean stale data if saving as "baseline"
if [ "$NAME" = "baseline" ]; then
    rm -f "$PROJECT_DIR/.benchmarks"/*.json
    echo "Cleaned stale .benchmarks/*.json files."
    echo ""
fi

# Run the render benchmarks (single-threaded, primary perf metric)
echo "--- Running render benchmarks ---"
python -m pytest "$PROJECT_DIR/benchmarks/test_benchmark_render.py" \
    --benchmark-only \
    --benchmark-save="$NAME" \
    --benchmark-min-rounds=10 \
    -q

echo ""
echo "--- Running full comparison benchmarks ---"
python -m pytest "$PROJECT_DIR/benchmarks/test_benchmark_full_comparison.py" \
    --benchmark-only \
    --benchmark-save="${NAME}_comparison" \
    --benchmark-min-rounds=5 \
    -q

echo ""
echo "=== Baseline '$NAME' saved to .benchmarks/ ==="
echo ""
echo "To compare later:"
echo "  pytest benchmarks/test_benchmark_render.py --benchmark-only \\"
echo "    --benchmark-save=current --benchmark-compare=$NAME"
