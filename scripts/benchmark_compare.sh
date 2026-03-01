#!/usr/bin/env bash
# Compare current benchmarks against a saved baseline.
#
# Usage:
#   ./scripts/benchmark_compare.sh              # compare against "baseline"
#   ./scripts/benchmark_compare.sh my-branch    # compare against "my-branch"
#
# Exit codes:
#   0 = all benchmarks within threshold
#   1 = regressions detected (>10% slower than baseline)
#   2 = baseline not found
#
# This script is designed for CI integration. It runs the render and full
# comparison benchmark suites, compares against a saved baseline, and fails
# if any benchmark is >10% slower.
#
# Prerequisites:
#   - A baseline must exist in benchmarks/ (run benchmark_baseline.sh first)
#   - pytest-benchmark must be installed

set -euo pipefail

BASELINE="${1:-baseline}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BENCHMARK_DIR="$PROJECT_DIR/benchmarks"
STORAGE="file://$PROJECT_DIR/benchmarks"

# Regression threshold: 10% slower than baseline triggers failure (matches CI)
THRESHOLD="10"

echo "=== Kida Benchmark Regression Check ==="
echo "Baseline: $BASELINE"
echo "Threshold: ${THRESHOLD}% regression"
echo "Storage: $STORAGE"
echo "Python: $(python --version 2>&1)"
echo "Date: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo ""

# Check baseline exists for current platform (pytest-benchmark uses platform-specific dirs)
PLATFORM_DIR=$(python -c "from pytest_benchmark.utils import get_machine_id; print(get_machine_id())")
BASELINE_FILE=$(find "$BENCHMARK_DIR/$PLATFORM_DIR" -name "*_${BASELINE}.json" -not -name "*_comparison*" 2>/dev/null | head -1)
if [ -z "$BASELINE_FILE" ]; then
    echo "ERROR: Baseline '$BASELINE' not found for platform $PLATFORM_DIR"
    echo "       (pytest-benchmark stores baselines in benchmarks/<platform>/)"
    echo ""
    echo "Available baselines:"
    find "$BENCHMARK_DIR" -name "*_${BASELINE}.json" 2>/dev/null | while read -r f; do
        echo "  $f"
    done
    echo ""
    echo "Run './scripts/benchmark_baseline.sh' on this platform, or use the"
    echo "'Benchmark baseline' workflow (Actions → Run workflow) for Linux CI."
    exit 2
fi

echo "Found baseline: $(basename "$BASELINE_FILE")"
echo ""

# Run current benchmarks and compare (use --benchmark-compare-fail for hard failure)
# pytest-benchmark saves as 0001_${name}.json; compare pattern must be *_${name} to match
echo "--- Running benchmarks ---"
python -m pytest \
    "$PROJECT_DIR/benchmarks/test_benchmark_render.py" \
    "$PROJECT_DIR/benchmarks/test_benchmark_full_comparison.py" \
    --benchmark-only \
    --benchmark-compare="*_${BASELINE}" \
    --benchmark-compare-fail="mean:${THRESHOLD}%" \
    --benchmark-storage="$STORAGE" \
    --benchmark-min-rounds=5 \
    -q
