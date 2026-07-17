"""Shared parsing for explicit namespaced template roots."""

from __future__ import annotations

import argparse
from pathlib import Path

from kida.inspection import TemplateRoot


def parse_template_root(value: str) -> TemplateRoot:
    """Parse ``NAMESPACE=PATH`` without ambient path discovery."""
    namespace, separator, raw_path = value.partition("=")
    if not separator or not raw_path:
        raise argparse.ArgumentTypeError("root must use NAMESPACE=PATH")
    try:
        return TemplateRoot(namespace=namespace, path=Path(raw_path))
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
