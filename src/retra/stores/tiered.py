"""Explicit memory-fronted persistent storage."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from ..protocols import Store
from ..records import CacheRecord
from .memory import MemoryStore


class TieredStore:
    """Read through a front memory store and a backing persistent store.

    The backing store is explicit because a front miss may perform disk I/O. Writes are
    write-through: backing storage succeeds before the front is updated.
    """

    __slots__ = ("backing", "clock", "front")
    persistent = True

    def __init__(self, front: MemoryStore, backing: Store) -> None:
        if not getattr(backing, "persistent", False):
            raise ValueError("tiered backing store must be persistent")
        self.front = front
        self.backing = backing
        self.clock = backing.clock
        self.front.clock = self.clock

    def get_record(self, key: object) -> CacheRecord[Any] | None:
        record = self.front.get_record(key)
        if record is not None:
            if not record.is_expired(self.clock.now_ns()):
                return record
            self.front.delete(key)
        record = self.backing.get_record(key)
        if record is not None:
            self.front.set_record(key, record)
        return record

    def get_metadata(self, key: object) -> CacheRecord[None] | None:
        metadata = self.front.get_metadata(key)
        if metadata is not None and not metadata.is_expired(self.clock.now_ns()):
            return metadata
        return self.backing.get_metadata(key)

    def set_record(self, key: object, record: CacheRecord[Any]) -> int:
        self.backing.set_record(key, record)
        return self.front.set_record(key, record)

    def delete(self, key: object) -> bool:
        backing_deleted = self.backing.delete(key)
        front_deleted = self.front.delete(key)
        return backing_deleted or front_deleted

    def clear(self) -> None:
        self.backing.clear()
        self.front.clear()

    def contains_key(self, key: object) -> bool:
        record = self.front.get_record(key)
        if record is not None and not record.is_expired(self.clock.now_ns()):
            return True
        return self.backing.contains_key(key)

    def get_many(self, keys: Iterable[object]) -> dict[object, CacheRecord[Any]]:
        return {key: record for key in keys if (record := self.get_record(key)) is not None}

    def set_many(self, records: Mapping[object, CacheRecord[Any]]) -> int:
        self.backing.set_many(records)
        return self.front.set_many(records)

    def delete_many(self, keys: Iterable[object]) -> int:
        materialized = tuple(keys)
        backing_count = self.backing.delete_many(materialized)
        front_count = self.front.delete_many(materialized)
        return max(backing_count, front_count)

    def prune(self) -> int:
        return self.front.prune() + self.backing.prune()

    def close(self) -> None:
        self.front.close()
        self.backing.close()
