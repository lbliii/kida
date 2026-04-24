#!/usr/bin/env bash
# Save a clean benchmark baseline snapshot.
#
# Usage:
#   ./scripts/benchmark_baseline.sh              # save as "baseline"
#   ./scripts/benchmark_baseline.sh my-branch    # save as "my-branch"
#
# To compare against baseline later:
#   pytest benchmarks/test_benchmark_render.py benchmarks/test_benchmark_full_comparison.py \\
#     --benchmark-only --benchmark-compare=baseline --benchmark-storage=file://benchmarks/
#
# The baseline is stored in benchmarks/ (committed) for CI regression detection.

set -euo pipefail

NAME="${1:-baseline}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
STORAGE="file://$PROJECT_DIR/benchmarks"

echo "=== Kida Benchmark Baseline ==="
echo "Name:    $NAME"
echo "Storage: $STORAGE"
echo "Python:  $(python --version 2>&1)"
echo "Date:    $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo ""

# Clean stale baseline files if saving as "baseline"
if [ "$NAME" = "baseline" ]; then
    rm -f "$PROJECT_DIR/benchmarks"/*_"$NAME"*.json 2>/dev/null || true
    echo "Cleaned stale baseline files in benchmarks/."
    echo ""
fi

# Run the full regression suite (must match benchmark_compare.sh)
echo "--- Running benchmark suite ---"
python -m pytest \
    "$PROJECT_DIR/benchmarks/test_benchmark_render.py" \
    "$PROJECT_DIR/benchmarks/test_benchmark_full_comparison.py" \
    "$PROJECT_DIR/benchmarks/test_benchmark_features.py" \
    "$PROJECT_DIR/benchmarks/test_benchmark_introspection.py" \
    "$PROJECT_DIR/benchmarks/test_benchmark_include_depth.py" \
    "$PROJECT_DIR/benchmarks/test_benchmark_inherited_blocks.py" \
    "$PROJECT_DIR/benchmarks/test_benchmark_output_sanity.py" \
    "$PROJECT_DIR/benchmarks/test_benchmark_regression_core.py" \
    --benchmark-only \
    --benchmark-save="$NAME" \
    --benchmark-storage="$STORAGE" \
    --benchmark-min-rounds=10 \
    -q

echo ""
echo "=== Baseline '$NAME' saved to benchmarks/ ==="
echo ""
echo "To compare later:"
echo "  pytest benchmarks/test_benchmark_render.py benchmarks/test_benchmark_full_comparison.py \\"
echo "    --benchmark-only --benchmark-compare=$NAME --benchmark-storage=$STORAGE"
