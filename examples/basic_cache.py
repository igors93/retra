from __future__ import annotations

from retra import MISSING, Cache

cache = Cache.memory(profile="balanced", max_items=1_000)

cache.set("instrument:PETR4", {"tick_size": 1, "currency": "BRL"}, ttl="5m")

value = cache.get("instrument:PETR4")
assert value is not MISSING
print(value)
