from __future__ import annotations

import asyncio

import pytest

from retra import MISSING, AsyncCache


@pytest.mark.asyncio
async def test_async_decorator_caches_and_refreshes() -> None:
    cache = AsyncCache.memory(concurrency="single", value_mode="reference", stats="exact")
    calls = 0

    @cache.cached()
    async def value(number: int) -> int:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        return number * calls

    assert value.peek(2) is MISSING
    assert await value(2) == 2
    assert await value(2) == 2
    assert await value.refresh(2) == 4
    assert await value(2) == 4
    assert calls == 2


@pytest.mark.asyncio
async def test_async_miss_gate_suppresses_duplicate_work() -> None:
    cache = AsyncCache.memory(concurrency="balanced", value_mode="reference")
    calls = 0

    @cache.cached()
    async def slow(number: int) -> int:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return number

    assert await asyncio.gather(*(slow(5) for _ in range(10))) == [5] * 10
    assert calls == 1
