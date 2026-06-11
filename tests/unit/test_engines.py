from __future__ import annotations

import pytest

from retra.engines import LockedEngine, SingleThreadEngine, SnapshotEngine
from retra.policies.eviction import EvictionPolicy
from retra.records import CacheRecord


def record(value: int) -> CacheRecord[int]:
    return CacheRecord(value, 1, 0, 0, 0)


def test_single_engine_uses_fifo_eviction() -> None:
    engine = SingleThreadEngine(2, EvictionPolicy.FIFO)
    engine.set("a", record(1))
    engine.set("b", record(2))
    assert engine.set("c", record(3)) == 1
    assert engine.get("a") is None


def test_single_engine_lru_promotes_reads() -> None:
    engine = SingleThreadEngine(2, EvictionPolicy.LRU)
    engine.set("a", record(1))
    engine.set("b", record(2))
    assert engine.get("a") is not None
    engine.set("c", record(3))
    assert engine.get("b") is None


@pytest.mark.parametrize(
    "engine",
    [
        LockedEngine(8, 4, EvictionPolicy.FIFO),
        SnapshotEngine(8, 4),
    ],
)
def test_sharded_engines_support_common_operations(engine) -> None:
    engine.set("a", record(1))
    engine.set("b", record(2))
    assert engine.get("a") == record(1)
    assert engine.contains("b")
    assert engine.delete("a")
    assert not engine.contains("a")
    assert engine.prune(lambda item: item.value == 2) == 1
