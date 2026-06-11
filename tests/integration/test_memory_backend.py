from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import sleep

from retra import Cache
from retra.backends import MemoryBackend


def test_memory_cache_prevents_duplicate_thread_work() -> None:
    cache = Cache(MemoryBackend())
    calls = 0
    calls_lock = Lock()

    @cache.cached(ttl=10)
    def expensive(number: int) -> int:
        nonlocal calls
        with calls_lock:
            calls += 1
        sleep(0.02)
        return number * 2

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(expensive, [5] * 16))

    assert results == [10] * 16
    assert calls == 1
