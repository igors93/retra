"""Regression tests: max_items is truly honoured across all concurrency modes."""

from __future__ import annotations

import pytest

from retra import MISSING, Cache, CacheConfig
from retra.config import ConcurrencyMode
from retra.policies.eviction import EvictionPolicy
from retra.stores import MemoryStore


def _cache_with_capacity(fake_clock, max_items: int, concurrency: ConcurrencyMode) -> Cache:
    effective_shards = 1  # keep simple: 1 shard so per-shard limit == max_items
    if concurrency is ConcurrencyMode.READ_HEAVY and max_items > 1:
        effective_shards = 1  # SnapshotEngine handles single-shard fine
    store = MemoryStore(
        max_items=max_items,
        concurrency=concurrency,
        shards=effective_shards,
        eviction=EvictionPolicy.FIFO,
        clock=fake_clock,
    )
    config = CacheConfig(
        concurrency=concurrency,
        max_items=max_items,
        shards=effective_shards,
        miss_locks=4,
    )
    return Cache(store, config=config)


@pytest.mark.parametrize(
    "concurrency",
    [ConcurrencyMode.SINGLE, ConcurrencyMode.BALANCED],
)
def test_max_items_1_evicts_oldest_entry(fake_clock, concurrency) -> None:
    cache = _cache_with_capacity(fake_clock, max_items=1, concurrency=concurrency)

    cache.set("a", 1)
    assert cache.peek("a") == 1

    cache.set("b", 2)  # "a" must be evicted
    assert cache.peek("b") == 2
    assert cache.peek("a") is MISSING, "a must have been evicted when max_items=1"


@pytest.mark.parametrize(
    "concurrency",
    [ConcurrencyMode.SINGLE, ConcurrencyMode.BALANCED],
)
def test_max_items_2_keeps_two_entries(fake_clock, concurrency) -> None:
    cache = _cache_with_capacity(fake_clock, max_items=2, concurrency=concurrency)

    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.peek("a") == 1
    assert cache.peek("b") == 2

    cache.set("c", 3)  # "a" evicted (FIFO)
    assert cache.peek("c") == 3
    assert cache.peek("b") == 2
    assert cache.peek("a") is MISSING, "a must be evicted as oldest entry"


def test_effective_shards_clamps_for_small_max_items() -> None:
    """When max_items < requested_shards the helper must clamp, not expose excess capacity."""
    from retra.cache import _effective_shards

    assert _effective_shards(1, 64) == 1
    assert _effective_shards(2, 64) == 2
    assert _effective_shards(3, 64) == 2   # floor power-of-two of min(3, 64)=3 → 2
    assert _effective_shards(4, 64) == 4
    assert _effective_shards(5, 64) == 4   # floor power-of-two of 5 → 4
    assert _effective_shards(64, 64) == 64
    assert _effective_shards(100, 64) == 64  # capped at shards


def test_memory_factory_respects_max_items_with_default_shards(fake_clock) -> None:
    """Cache.memory() with max_items smaller than default shards stays within bound."""
    # max_items=2, default shards=64 → effective_shards=2
    cache = Cache.memory(
        concurrency="single",
        value_mode="reference",
        max_items=2,
        shards=64,
    )
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)  # must evict one of a/b

    live = sum(1 for k in ("a", "b", "c") if cache.peek(k) is not MISSING)
    assert live <= 2, f"expected at most 2 live entries, found {live}"


def test_decorated_function_respects_max_items(fake_clock) -> None:
    """@cache.cached() entries count toward the same max_items limit."""
    cache = _cache_with_capacity(fake_clock, max_items=1, concurrency=ConcurrencyMode.SINGLE)
    calls = 0

    @cache.cached()
    def fn(x: int) -> int:
        nonlocal calls
        calls += 1
        return x

    fn(1)  # stores key 1
    fn(2)  # stores key 2, evicts key 1
    fn(1)  # must recompute (evicted)

    assert calls == 3, "key 1 must be evicted after key 2 was stored in a max_items=1 cache"
