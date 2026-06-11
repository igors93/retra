"""O(1) invalidation tokens."""

from __future__ import annotations

from threading import Lock


class Generation:
    """A monotonic invalidation counter.

    Reading ``value`` intentionally avoids a lock. On CPython, assigning an integer reference is
    atomic under the interpreter lock. ``advance`` uses a lock so increments are not lost when
    called by multiple threads. Engines that require implementation-independent guarantees may
    serialize generation changes at the application boundary.
    """

    __slots__ = ("_lock", "_name", "_value")

    def __init__(self, name: str, initial: int = 0) -> None:
        if not name or not name.strip():
            raise ValueError("generation name must be a non-empty string")
        if initial < 0:
            raise ValueError("generation initial value must be non-negative")
        self._name = name
        self._value = initial
        self._lock = Lock()

    @property
    def name(self) -> str:
        return self._name

    @property
    def value(self) -> int:
        return self._value

    def advance(self, amount: int = 1) -> int:
        """Advance the generation and return its new value."""

        if amount <= 0:
            raise ValueError("generation amount must be greater than zero")
        with self._lock:
            self._value += amount
            return self._value

    def snapshot(self) -> int:
        """Return the current generation value."""

        return self._value

    def __repr__(self) -> str:
        return f"Generation(name={self._name!r}, value={self._value})"
