from __future__ import annotations

from pathlib import Path

from retra import Cache


def test_tiered_store_promotes_persistent_hit_to_memory(tmp_path: Path) -> None:
    backing = Cache.sqlite_store(tmp_path / "cache.db")
    seed = Cache(backing, config=None)
    seed.set("key", 42)
    seed.close()

    front = Cache.memory_store(max_items=8, concurrency="single", shards=1)
    backing = Cache.sqlite_store(tmp_path / "cache.db")
    cache = Cache.tiered(front=front, backing=backing, value_mode="reference")
    assert cache.get("key") == 42
    # Closing the backing connection demonstrates that the second read is served by the front.
    backing.close()
    assert cache.get("key") == 42
    cache.close()
