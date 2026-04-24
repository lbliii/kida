#!/usr/bin/env bash
# Save a clean benchmark baseline snapshot.
#
# Usage:
#   ./scripts/benchmark_baseline.sh                        # save core suite as "baseline"
#   ./scripts/benchmark_baseline.sh my-branch              # save core suite as "my-branch"
#   BENCHMARK_SUITE=product ./scripts/benchmark_baseline.sh docs
#
# To compare against baseline later:
#   BENCHMARK_SUITE=core ./scripts/benchmark_compare.sh
#
# The baseline is stored in benchmarks/ (committed) for CI regression detection.

set -euo pipefail

NAME="${1:-baseline}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
STORAGE_DIR="${BENCHMARK_STORAGE_DIR:-$PROJECT_DIR/benchmarks}"
STORAGE="file://$STORAGE_DIR"
SUITE="${BENCHMARK_SUITE:-core}"

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

echo "=== Kida Benchmark Baseline ==="
echo "Name:    $NAME"
echo "Suite:   $SUITE ($SUITE_DESCRIPTION)"
echo "Storage: $STORAGE"
echo "Python:  $(python --version 2>&1)"
echo "Date:    $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo ""

mkdir -p "$STORAGE_DIR"

# Clean stale baseline files if saving as "baseline"
if [ "$NAME" = "baseline" ]; then
    find "$STORAGE_DIR" -mindepth 2 -maxdepth 2 \
        -type f -name "*_${NAME}.json" -exec rm -f {} + 2>/dev/null || true
    echo "Cleaned stale baseline files in $STORAGE_DIR."
    echo ""
fi

# Run the selected suite (must match benchmark_compare.sh)
echo "--- Running benchmark suite ---"
python -m pytest "${BENCHMARK_FILES[@]}" \
    --benchmark-only \
    --benchmark-save="$NAME" \
    --benchmark-storage="$STORAGE" \
    --benchmark-min-rounds=10 \
    -q

echo ""
echo "=== Baseline '$NAME' saved to benchmarks/ ==="
echo ""
echo "To compare later:"
echo "  BENCHMARK_SUITE=$SUITE ./scripts/benchmark_compare.sh $NAME"
