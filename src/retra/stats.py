"""Thread-safe counters for cache activity."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from threading import Lock
from typing import Literal

CounterName = Literal["hits", "misses", "writes", "deletions", "expirations", "errors"]


@dataclass(frozen=True, slots=True)
class CacheStatsSnapshot:
    """Immutable point-in-time view of cache statistics."""

    hits: int
    misses: int
    writes: int
    deletions: int
    expirations: int
    errors: int

    @property
    def requests(self) -> int:
        """Return the number of cache lookups."""

        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        """Return cache hit ratio between zero and one."""

        return self.hits / self.requests if self.requests else 0.0

    def as_dict(self) -> dict[str, int]:
        """Return the snapshot as a plain dictionary."""

        return asdict(self)


class CacheStats:
    """Mutable, thread-safe collection of cache counters."""

    __slots__ = (
        "_deletions",
        "_errors",
        "_expirations",
        "_hits",
        "_lock",
        "_misses",
        "_writes",
    )

    def __init__(self) -> None:
        self._lock = Lock()
        self._hits = 0
        self._misses = 0
        self._writes = 0
        self._deletions = 0
        self._expirations = 0
        self._errors = 0

    def increment(self, counter: CounterName, amount: int = 1) -> None:
        """Increase a counter by a positive amount."""

        if amount < 0:
            raise ValueError("amount must be non-negative")
        attribute = f"_{counter}"
        with self._lock:
            setattr(self, attribute, getattr(self, attribute) + amount)

    def snapshot(self) -> CacheStatsSnapshot:
        """Create an immutable view of the current counters."""

        with self._lock:
            return CacheStatsSnapshot(
                hits=self._hits,
                misses=self._misses,
                writes=self._writes,
                deletions=self._deletions,
                expirations=self._expirations,
                errors=self._errors,
            )

    def reset(self) -> None:
        """Reset every counter to zero."""

        with self._lock:
            self._hits = 0
            self._misses = 0
            self._writes = 0
            self._deletions = 0
            self._expirations = 0
            self._errors = 0
