"""Async striped miss coordination."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from ..internal.hashing import mix_hash
from ..observability import Counters


class AsyncMissGate:
    __slots__ = ("_counters", "_locks", "_mask")

    def __init__(self, stripes: int, counters: Counters) -> None:
        self._locks = tuple(asyncio.Lock() for _ in range(stripes))
        self._mask = stripes - 1
        self._counters = counters

    @asynccontextmanager
    async def acquire(self, key: object) -> AsyncIterator[None]:
        lock = self._locks[mix_hash(hash(key)) & self._mask]
        if lock.locked():
            self._counters.increment("lock_waits")
        await lock.acquire()
        try:
            yield
        finally:
            lock.release()
