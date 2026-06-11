from __future__ import annotations

import asyncio

import pytest

from retra import Cache
from retra.backends import MemoryBackend


def test_decorator_caches_function_result(fake_clock) -> None:
    cache = Cache(MemoryBackend(), clock=fake_clock)
    calls = 0

    @cache.cached(ttl=30)
    def add(left: int, right: int = 1) -> int:
        nonlocal calls
        calls += 1
        return left + right

    assert add(2, right=3) == 5
    assert add(left=2, right=3) == 5
    assert calls == 1


def test_decorated_value_can_be_invalidated(fake_clock) -> None:
    cache = Cache(MemoryBackend(), clock=fake_clock)
    calls = 0

    @cache.cached()
    def value(number: int) -> int:
        nonlocal calls
        calls += 1
        return number * 2

    assert value(4) == 8
    invalidator = getattr(value, "cache_invalidate")
    assert invalidator(4) is True
    assert value(4) == 8
    assert calls == 2


def test_custom_key_is_supported(fake_clock) -> None:
    cache = Cache(MemoryBackend(), clock=fake_clock)
    calls = 0

    @cache.cached(key=lambda user_id, verbose=False: str(user_id))
    def load_user(user_id: int, verbose: bool = False) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"id": user_id, "verbose": verbose}

    assert load_user(1, verbose=False) == {"id": 1, "verbose": False}
    assert load_user(1, verbose=True) == {"id": 1, "verbose": False}
    assert calls == 1


def test_async_function_is_rejected(fake_clock) -> None:
    cache = Cache(MemoryBackend(), clock=fake_clock)

    with pytest.raises(TypeError):

        @cache.cached()
        async def async_value() -> int:
            await asyncio.sleep(0)
            return 1
