"""In-process memory backend."""

from __future__ import annotations

from threading import RLock

from ..entry import CacheEntry


class MemoryBackend:
    """Store cache entries in a thread-safe dictionary."""

    def __init__(self) -> None:
        self._entries: dict[str, CacheEntry] = {}
        self._lock = RLock()

    def get(self, key: str) -> CacheEntry | None:
        with self._lock:
            return self._entries.get(key)

    def set(self, entry: CacheEntry) -> None:
        with self._lock:
            self._entries[entry.key] = entry

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._entries.pop(key, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def close(self) -> None:
        """Memory storage does not own external resources."""

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)
