"""Read-optimized copy-on-write engine."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from threading import Lock
from typing import Any

from ..internal.hashing import shard_index
from ..records import CacheRecord


@dataclass(frozen=True, slots=True)
class _ShardState:
    table: dict[object, CacheRecord[Any]]
    version: int


@dataclass(slots=True)
class _SnapshotShard:
    state: _ShardState
    write_lock: Lock
    capacity: int


class SnapshotEngine:
    """Lock-free reads with copy-on-write shard updates.

    A reader sees either the old immutable snapshot or the new one. This engine is intended for
    read-heavy workloads. FIFO eviction is used because exact LRU would require mutating state on
    every hit and would defeat the lock-free read path.
    """

    __slots__ = ("_mask", "_shards")

    def __init__(self, max_items: int, shard_count: int) -> None:
        self._mask = shard_count - 1
        base, remainder = divmod(max_items, shard_count)
        self._shards = [
            _SnapshotShard(
                state=_ShardState({}, 0),
                write_lock=Lock(),
                capacity=max(1, base + (1 if index < remainder else 0)),
            )
            for index in range(shard_count)
        ]

    def _shard(self, key: object) -> _SnapshotShard:
        return self._shards[shard_index(key, self._mask)]

    def get(self, key: object) -> CacheRecord[Any] | None:
        state = self._shard(key).state
        return state.table.get(key)

    def set(self, key: object, record: CacheRecord[Any]) -> int:
        shard = self._shard(key)
        with shard.write_lock:
            old = shard.state
            new_table = old.table.copy()
            existed = key in new_table
            new_table[key] = record
            evicted = 0
            if not existed and len(new_table) > shard.capacity:
                oldest = next(iter(new_table))
                del new_table[oldest]
                evicted = 1
            shard.state = _ShardState(new_table, old.version + 1)
            return evicted

    def delete(self, key: object) -> bool:
        shard = self._shard(key)
        with shard.write_lock:
            old = shard.state
            if key not in old.table:
                return False
            new_table = old.table.copy()
            del new_table[key]
            shard.state = _ShardState(new_table, old.version + 1)
            return True

    def contains(self, key: object) -> bool:
        return key in self._shard(key).state.table

    def clear(self) -> None:
        for shard in self._shards:
            with shard.write_lock:
                old = shard.state
                shard.state = _ShardState({}, old.version + 1)

    def get_many(self, keys: Iterable[object]) -> dict[object, CacheRecord[Any]]:
        return {key: record for key in keys if (record := self.get(key)) is not None}

    def set_many(self, records: Mapping[object, CacheRecord[Any]]) -> int:
        # Grouping by shard limits each copy-on-write transaction to one published state.
        grouped: dict[int, list[tuple[object, CacheRecord[Any]]]] = {}
        for key, record in records.items():
            index = shard_index(key, self._mask)
            grouped.setdefault(index, []).append((key, record))
        evicted = 0
        for index, items in grouped.items():
            shard = self._shards[index]
            with shard.write_lock:
                old = shard.state
                table = old.table.copy()
                for key, record in items:
                    table[key] = record
                while len(table) > shard.capacity:
                    del table[next(iter(table))]
                    evicted += 1
                shard.state = _ShardState(table, old.version + 1)
        return evicted

    def delete_many(self, keys: Iterable[object]) -> int:
        return sum(self.delete(key) for key in keys)

    def prune(self, predicate: Callable[[CacheRecord[Any]], bool]) -> int:
        removed = 0
        for shard in self._shards:
            with shard.write_lock:
                old = shard.state
                table = {key: record for key, record in old.table.items() if not predicate(record)}
                difference = len(old.table) - len(table)
                if difference:
                    shard.state = _ShardState(table, old.version + 1)
                    removed += difference
        return removed

    def __len__(self) -> int:
        return sum(len(shard.state.table) for shard in self._shards)
