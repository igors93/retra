"""Per-key lock registry used to reduce duplicate computations."""

from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from threading import Lock, RLock
from typing import Iterator


class KeyLockRegistry:
    """Maintain one re-entrant lock for each active cache key.

    Locks are reference-counted and removed after their last user exits. This avoids
    retaining one lock forever for every key the application has ever seen.
    """

    def __init__(self) -> None:
        self._registry_lock = Lock()
        self._locks: dict[str, RLock] = defaultdict(RLock)
        self._references: dict[str, int] = defaultdict(int)

    @contextmanager
    def acquire(self, key: str) -> Iterator[None]:
        with self._registry_lock:
            lock = self._locks[key]
            self._references[key] += 1

        lock.acquire()
        try:
            yield
        finally:
            lock.release()
            with self._registry_lock:
                self._references[key] -= 1
                if self._references[key] == 0:
                    del self._references[key]
                    del self._locks[key]
