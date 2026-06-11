"""Clock implementations selected once when a store is created."""

from __future__ import annotations

import time
from typing import Protocol


class Clock(Protocol):
    """Return nanosecond timestamps in one stable time domain."""

    def now_ns(self) -> int:
        """Return the current timestamp in nanoseconds."""


class MonotonicClock:
    """Monotonic clock for process-local caches."""

    __slots__ = ()

    def now_ns(self) -> int:
        return time.monotonic_ns()


class WallClock:
    """Wall clock for values that must survive process restarts."""

    __slots__ = ()

    def now_ns(self) -> int:
        return time.time_ns()
