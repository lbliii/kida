"""Type aliases for Kida template contracts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

BlockCallable = Callable[[dict[str, Any], dict[str, Any] | None], str]
BlocksDict = dict[str, BlockCallable]
