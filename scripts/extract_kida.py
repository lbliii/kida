#!/usr/bin/env python3
"""Extract kida from Bengal to standalone package.

Usage:
    python scripts/extract_kida.py           # Execute extraction
    python scripts/extract_kida.py --dry-run # Preview without writing
    python scripts/extract_kida.py --verify  # Verify extraction succeeded
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

BENGAL_ROOT = Path("/Users/llane/Documents/github/python/bengal")
KIDA_ROOT = Path("/Users/llane/Documents/github/python/kida")

# Import transformations
IMPORT_TRANSFORMS: list[tuple[str, str]] = [
    (r"from bengal\.rendering\.kida\.", "from kida."),
    (r"import bengal\.rendering\.kida\.", "import kida."),
    (r"bengal\.rendering\.kida\.", "kida."),
    (r"from bengal\.utils\.lru_cache", "from kida.utils.lru_cache"),
]

# Files/dirs to skip (empty or not needed)
SKIP_DIRS = {"__pycache__", "optimizer"}


def transform_file(content: str) -> str:
    """Apply all transformations to file content."""
    for pattern, replacement in IMPORT_TRANSFORMS:
        content = re.sub(pattern, replacement, content)
    return content


def should_skip(path: Path) -> bool:
    """Check if path should be skipped."""
    return any(skip in path.parts for skip in SKIP_DIRS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract Kida from Bengal")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--verify", action="store_true", help="Verify extraction")
    args = parser.parse_args()

    if args.verify:
        verify_extraction()
        return

    src_dir = KIDA_ROOT / "src" / "kida"
    test_dir = KIDA_ROOT / "tests"

    if args.dry_run:
        print("🔍 DRY RUN - No files will be written\n")
    else:
        src_dir.mkdir(parents=True, exist_ok=True)
        test_dir.mkdir(parents=True, exist_ok=True)

    stats = {"source": 0, "tests": 0, "skipped": 0, "transforms": 0}

    # 1. Copy and transform source files
    print("📦 Source files:")
    source_src = BENGAL_ROOT / "bengal" / "rendering" / "kida"
    for py_file in sorted(source_src.rglob("*.py")):
        if should_skip(py_file):
            stats["skipped"] += 1
            continue

        rel_path = py_file.relative_to(source_src)
        dest_path = src_dir / rel_path

        content = py_file.read_text()
        transformed = transform_file(content)

        if not args.dry_run:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_text(transformed)

        stats["source"] += 1
        print(f"  ✓ {rel_path}")

    # 2. Copy py.typed marker
    py_typed_src = source_src / "py.typed"
    if py_typed_src.exists():
        if not args.dry_run:
            shutil.copy(py_typed_src, src_dir / "py.typed")
        print("  ✓ py.typed")

    # 3. Copy LRU cache utility
    print("\n📦 Utilities:")
    utils_dir = src_dir / "utils"
    if not args.dry_run:
        utils_dir.mkdir(exist_ok=True)

    lru_cache_src = BENGAL_ROOT / "bengal" / "utils" / "lru_cache.py"
    if lru_cache_src.exists():
        if not args.dry_run:
            content = lru_cache_src.read_text()
            # Update docstring example
            content = content.replace(
                "from bengal.utils.lru_cache import LRUCache",
                "from kida.utils.lru_cache import LRUCache",
            )
            (utils_dir / "lru_cache.py").write_text(content)
            (utils_dir / "__init__.py").write_text(
                '"""Kida utilities."""\n\n'
                "from kida.utils.lru_cache import LRUCache\n\n"
                '__all__ = ["LRUCache"]\n'
            )
        print("  ✓ utils/lru_cache.py")
        print("  ✓ utils/__init__.py")

    # 4. Copy and transform tests
    print("\n🧪 Test files:")
    test_sources = [
        (BENGAL_ROOT / "tests" / "rendering" / "kida", test_dir),
        (BENGAL_ROOT / "tests" / "unit" / "rendering" / "kida", test_dir / "unit"),
        (BENGAL_ROOT / "tests" / "kida", test_dir / "misc"),
    ]

    for source_dir_path, dest_base in test_sources:
        if not source_dir_path.exists():
            continue
        for py_file in sorted(source_dir_path.rglob("*.py")):
            if should_skip(py_file):
                stats["skipped"] += 1
                continue

            rel_path = py_file.relative_to(source_dir_path)
            dest_path = dest_base / rel_path

            content = py_file.read_text()
            transformed = transform_file(content)

            if not args.dry_run:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                dest_path.write_text(transformed)

            stats["tests"] += 1
            print(f"  ✓ {dest_base.name}/{rel_path}")

    # 5. Copy standalone tests
    standalone_tests = [
        BENGAL_ROOT / "tests" / "unit" / "rendering" / "test_kida_thread_safety.py",
        BENGAL_ROOT / "tests" / "unit" / "rendering" / "test_template_cycles.py",
    ]
    for test_file in standalone_tests:
        if test_file.exists():
            content = test_file.read_text()
            transformed = transform_file(content)
            if not args.dry_run:
                (test_dir / test_file.name).write_text(transformed)
            stats["tests"] += 1
            print(f"  ✓ {test_file.name}")

    # Summary
    print(f"\n{'📋 DRY RUN SUMMARY' if args.dry_run else '✅ EXTRACTION COMPLETE'}")
    print(f"   Source files: {stats['source']}")
    print(f"   Test files:   {stats['tests']}")
    print(f"   Skipped:      {stats['skipped']}")

    if not args.dry_run:
        print(f"\n📍 Extracted to: {KIDA_ROOT}")
        print("\n🚀 Next steps:")
        print("   1. cd kida && uv sync")
        print("   2. pytest")
        print("   3. pyright src/")
        print("   4. python scripts/extract_kida.py --verify")


def verify_extraction() -> None:
    """Verify extraction succeeded."""
    print("🔍 Verifying extraction...\n")
    errors: list[str] = []

    src_dir = KIDA_ROOT / "src" / "kida"

    # Check for Bengal imports
    for py_file in src_dir.rglob("*.py"):
        content = py_file.read_text()
        if "from bengal" in content or "import bengal" in content:
            rel_path = py_file.relative_to(KIDA_ROOT)
            errors.append(f"Bengal import found in {rel_path}")

    # Check key files exist
    required = [
        src_dir / "__init__.py",
        src_dir / "py.typed",
        src_dir / "environment" / "core.py",
        src_dir / "utils" / "lru_cache.py",
    ]
    for path in required:
        if not path.exists():
            errors.append(f"Missing required file: {path.relative_to(KIDA_ROOT)}")

    if errors:
        print("❌ Verification failed:")
        for error in errors:
            print(f"   • {error}")
        sys.exit(1)
    else:
        print("✅ Verification passed!")
        print("   • No Bengal imports found")
        print("   • All required files present")


if __name__ == "__main__":
    main()
