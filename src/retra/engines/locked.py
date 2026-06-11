"""Shard-locked engine for balanced read/write workloads."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from threading import RLock
from typing import Any

from ..internal.hashing import shard_index
from ..policies.eviction import EvictionPolicy
from ..records import CacheRecord


@dataclass(slots=True)
class _LockedShard:
    table: dict[object, CacheRecord[Any]] | OrderedDict[object, CacheRecord[Any]]
    lock: RLock
    capacity: int


class LockedEngine:
    """A portable thread-safe engine using one lock per shard."""

    __slots__ = ("_eviction", "_mask", "_shards")

    def __init__(self, max_items: int, shard_count: int, eviction: EvictionPolicy) -> None:
        self._mask = shard_count - 1
        self._eviction = eviction
        base, remainder = divmod(max_items, shard_count)
        self._shards: list[_LockedShard] = []
        for index in range(shard_count):
            capacity = base + (1 if index < remainder else 0)
            table: dict[object, CacheRecord[Any]] | OrderedDict[object, CacheRecord[Any]]
            table = OrderedDict() if eviction is EvictionPolicy.LRU else {}
            self._shards.append(_LockedShard(table, RLock(), max(1, capacity)))

    def _shard(self, key: object) -> _LockedShard:
        return self._shards[shard_index(key, self._mask)]

    def get(self, key: object) -> CacheRecord[Any] | None:
        shard = self._shard(key)
        with shard.lock:
            record = shard.table.get(key)
            if record is not None and self._eviction is EvictionPolicy.LRU:
                assert isinstance(shard.table, OrderedDict)
                shard.table.move_to_end(key)
            return record

    def set(self, key: object, record: CacheRecord[Any]) -> int:
        shard = self._shard(key)
        with shard.lock:
            existed = key in shard.table
            shard.table[key] = record
            if self._eviction is EvictionPolicy.LRU:
                assert isinstance(shard.table, OrderedDict)
                shard.table.move_to_end(key)
            if existed or len(shard.table) <= shard.capacity:
                return 0
            oldest = next(iter(shard.table))
            del shard.table[oldest]
            return 1

    def delete(self, key: object) -> bool:
        shard = self._shard(key)
        with shard.lock:
            try:
                del shard.table[key]
            except KeyError:
                return False
            return True

    def contains(self, key: object) -> bool:
        shard = self._shard(key)
        with shard.lock:
            return key in shard.table

    def clear(self) -> None:
        for shard in self._shards:
            with shard.lock:
                shard.table.clear()

    def get_many(self, keys: Iterable[object]) -> dict[object, CacheRecord[Any]]:
        return {key: record for key in keys if (record := self.get(key)) is not None}

    def set_many(self, records: Mapping[object, CacheRecord[Any]]) -> int:
        return sum(self.set(key, record) for key, record in records.items())

    def delete_many(self, keys: Iterable[object]) -> int:
        return sum(self.delete(key) for key in keys)

    def prune(self, predicate: Callable[[CacheRecord[Any]], bool]) -> int:
        removed = 0
        for shard in self._shards:
            with shard.lock:
                keys = [key for key, record in shard.table.items() if predicate(record)]
                for key in keys:
                    del shard.table[key]
                removed += len(keys)
        return removed

    def __len__(self) -> int:
        total = 0
        for shard in self._shards:
            with shard.lock:
                total += len(shard.table)
        return total
