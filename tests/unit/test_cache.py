from __future__ import annotations

import pytest

from retra import BackendError, Cache, CacheConfig
from retra.backends import MemoryBackend
from retra.entry import CacheEntry
from retra.serializers import JsonSerializer


class BrokenBackend:
    def get(self, key: str) -> CacheEntry | None:
        raise RuntimeError("read failure")

    def set(self, entry: CacheEntry) -> None:
        raise RuntimeError("write failure")

    def delete(self, key: str) -> bool:
        raise RuntimeError("delete failure")

    def clear(self) -> None:
        raise RuntimeError("clear failure")

    def close(self) -> None:
        return None


def test_set_and_get_value(fake_clock) -> None:
    cache = Cache(MemoryBackend(), serializer=JsonSerializer(), clock=fake_clock)

    assert cache.set("user", {"id": 1}) is True
    assert cache.get("user") == {"id": 1}

    stats = cache.stats()
    assert stats.writes == 1
    assert stats.hits == 1


def test_expired_value_becomes_a_miss(fake_clock) -> None:
    backend = MemoryBackend()
    cache = Cache(backend, clock=fake_clock)
    cache.set("short", "value", ttl=5)

    fake_clock.advance(5)

    assert cache.get("short") is None
    assert len(backend) == 0
    assert cache.stats().expirations == 1


def test_zero_ttl_skips_storage(fake_clock) -> None:
    cache = Cache(MemoryBackend(), clock=fake_clock)

    assert cache.set("key", "value", ttl=0) is False
    assert cache.contains("key") is False


def test_cache_none_can_be_disabled(fake_clock) -> None:
    cache = Cache(
        MemoryBackend(),
        config=CacheConfig(cache_none=False),
        clock=fake_clock,
    )

    assert cache.set("empty", None) is False
    assert cache.contains("empty") is False


def test_get_or_set_calls_factory_only_once(fake_clock) -> None:
    cache = Cache(MemoryBackend(), clock=fake_clock)
    calls = 0

    def factory() -> int:
        nonlocal calls
        calls += 1
        return 42

    assert cache.get_or_set("answer", factory) == 42
    assert cache.get_or_set("answer", factory) == 42
    assert calls == 1
    assert cache.stats().misses == 1
    assert cache.stats().hits == 1


def test_fail_open_returns_default(fake_clock) -> None:
    cache = Cache(BrokenBackend(), clock=fake_clock)

    assert cache.get("key", default="fallback") == "fallback"
    assert cache.stats().errors == 1


def test_strict_mode_propagates_backend_error(fake_clock) -> None:
    cache = Cache(
        BrokenBackend(),
        config=CacheConfig(fail_open=False),
        clock=fake_clock,
    )

    with pytest.raises(BackendError):
        cache.get("key")


def test_closed_cache_rejects_operations(fake_clock) -> None:
    cache = Cache(MemoryBackend(), clock=fake_clock)
    cache.close()

    with pytest.raises(BackendError):
        cache.get("key")
