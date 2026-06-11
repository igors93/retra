from __future__ import annotations

from retra import Cache, JsonSerializer

with Cache.sqlite(
    ".cache/retra.db",
    serializer=JsonSerializer(),
    value_mode="reference",
) as cache:
    cache.set("daily-report", {"status": "ready"}, ttl="1h")
    print(cache.get("daily-report"))
