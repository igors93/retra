"""Direct-object memory storage."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from ..config import ConcurrencyMode
from ..engines import LockedEngine, SingleThreadEngine, SnapshotEngine
from ..engines.base import MemoryEngine
from ..exceptions import ConfigurationError
from ..internal.clock import Clock, MonotonicClock
from ..policies.eviction import EvictionPolicy
from ..records import CacheRecord


class MemoryStore:
    """Store Python objects directly without serialization."""

    __slots__ = ("_engine", "_version", "clock")
    persistent = False

    def __init__(
        self,
        *,
        max_items: int,
        concurrency: ConcurrencyMode,
        shards: int,
        eviction: EvictionPolicy,
        clock: Clock | None = None,
    ) -> None:
        self.clock = clock or MonotonicClock()
        self._version: int = 0
        self._engine: MemoryEngine
        if concurrency is ConcurrencyMode.SINGLE:
            self._engine = SingleThreadEngine(max_items, eviction)
        elif concurrency is ConcurrencyMode.READ_HEAVY:
            if eviction is EvictionPolicy.LRU:
                raise ConfigurationError("read_heavy mode supports FIFO eviction only")
            self._engine = SnapshotEngine(max_items, shards)
        else:
            self._engine = LockedEngine(max_items, shards, eviction)

    def get_record(self, key: object) -> CacheRecord[Any] | None:
        return self._engine.get(key)

    def get_metadata(self, key: object) -> CacheRecord[None] | None:
        record = self._engine.get(key)
        if record is None:
            return None
        return CacheRecord(
            value=None,
            created_ns=record.created_ns,
            deadline_ns=record.deadline_ns,
            namespace_generation=record.namespace_generation,
            function_generation=record.function_generation,
            dependency_versions=record.dependency_versions,
        )

    def version(self) -> int:
        """Monotonic counter that increments on any structural change (set, delete, clear)."""
        return self._version

    def set_record(self, key: object, record: CacheRecord[Any]) -> int:
        evicted = self._engine.set(key, record)
        self._version += 1
        return evicted

    def delete(self, key: object) -> bool:
        deleted = self._engine.delete(key)
        if deleted:
            self._version += 1
        return deleted

    def clear(self) -> None:
        self._engine.clear()
        self._version += 1

    def contains_key(self, key: object) -> bool:
        return self._engine.contains(key)

    def get_many(self, keys: Iterable[object]) -> dict[object, CacheRecord[Any]]:
        return self._engine.get_many(keys)

    def set_many(self, records: Mapping[object, CacheRecord[Any]]) -> int:
        evicted = self._engine.set_many(records)
        if records:
            self._version += 1
        return evicted

    def delete_many(self, keys: Iterable[object]) -> int:
        deleted = self._engine.delete_many(keys)
        if deleted:
            self._version += 1
        return deleted

    def prune(self) -> int:
        now_ns = self.clock.now_ns()
        return self._engine.prune(lambda record: record.is_expired(now_ns))

    def close(self) -> None:
        return None

    def __len__(self) -> int:
        return len(self._engine)
