"""Striped miss coordination kept outside the hit path."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock

from ..internal.hashing import mix_hash
from ..observability import Counters


class MissGate:
    """Coordinate cache misses with a fixed number of locks.

    Locks are selected by key hash and never allocated per cache entry. A hit never acquires one.
    """

    __slots__ = ("_counters", "_locks", "_mask")

    def __init__(self, stripes: int, counters: Counters) -> None:
        self._locks = tuple(Lock() for _ in range(stripes))
        self._mask = stripes - 1
        self._counters = counters

    @contextmanager
    def acquire(self, key: object) -> Iterator[None]:
        lock = self._locks[mix_hash(hash(key)) & self._mask]
        if not lock.acquire(blocking=False):
            self._counters.increment("lock_waits")
            lock.acquire()
        try:
            yield
        finally:
            lock.release()
