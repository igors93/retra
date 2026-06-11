from __future__ import annotations

from typing import Any

from retra import DO_NOT_CACHE, MISSING, NEVER_EXPIRE, Cache, CacheConfig
from retra.config import ConcurrencyMode, StatsMode
from retra.policies.eviction import EvictionPolicy
from retra.policies.freezing import FrozenDict, ValueMode
from retra.stores import MemoryStore


def make_cache(fake_clock, **config_values: Any) -> Cache:
    config = CacheConfig(
        concurrency=ConcurrencyMode.SINGLE,
        max_items=16,
        shards=1,
        miss_locks=8,
        eviction=EvictionPolicy.FIFO,
        stats=StatsMode.EXACT,
        **config_values,
    )
    store = MemoryStore(
        max_items=16,
        concurrency=ConcurrencyMode.SINGLE,
        shards=1,
        eviction=EvictionPolicy.FIFO,
        clock=fake_clock,
    )
    return Cache(store, config=config)


def test_manual_get_set_and_delete(fake_clock) -> None:
    cache = make_cache(fake_clock, value_mode=ValueMode.REFERENCE)
    assert cache.get("missing") is MISSING
    assert cache.set("key", 42)
    assert cache.get("key") == 42
    assert cache.contains("key")
    assert cache.delete("key")
    assert cache.peek("key") is MISSING


def test_zero_ttl_skips_storage(fake_clock) -> None:
    cache = make_cache(fake_clock)
    assert cache.set("key", 1, ttl=0) is False
    assert cache.set("key", 1, ttl=DO_NOT_CACHE) is False
    assert cache.peek("key") is MISSING


def test_never_expire_constant(fake_clock) -> None:
    cache = make_cache(fake_clock)
    cache.set("key", 1, ttl=NEVER_EXPIRE)
    fake_clock.advance(10**18)
    assert cache.get("key") == 1


def test_ttl_expiration(fake_clock) -> None:
    cache = make_cache(fake_clock)
    cache.set("key", 1, ttl="10ns")
    fake_clock.advance(10)
    assert cache.get("key") is MISSING
    assert cache.stats().expirations == 1


def test_generation_invalidation_is_constant_time(fake_clock) -> None:
    cache = make_cache(fake_clock)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.invalidate_all()
    assert cache.peek("a") is MISSING
    assert cache.peek("b") is MISSING


def test_frozen_mode_protects_cached_values(fake_clock) -> None:
    cache = make_cache(fake_clock, value_mode=ValueMode.FROZEN)
    source = {"values": [1, 2]}
    cache.set("key", source)
    source["values"].append(3)
    cached = cache.get("key")
    assert isinstance(cached, FrozenDict)
    assert cached["values"] == (1, 2)


def test_batch_operations(fake_clock) -> None:
    cache = make_cache(fake_clock, value_mode=ValueMode.REFERENCE)
    assert cache.set_many({"a": 1, "b": 2}) == 2
    assert cache.get_many(["a", "b", "c"]) == {"a": 1, "b": 2}
    assert cache.delete_many(["a", "b"]) == 2


def test_get_or_set_only_executes_factory_on_miss(fake_clock) -> None:
    cache = make_cache(fake_clock, value_mode=ValueMode.REFERENCE)
    calls = 0

    def factory() -> int:
        nonlocal calls
        calls += 1
        return 10

    assert cache.get_or_set("key", factory) == 10
    assert cache.get_or_set("key", factory) == 10
    assert calls == 1


def test_memory_profiles_select_expected_tradeoffs() -> None:
    speed = Cache.memory(profile="speed")
    precise = Cache.memory(profile="precise")
    assert speed.config.concurrency is ConcurrencyMode.SINGLE
    assert speed.config.value_mode is ValueMode.REFERENCE
    assert speed.config.stats is StatsMode.OFF
    assert precise.config.value_mode is ValueMode.FROZEN
    assert precise.config.stats is StatsMode.EXACT
