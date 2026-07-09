"""Public command-line entry point for Kida.

Command parsing and implementations live in the private :mod:`kida._cli`
package. This facade preserves the documented ``kida.cli:main`` entry point.
Kida intentionally remains argparse-based: adopting ``milo-cli`` would create
a dependency cycle because Milo depends on Kida.
"""

from __future__ import annotations


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``python -m kida`` and the ``kida`` console script."""
    from kida._cli.bootstrap import main as dispatch

    return dispatch(argv)


if __name__ == "__main__":
    raise SystemExit(main())
