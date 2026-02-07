"""Filter and test registry for Kida environment.

Provides dict-like interface for filters and tests.
"""

from __future__ import annotations

from collections.abc import Callable, ItemsView, KeysView, ValuesView
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kida.environment.core import Environment


class FilterRegistry:
    """Dict-like interface for filters/tests that matches Jinja2's API.

    Supports:
        - env.filters['name'] = func
        - env.filters.update({'name': func})
        - func = env.filters['name']
        - 'name' in env.filters

    All mutations use copy-on-write for thread-safety.

    """

    __slots__ = ("_attr", "_env")

    def __init__(self, env: Environment, attr: str) -> None:
        self._env = env
        self._attr = attr

    def _get_dict(self) -> dict[str, Callable[..., Any]]:
        result: dict[str, Callable[..., Any]] = getattr(self._env, self._attr)
        return result

    def _set_dict(self, d: dict[str, Callable[..., Any]]) -> None:
        setattr(self._env, self._attr, d)

    def __getitem__(self, name: str) -> Callable[..., Any]:
        return self._get_dict()[name]

    def __setitem__(self, name: str, func: Callable[..., Any]) -> None:
        new = self._get_dict().copy()
        new[name] = func
        self._set_dict(new)

    def __contains__(self, name: object) -> bool:
        return name in self._get_dict()

    def get(
        self, name: str, default: Callable[..., Any] | None = None
    ) -> Callable[..., Any] | None:
        return self._get_dict().get(name, default)

    def update(self, mapping: dict[str, Callable[..., Any]]) -> None:
        """Batch update filters."""
        new = self._get_dict().copy()
        new.update(mapping)
        self._set_dict(new)

    def copy(self) -> dict[str, Callable[..., Any]]:
        """Return a copy of the underlying dict."""
        return self._get_dict().copy()

    def keys(self) -> KeysView[str]:
        return self._get_dict().keys()

    def values(self) -> ValuesView[Callable[..., Any]]:
        return self._get_dict().values()

    def items(self) -> ItemsView[str, Callable[..., Any]]:
        return self._get_dict().items()
