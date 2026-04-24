#!/usr/bin/env bash
# Shared benchmark suite definitions for baseline and regression scripts.

benchmark_suite_description() {
    case "$1" in
        core)
            echo "CI regression probes: batched Kida hot paths, compile pipeline, output sanity"
            ;;
        product)
            echo "Documentation/product comparison: render, feature, inheritance, and parity-facing probes"
            ;;
        exploratory)
            echo "Human profiling sweep: all benchmark test modules, including optional comparisons"
            ;;
        *)
            return 1
            ;;
    esac
}

benchmark_files_for_suite() {
    local project_dir="$1"
    local suite="$2"

    case "$suite" in
        core)
            printf '%s\n' \
                "$project_dir/benchmarks/test_benchmark_regression_core.py" \
                "$project_dir/benchmarks/test_benchmark_compile_pipeline.py" \
                "$project_dir/benchmarks/test_benchmark_output_sanity.py"
            ;;
        product)
            printf '%s\n' \
                "$project_dir/benchmarks/test_benchmark_render.py" \
                "$project_dir/benchmarks/test_benchmark_full_comparison.py" \
                "$project_dir/benchmarks/test_benchmark_features.py" \
                "$project_dir/benchmarks/test_benchmark_introspection.py" \
                "$project_dir/benchmarks/test_benchmark_include_depth.py" \
                "$project_dir/benchmarks/test_benchmark_inherited_blocks.py" \
                "$project_dir/benchmarks/test_benchmark_output_sanity.py" \
                "$project_dir/benchmarks/test_benchmark_regression_core.py"
            ;;
        exploratory)
            find "$project_dir/benchmarks" -maxdepth 1 -name 'test_benchmark_*.py' | sort
            ;;
        *)
            return 1
            ;;
    esac
}

benchmark_exclude_for_suite() {
    case "$1" in
        core)
            # These tiny output-sanity probes are useful for humans, but too
            # sensitive to shared-runner clock jitter to gate CI reliably.
            echo "not (test_benchmark_inherited_blocks_output_not_duplicated or test_benchmark_include_depth_output_count_matches_include_count)"
            ;;
        product)
            echo "not (_jinja2 or test_render_async_medium_kida or test_render_async_large_kida or test_render_complex_kida or test_include_depth_scaling or test_compile_complex_kida or test_compile_small_kida or test_render_fragment_cache_cold_kida or test_render_fragment_cache_kida or test_benchmark_inherited_render_block or test_benchmark_inherited_list_blocks or test_benchmark_inherited_blocks_output_not_duplicated or test_benchmark_include_depth_output_count_matches_include_count or test_load_from_bytecode_cache_kida or test_match_first_case_kida or test_match_middle_case_kida or test_match_default_case_kida)"
            ;;
        exploratory)
            echo ""
            ;;
        *)
            return 1
            ;;
    esac
}

benchmark_suite_names() {
    echo "core, product, exploratory"
}
