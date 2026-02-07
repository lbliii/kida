"""Loop iteration metadata for Kida ``{% for %}`` blocks."""

from __future__ import annotations

from typing import Any


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

    __slots__ = ("_items", "_index", "_length")

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
