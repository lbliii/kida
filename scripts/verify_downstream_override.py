"""Prove a downstream canary imports Kida from the requested source checkout."""

from __future__ import annotations

import argparse
from pathlib import Path


def verify_source(import_path: Path, checkout: Path) -> Path:
    """Return the resolved import path or raise when it is outside *checkout*."""
    resolved_import = import_path.resolve()
    expected_package = checkout.resolve() / "src" / "kida"
    if not resolved_import.is_relative_to(expected_package):
        raise RuntimeError(
            "downstream canary imported the wrong Kida: "
            f"expected a module below {expected_package}, got {resolved_import}"
        )
    return resolved_import


def main(argv: list[str] | None = None) -> int:
    """Verify the active interpreter's Kida import and print its provenance."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, required=True)
    args = parser.parse_args(argv)

    import kida

    imported_from = verify_source(Path(kida.__file__), args.checkout)
    print(f"verified Kida source override: {imported_from}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
