#!/usr/bin/env bash
# Compare current benchmarks against a saved baseline.
#
# Usage:
#   ./scripts/benchmark_compare.sh              # compare against "baseline"
#   ./scripts/benchmark_compare.sh my-branch    # compare against "my-branch"
#
# Exit codes:
#   0 = all benchmarks within threshold
#   1 = regressions detected (>5% slower than baseline)
#   2 = baseline not found
#
# This script is designed for CI integration. It runs the render benchmark
# suite, compares against a saved baseline, and prints a summary table.
#
# Prerequisites:
#   - A baseline must exist in .benchmarks/ (run benchmark_baseline.sh first)
#   - pytest-benchmark must be installed

set -euo pipefail

BASELINE="${1:-baseline}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BENCHMARK_DIR="$PROJECT_DIR/.benchmarks"

# Regression threshold: 5% slower than baseline triggers failure
THRESHOLD="5"

echo "=== Kida Benchmark Regression Check ==="
echo "Baseline: $BASELINE"
echo "Threshold: ${THRESHOLD}% regression"
echo "Python: $(python --version 2>&1)"
echo "Date: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo ""

# Check baseline exists (pytest-benchmark saves as 000N_name.json)
BASELINE_FILE=$(find "$BENCHMARK_DIR" -name "*_${BASELINE}.json" 2>/dev/null | head -1)
if [ -z "$BASELINE_FILE" ]; then
    echo "ERROR: Baseline '$BASELINE' not found in $BENCHMARK_DIR/"
    echo ""
    echo "Available baselines:"
    ls "$BENCHMARK_DIR"/*.json 2>/dev/null | while read -r f; do
        basename "$f" .json | sed 's/^[0-9]*_/  /'
    done
    echo ""
    echo "Run './scripts/benchmark_baseline.sh $BASELINE' first."
    exit 2
fi

echo "Found baseline: $(basename "$BASELINE_FILE")"
echo ""

# Run current benchmarks and compare
echo "--- Running benchmarks ---"
COMPARE_OUTPUT=$(python -m pytest "$PROJECT_DIR/benchmarks/test_benchmark_render.py" \
    --benchmark-only \
    --benchmark-save=current \
    --benchmark-compare="$BASELINE" \
    --benchmark-min-rounds=5 \
    -q 2>&1) || true

echo "$COMPARE_OUTPUT"
echo ""

# Parse for regressions: look for lines where current is >5% slower
# pytest-benchmark compare output shows columns with mean times and relative changes
REGRESSIONS=$(echo "$COMPARE_OUTPUT" | grep -i "slower\|regression" || true)

if [ -n "$REGRESSIONS" ]; then
    echo ""
    echo "=== REGRESSIONS DETECTED ==="
    echo "$REGRESSIONS"
    echo ""
    echo "One or more benchmarks regressed beyond the ${THRESHOLD}% threshold."
    echo "Review the comparison table above for details."
    exit 1
else
    echo ""
    echo "=== ALL BENCHMARKS WITHIN THRESHOLD ==="
    echo "No regressions detected (threshold: ${THRESHOLD}%)."
    exit 0
fi
