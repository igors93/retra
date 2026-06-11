"""Regression tests: CacheClosedError is raised consistently after cache.close()."""

from __future__ import annotations

import pytest

from retra import Cache, MISSING
from retra.exceptions import CacheClosedError


def _simple_cache() -> Cache:
    return Cache.memory(concurrency="single", value_mode="reference", stats="off", inline_cache=False)


def test_decorated_function_raises_on_miss_after_close() -> None:
    """After close(), a decorated function that misses must raise CacheClosedError."""
    cache = _simple_cache()

    @cache.cached()
    def fn(x: int) -> int:
        return x

    cache.close()

    with pytest.raises(CacheClosedError):
        fn(42)  # miss → miss_handler → _ensure_open() → raises


def test_manual_get_raises_after_close() -> None:
    cache = _simple_cache()
    cache.close()
    with pytest.raises(CacheClosedError):
        cache.get("k")


def test_manual_set_raises_after_close() -> None:
    cache = _simple_cache()
    cache.close()
    with pytest.raises(CacheClosedError):
        cache.set("k", 1)


def test_manual_delete_raises_after_close() -> None:
    cache = _simple_cache()
    cache.close()
    with pytest.raises(CacheClosedError):
        cache.delete("k")


def test_manual_peek_raises_after_close() -> None:
    cache = _simple_cache()
    cache.close()
    with pytest.raises(CacheClosedError):
        cache.peek("k")


def test_manual_contains_raises_after_close() -> None:
    cache = _simple_cache()
    cache.close()
    with pytest.raises(CacheClosedError):
        cache.contains("k")


def test_clear_raises_after_close() -> None:
    cache = _simple_cache()
    cache.close()
    with pytest.raises(CacheClosedError):
        cache.clear()


def test_prune_raises_after_close() -> None:
    cache = _simple_cache()
    cache.close()
    with pytest.raises(CacheClosedError):
        cache.prune()


def test_double_close_is_idempotent() -> None:
    """Closing a cache twice must not raise."""
    cache = _simple_cache()
    cache.close()
    cache.close()  # must not raise


def test_context_manager_closes_on_exit() -> None:
    with Cache.memory(concurrency="single", value_mode="reference") as cache:
        cache.set("k", 1)
    with pytest.raises(CacheClosedError):
        cache.get("k")


def test_decorated_hit_served_after_close() -> None:
    """A cached hit does not go through miss_handler, so it must succeed even after close.

    This is a documented behaviour: read-only hits are served from the store until the
    process exits. Only misses (which would trigger computation + write) are blocked.
    """
    cache = Cache.memory(concurrency="single", value_mode="reference", inline_cache=False)

    @cache.cached()
    def fn(x: int) -> int:
        return x

    fn(99)       # populate store
    cache.close()

    # Hit path does not call _ensure_open(), so it returns the cached value.
    assert fn(99) == 99
