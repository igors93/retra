from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from retra.config import ConcurrencyMode
from retra.policies.eviction import EvictionPolicy
from retra.protocols import Store
from retra.records import CacheRecord
from retra.stores import FileStore, MemoryStore, SQLiteStore


@contextmanager
def opened(factory: Callable[[], Store]) -> Iterator[Store]:
    store = factory()
    try:
        yield store
    finally:
        store.close()


@pytest.fixture(params=["memory", "file", "sqlite"])
def store_factory(request, tmp_path: Path) -> Callable[[], Store]:
    if request.param == "memory":
        return lambda: MemoryStore(
            max_items=32,
            concurrency=ConcurrencyMode.BALANCED,
            shards=4,
            eviction=EvictionPolicy.FIFO,
        )
    if request.param == "file":
        return lambda: FileStore(tmp_path / "files")
    return lambda: SQLiteStore(tmp_path / "cache.db")


def record(value: object = "value") -> CacheRecord[object]:
    return CacheRecord(value, 1, 0, 1, 2, (3, 4))


def test_missing_key_returns_none(store_factory: Callable[[], Store]) -> None:
    with opened(store_factory) as store:
        assert store.get_record("missing") is None


def test_record_round_trip(store_factory: Callable[[], Store]) -> None:
    with opened(store_factory) as store:
        expected = record({"a": 1})
        assert store.set_record("key", expected) == 0
        assert store.get_record("key") == expected


def test_record_can_be_overwritten(store_factory: Callable[[], Store]) -> None:
    with opened(store_factory) as store:
        store.set_record("key", record("first"))
        store.set_record("key", record("second"))
        assert store.get_record("key") == record("second")


def test_delete_and_clear(store_factory: Callable[[], Store]) -> None:
    with opened(store_factory) as store:
        store.set_record("a", record(1))
        store.set_record("b", record(2))
        assert store.delete("a")
        assert not store.delete("a")
        store.clear()
        assert store.get_record("b") is None


def test_batch_operations(store_factory: Callable[[], Store]) -> None:
    with opened(store_factory) as store:
        store.set_many({"a": record(1), "b": record(2)})
        assert store.get_many(["a", "b", "c"]) == {"a": record(1), "b": record(2)}
        assert store.delete_many(["a", "b"]) == 2
