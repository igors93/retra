"""Persist values in a SQLite database."""

from retra import Cache

with Cache.sqlite(".retra/example.db") as cache:
    cache.set("report:latest", {"status": "ready"}, ttl="5m")
    print(cache.get("report:latest"))
