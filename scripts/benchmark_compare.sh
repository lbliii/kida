#!/usr/bin/env bash
# Compare current benchmarks against a saved baseline.
#
# Usage:
#   ./scripts/benchmark_compare.sh              # compare against "baseline"
#   ./scripts/benchmark_compare.sh my-branch    # compare against "my-branch"
#
# Exit codes:
#   0 = all benchmarks within threshold
#   1 = regressions detected (slower than threshold)
#   2 = baseline not found
#
# This script is designed for CI integration. It runs the selected benchmark
# suite, compares against a saved baseline, and fails if any benchmark exceeds
# the regression threshold.
#
# High-variance benchmarks are excluded from regression checks by default.
# Override with BENCHMARK_INCLUDE_ALL=1 to include them.
#
# Prerequisites:
#   - A baseline must exist in benchmarks/ (run benchmark_baseline.sh first)
#   - pytest-benchmark must be installed

set -euo pipefail

BASELINE="${1:-baseline}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BENCHMARK_DIR="${BENCHMARK_STORAGE_DIR:-$PROJECT_DIR/benchmarks}"
STORAGE="file://$BENCHMARK_DIR"
SUITE="${BENCHMARK_SUITE:-core}"
COMPARE_STAT="${BENCHMARK_COMPARE_STAT:-median}"

# shellcheck source=benchmark_suites.sh
source "$SCRIPT_DIR/benchmark_suites.sh"
if ! SUITE_DESCRIPTION=$(benchmark_suite_description "$SUITE"); then
    echo "ERROR: Unknown benchmark suite '$SUITE'"
    echo "Known suites: $(benchmark_suite_names)"
    exit 2
fi
BENCHMARK_FILES=()
while IFS= read -r benchmark_file; do
    BENCHMARK_FILES+=("$benchmark_file")
done < <(benchmark_files_for_suite "$PROJECT_DIR" "$SUITE")

# Regression threshold: CI uses 20% (shared runners, 4 cores); local uses 15%
# Override with BENCHMARK_REGRESSION_THRESHOLD=25
if [ -n "${BENCHMARK_REGRESSION_THRESHOLD:-}" ]; then
    THRESHOLD="$BENCHMARK_REGRESSION_THRESHOLD"
elif [ "${CI:-}" = "true" ]; then
    THRESHOLD="20"
else
    THRESHOLD="15"
fi

EXCLUDE_K=$(benchmark_exclude_for_suite "$SUITE")

echo "=== Kida Benchmark Regression Check ==="
echo "Baseline: $BASELINE"
echo "Suite: $SUITE ($SUITE_DESCRIPTION)"
echo "Threshold: ${THRESHOLD}% regression"
echo "Compare stat: $COMPARE_STAT"
echo "Storage: $STORAGE"
echo "Python: $(python --version 2>&1)"
echo "Date: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
if [ "${BENCHMARK_INCLUDE_ALL:-0}" != "1" ] && [ -n "$EXCLUDE_K" ]; then
    echo "Filter: $EXCLUDE_K"
fi
echo ""

# Check baseline exists for current platform (pytest-benchmark uses platform-specific dirs)
PLATFORM_DIR=$(python -c "from pytest_benchmark.utils import get_machine_id; print(get_machine_id())")
# find exits 1 when path doesn't exist; avoid triggering set -e so we can handle gracefully
BASELINE_FILE=""
if [ -d "$BENCHMARK_DIR/$PLATFORM_DIR" ]; then
    BASELINE_FILE=$(find "$BENCHMARK_DIR/$PLATFORM_DIR" -name "*_${BASELINE}.json" -not -name "*_comparison*" 2>/dev/null | sort | tail -1)
fi
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
# Keep compare settings aligned with benchmark_baseline.sh to avoid artificial drift.
echo "--- Running benchmarks ---"
if [ "${BENCHMARK_INCLUDE_ALL:-0}" = "1" ] || [ -z "$EXCLUDE_K" ]; then
    python -m pytest "${BENCHMARK_FILES[@]}" \
        --benchmark-only \
        --benchmark-compare="*_${BASELINE}" \
        --benchmark-compare-fail="${COMPARE_STAT}:${THRESHOLD}%" \
        --benchmark-storage="$STORAGE" \
        --benchmark-min-rounds=10 \
        -q
else
    python -m pytest "${BENCHMARK_FILES[@]}" \
        -k "$EXCLUDE_K" \
        --benchmark-only \
        --benchmark-compare="*_${BASELINE}" \
        --benchmark-compare-fail="${COMPARE_STAT}:${THRESHOLD}%" \
        --benchmark-storage="$STORAGE" \
        --benchmark-min-rounds=10 \
        -q
fi
