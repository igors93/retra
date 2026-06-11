from __future__ import annotations

from retra import Cache

front = Cache.memory_store(max_items=10_000, concurrency="balanced")
backing = Cache.sqlite_store(".cache/tiered.db")
cache = Cache.tiered(front=front, backing=backing, value_mode="reference")

cache.set("reference-data", {"version": 4})
print(cache.get("reference-data"))
