from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from retra import Cache


def test_thread_miss_gate_suppresses_duplicate_work() -> None:
    cache = Cache.memory(concurrency="balanced", value_mode="reference", stats="exact")
    calls = 0
    calls_lock = threading.Lock()

    @cache.cached()
    def slow(value: int) -> int:
        nonlocal calls
        with calls_lock:
            calls += 1
        time.sleep(0.02)
        return value

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(slow, [7] * 16))
    assert results == [7] * 16
    assert calls == 1
    assert cache.stats().lock_waits > 0
