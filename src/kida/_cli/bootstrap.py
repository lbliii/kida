"""Small, lazy command dispatcher for the public CLI entry point."""

from __future__ import annotations

from importlib import import_module
from types import MappingProxyType
from typing import TYPE_CHECKING, Protocol, cast

from kida._cli.parser import parse_args

if TYPE_CHECKING:
    import argparse
    from collections.abc import Mapping


class _CommandHandler(Protocol):
    def __call__(self, args: argparse.Namespace, /) -> int: ...


_COMMAND_MODULES: Mapping[str, str] = MappingProxyType(
    {
        "check": "kida._cli.check",
        "render": "kida._cli.render",
        "extract": "kida._cli.extract",
        "readme": "kida._cli.readme",
        "components": "kida._cli.components",
        "manifest": "kida._cli.manifest",
        "diff": "kida._cli.diff",
        "fmt": "kida._cli.fmt",
    }
)


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and load only the selected command implementation."""
    args = parse_args(argv)
    module = import_module(_COMMAND_MODULES[args.command])
    handler = cast("_CommandHandler", module.run)
    return handler(args)
