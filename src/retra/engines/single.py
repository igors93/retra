"""Fast single-thread memory engine."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from ..policies.eviction import EvictionPolicy
from ..records import CacheRecord


class SingleThreadEngine:
    """A bounded table with no synchronization.

    The caller must guarantee that all operations occur on one thread. This engine is the closest
    Retra gets to the cost of a direct dictionary lookup.
    """

    __slots__ = ("_eviction", "_max_items", "_table")

    def __init__(self, max_items: int, eviction: EvictionPolicy) -> None:
        self._max_items = max_items
        self._eviction = eviction
        self._table: dict[object, CacheRecord[Any]] | OrderedDict[object, CacheRecord[Any]]
        self._table = OrderedDict() if eviction is EvictionPolicy.LRU else {}

    def get(self, key: object) -> CacheRecord[Any] | None:
        record = self._table.get(key)
        if record is not None and self._eviction is EvictionPolicy.LRU:
            assert isinstance(self._table, OrderedDict)
            self._table.move_to_end(key)
        return record

    def set(self, key: object, record: CacheRecord[Any]) -> int:
        existed = key in self._table
        self._table[key] = record
        if self._eviction is EvictionPolicy.LRU:
            assert isinstance(self._table, OrderedDict)
            self._table.move_to_end(key)
        if existed or len(self._table) <= self._max_items:
            return 0
        oldest = next(iter(self._table))
        del self._table[oldest]
        return 1

    def delete(self, key: object) -> bool:
        try:
            del self._table[key]
        except KeyError:
            return False
        return True

    def contains(self, key: object) -> bool:
        return key in self._table

    def clear(self) -> None:
        self._table.clear()

    def get_many(self, keys: Iterable[object]) -> dict[object, CacheRecord[Any]]:
        found: dict[object, CacheRecord[Any]] = {}
        for key in keys:
            record = self.get(key)
            if record is not None:
                found[key] = record
        return found

    def set_many(self, records: Mapping[object, CacheRecord[Any]]) -> int:
        evicted = 0
        for key, record in records.items():
            evicted += self.set(key, record)
        return evicted

    def delete_many(self, keys: Iterable[object]) -> int:
        return sum(self.delete(key) for key in keys)

    def prune(self, predicate: Callable[[CacheRecord[Any]], bool]) -> int:
        keys = [key for key, record in self._table.items() if predicate(record)]
        for key in keys:
            del self._table[key]
        return len(keys)

    def __len__(self) -> int:
        return len(self._table)
