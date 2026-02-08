"""Loop iteration metadata for Kida ``{% for %}`` and ``{% async for %}`` blocks."""

from __future__ import annotations

from typing import Any, NoReturn


class LoopContext:
    """Loop iteration metadata accessible as `loop` inside `{% for %}` blocks.

    Provides index tracking, boundary detection, and utility methods for
    common iteration patterns. All properties are computed on-access.

    Properties:
        index: 1-based iteration count (1, 2, 3, ...)
        index0: 0-based iteration count (0, 1, 2, ...)
        first: True on the first iteration
        last: True on the final iteration
        length: Total number of items in the sequence
        revindex: Reverse 1-based index (counts down to 1)
        revindex0: Reverse 0-based index (counts down to 0)
        previtem: Previous item in sequence (None on first)
        nextitem: Next item in sequence (None on last)

    Methods:
        cycle(*values): Return values[index % len(values)]

    Example:
            ```jinja
            <ul>
            {% for item in items %}
                <li class="{{ loop.cycle('odd', 'even') }}">
                    {{ loop.index }}/{{ loop.length }}: {{ item }}
                    {% if loop.first %}← First{% endif %}
                    {% if loop.last %}← Last{% endif %}
                </li>
            {% end %}
            </ul>
            ```

    Output:
            ```html
            <ul>
                <li class="odd">1/3: Apple ← First</li>
                <li class="even">2/3: Banana</li>
                <li class="odd">3/3: Cherry ← Last</li>
            </ul>
            ```

    """

    __slots__ = ("_index", "_items", "_length")

    def __init__(self, items: list[Any]) -> None:
        self._items = items
        self._length = len(items)
        self._index = 0

    def __iter__(self) -> Any:
        """Iterate through items, updating index for each."""
        for i, item in enumerate(self._items):
            self._index = i
            yield item

    @property
    def index(self) -> int:
        """1-based iteration count."""
        return self._index + 1

    @property
    def index0(self) -> int:
        """0-based iteration count."""
        return self._index

    @property
    def first(self) -> bool:
        """True if this is the first iteration."""
        return self._index == 0

    @property
    def last(self) -> bool:
        """True if this is the last iteration."""
        return self._index == self._length - 1

    @property
    def length(self) -> int:
        """Total number of items in the sequence."""
        return self._length

    @property
    def revindex(self) -> int:
        """Reverse 1-based index (counts down to 1)."""
        return self._length - self._index

    @property
    def revindex0(self) -> int:
        """Reverse 0-based index (counts down to 0)."""
        return self._length - self._index - 1

    @property
    def previtem(self) -> Any:
        """Previous item in the sequence, or None if first."""
        if self._index == 0:
            return None
        return self._items[self._index - 1]

    @property
    def nextitem(self) -> Any:
        """Next item in the sequence, or None if last."""
        if self._index >= self._length - 1:
            return None
        return self._items[self._index + 1]

    def cycle(self, *values: Any) -> Any:
        """Cycle through the given values.

        Example:
            {{ loop.cycle('odd', 'even') }}
        """
        if not values:
            return None
        return values[self._index % len(values)]

    def __repr__(self) -> str:
        return f"<LoopContext {self.index}/{self.length}>"


def _async_loop_unavailable(name: str) -> NoReturn:
    """Raise TemplateRuntimeError for size-dependent loop variables in async for."""
    from kida.environment.exceptions import TemplateRuntimeError

    raise TemplateRuntimeError(
        f"'loop.{name}' is not available in async for-loops "
        f"(requires knowing total size). "
        f"Use {{% for %}} for size-dependent loop variables.",
    )


class AsyncLoopContext:
    """Loop iteration metadata for ``{% async for %}`` blocks.

    Provides index-forward variables only. Size-dependent variables
    (``last``, ``length``, ``revindex``, ``revindex0``, ``nextitem``)
    raise ``TemplateRuntimeError`` because async iterables cannot be
    pre-materialized without defeating the purpose of lazy streaming.

    The async for-loop drives iteration externally — this class does not
    implement ``__aiter__``. Instead, ``advance(item)`` is called at the
    top of each loop iteration by the compiled code.

    Properties:
        index: 1-based iteration count (1, 2, 3, ...)
        index0: 0-based iteration count (0, 1, 2, ...)
        first: True on the first iteration
        previtem: Previous item in sequence (None on first)

    Methods:
        cycle(*values): Return values[index % len(values)]
        advance(item): Update state for current iteration (called by compiled code)

    Part of RFC: rfc-async-rendering.
    """

    __slots__ = ("_current", "_index", "_prev")

    def __init__(self) -> None:
        self._index = -1  # incremented to 0 on first advance()
        self._current: Any = None
        self._prev: Any = None

    def advance(self, item: Any) -> None:
        """Update loop state for the current iteration.

        Called by compiled async for-loop code at the top of each iteration,
        before the loop body executes.
        """
        self._prev = self._current
        self._current = item
        self._index += 1

    @property
    def index(self) -> int:
        """1-based iteration count."""
        return self._index + 1

    @property
    def index0(self) -> int:
        """0-based iteration count."""
        return self._index

    @property
    def first(self) -> bool:
        """True if this is the first iteration."""
        return self._index == 0

    @property
    def last(self) -> bool:
        """Not available in async for-loops."""
        _async_loop_unavailable("last")

    @property
    def length(self) -> int:
        """Not available in async for-loops."""
        _async_loop_unavailable("length")

    @property
    def revindex(self) -> int:
        """Not available in async for-loops."""
        _async_loop_unavailable("revindex")

    @property
    def revindex0(self) -> int:
        """Not available in async for-loops."""
        _async_loop_unavailable("revindex0")

    @property
    def previtem(self) -> Any:
        """Previous item in the sequence, or None if first."""
        if self._index <= 0:
            return None
        return self._prev

    @property
    def nextitem(self) -> Any:
        """Not available in async for-loops."""
        _async_loop_unavailable("nextitem")

    def cycle(self, *values: Any) -> Any:
        """Cycle through the given values.

        Example:
            {{ loop.cycle('odd', 'even') }}
        """
        if not values:
            return None
        return values[self._index % len(values)]

    def __repr__(self) -> str:
        return f"<AsyncLoopContext index={self.index}>"
