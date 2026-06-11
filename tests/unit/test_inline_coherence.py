"""Regression tests: inline cache slot must never serve stale values.

The inline slot holds one (key, record, store_version) triple. A hit is only
served when ALL of:
  - slot.key   == call_key
  - slot.store_version == store.version()   ← eviction / delete / clear guard
  - validity_expression is True             ← generation + TTL guard
"""

from __future__ import annotations

from retra import Cache
from retra.config import ConcurrencyMode
from retra.policies.eviction import EvictionPolicy
from retra.stores import MemoryStore


def _make_inline_cache(fake_clock, *, max_items: int = 2):
    """Return a cache backed by a single-shard store with inline_cache=True."""
    store = MemoryStore(
        max_items=max_items,
        concurrency=ConcurrencyMode.SINGLE,
        shards=1,
        eviction=EvictionPolicy.FIFO,
        clock=fake_clock,
    )
    from retra import CacheConfig

    config = CacheConfig(
        concurrency=ConcurrencyMode.SINGLE,
        max_items=max_items,
        shards=1,
        miss_locks=4,
        inline_cache=True,
    )
    return Cache(store, config=config)


def test_inline_slot_is_invalidated_after_eviction(fake_clock) -> None:
    """When key A is evicted by a write of key B, a subsequent call for A must recompute."""
    cache = _make_inline_cache(fake_clock, max_items=1)
    calls: dict[str, int] = {"a": 0, "b": 0}

    @cache.cached()
    def fn_a(x: int) -> int:
        calls["a"] += 1
        return x

    @cache.cached()
    def fn_b(x: int) -> int:
        calls["b"] += 1
        return x * 2

    fn_a(1)  # store version=1, slot_a={key_a1, version=1}
    fn_a(1)  # inline hit — calls["a"] still 1

    fn_b(1)  # miss → store (evicts fn_a's entry) → version=2, slot_b={key_b1, version=2}

    fn_a(1)  # slot_a: key matches BUT version=1 ≠ 2 → miss → store miss → recompute
    assert calls["a"] == 2, "fn_a must recompute after its entry was evicted"


def test_inline_slot_is_invalidated_after_delete(fake_clock) -> None:
    """Deleting an entry from the store (without clearing the slot) must invalidate the slot."""
    cache = _make_inline_cache(fake_clock, max_items=4)
    calls = 0

    @cache.cached()
    def fn(x: int) -> int:
        nonlocal calls
        calls += 1
        return x

    fn(1)  # stores, slot={key1, version=N}
    fn(1)  # inline hit

    # Delete directly from the store so the InlineSlot is NOT explicitly cleared.
    # This simulates eviction or external deletion that bypasses the wrapper.
    assert cache.store.delete(fn.cache_key(1))  # store._version increments

    fn(1)  # slot.key matches BUT store_version N ≠ N+1 → miss → store miss → recompute
    assert calls == 2, "fn must recompute after its entry was deleted from the store"


def test_inline_slot_is_invalidated_after_cache_clear(fake_clock) -> None:
    """After cache.clear(), every inline slot is stale."""
    cache = _make_inline_cache(fake_clock, max_items=4)
    calls = 0

    @cache.cached()
    def fn(x: int) -> int:
        nonlocal calls
        calls += 1
        return x

    fn(5)  # stores, slot={key5, version=N}
    fn(5)  # inline hit

    cache.clear()  # store version increments

    fn(5)  # slot.key matches but version mismatch → miss → recompute
    assert calls == 2, "fn must recompute after cache.clear()"


def test_inline_slot_is_invalidated_after_invalidate_all(fake_clock) -> None:
    """invalidate_all() advances the namespace generation, making the slot record invalid."""
    cache = _make_inline_cache(fake_clock, max_items=4)
    calls = 0

    @cache.cached()
    def fn(x: int) -> int:
        nonlocal calls
        calls += 1
        return x

    fn(3)
    fn(3)  # inline hit

    cache.invalidate_all()  # namespace generation advances

    fn(3)  # slot.key matches + version matches, but namespace_generation mismatch → miss
    assert calls == 2, "fn must recompute after invalidate_all()"


def test_inline_slot_respects_ttl_expiration(fake_clock) -> None:
    """An inline slot hit for an expired record must not be returned."""
    store = MemoryStore(
        max_items=4,
        concurrency=ConcurrencyMode.SINGLE,
        shards=1,
        eviction=EvictionPolicy.FIFO,
        clock=fake_clock,
    )
    from retra import CacheConfig

    config = CacheConfig(
        concurrency=ConcurrencyMode.SINGLE,
        max_items=4,
        shards=1,
        miss_locks=4,
        inline_cache=True,
    )
    cache = Cache(store, config=config)
    calls = 0

    @cache.cached(ttl="100ns")
    def fn(x: int) -> int:
        nonlocal calls
        calls += 1
        return x

    fn(7)  # slot={key7, record.deadline=now+100}
    fake_clock.advance(200)  # advance past deadline

    fn(7)  # deadline check in validity_expression fails → miss → recompute
    assert calls == 2, "fn must recompute when TTL has expired"
