"""Clock implementations."""

from __future__ import annotations

import time


class SystemClock:
    """Read the system wall clock as a Unix timestamp."""

    __slots__ = ()

    def now(self) -> float:
        return time.time()
