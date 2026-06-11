"""Persist values in a SQLite database."""

from retra import Cache
from retra.backends import SQLiteBackend

with Cache(SQLiteBackend(".retra/example.db")) as cache:
    cache.set("report:latest", {"status": "ready"}, ttl=300)
    print(cache.get("report:latest"))
