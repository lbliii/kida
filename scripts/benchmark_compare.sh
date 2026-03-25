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
# This script is designed for CI integration. It runs the render and full
# comparison benchmark suites, compares against a saved baseline, and fails
# if any benchmark exceeds the regression threshold.
#
# High-variance benchmarks (async, complex inheritance) are excluded from
# regression checks—CI runners (4 cores) differ from dev machines, causing
# noisy comparisons. Override with BENCHMARK_INCLUDE_ALL=1 to include them.
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

# Regression threshold: CI uses 20% (shared runners, 4 cores); local uses 15%
# Override with BENCHMARK_REGRESSION_THRESHOLD=25
if [ -n "${BENCHMARK_REGRESSION_THRESHOLD:-}" ]; then
    THRESHOLD="$BENCHMARK_REGRESSION_THRESHOLD"
elif [ "${CI:-}" = "true" ]; then
    THRESHOLD="20"
else
    THRESHOLD="15"
fi

# Exclude high-variance benchmarks from regression (async + complex inheritance + include depth + compile:complex)
# These have StdDev ~50-100% of mean on shared CI runners; include_depth[1] is especially noisy.
# compile_complex (~3ms) fluctuates 30-40% on shared 4-core runners due to cold-cache effects.
EXCLUDE_K="not (test_render_async_medium_kida or test_render_async_large_kida or test_render_complex_kida or test_render_complex_jinja2 or test_include_depth_scaling or test_compile_complex_kida or test_compile_complex_jinja2)"

echo "=== Kida Benchmark Regression Check ==="
echo "Baseline: $BASELINE"
echo "Threshold: ${THRESHOLD}% regression"
echo "Storage: $STORAGE"
echo "Python: $(python --version 2>&1)"
echo "Date: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
if [ "${BENCHMARK_INCLUDE_ALL:-0}" != "1" ]; then
    echo "Excluded (high variance): async_medium, async_large, render_complex, compile_complex (kida+jinja2), include_depth_scaling"
fi
echo ""

# Check baseline exists for current platform (pytest-benchmark uses platform-specific dirs)
PLATFORM_DIR=$(python -c "from pytest_benchmark.utils import get_machine_id; print(get_machine_id())")
# find exits 1 when path doesn't exist; avoid triggering set -e so we can handle gracefully
BASELINE_FILE=""
if [ -d "$BENCHMARK_DIR/$PLATFORM_DIR" ]; then
    BASELINE_FILE=$(find "$BENCHMARK_DIR/$PLATFORM_DIR" -name "*_${BASELINE}.json" -not -name "*_comparison*" 2>/dev/null | head -1)
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
# Benchmark suite must stay in sync with benchmark_baseline.sh.
echo "--- Running benchmarks ---"
BENCHMARK_FILES=(
    "$PROJECT_DIR/benchmarks/test_benchmark_render.py"
    "$PROJECT_DIR/benchmarks/test_benchmark_full_comparison.py"
    "$PROJECT_DIR/benchmarks/test_benchmark_features.py"
    "$PROJECT_DIR/benchmarks/test_benchmark_introspection.py"
    "$PROJECT_DIR/benchmarks/test_benchmark_include_depth.py"
    "$PROJECT_DIR/benchmarks/test_benchmark_inherited_blocks.py"
    "$PROJECT_DIR/benchmarks/test_benchmark_output_sanity.py"
)
if [ "${BENCHMARK_INCLUDE_ALL:-0}" = "1" ]; then
    python -m pytest "${BENCHMARK_FILES[@]}" \
        --benchmark-only \
        --benchmark-compare="*_${BASELINE}" \
        --benchmark-compare-fail="mean:${THRESHOLD}%" \
        --benchmark-storage="$STORAGE" \
        --benchmark-min-rounds=10 \
        -q
else
    python -m pytest "${BENCHMARK_FILES[@]}" \
        -k "$EXCLUDE_K" \
        --benchmark-only \
        --benchmark-compare="*_${BASELINE}" \
        --benchmark-compare-fail="mean:${THRESHOLD}%" \
        --benchmark-storage="$STORAGE" \
        --benchmark-min-rounds=10 \
        -q
fi
