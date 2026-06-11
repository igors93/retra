"""Persist JSON-compatible values as individual cache files."""

from retra import Cache
from retra.serializers import JsonSerializer

with Cache.file(".retra/files", serializer=JsonSerializer()) as cache:
    cache.set("settings", {"theme": "dark", "language": "en"})
    print(cache.get("settings"))
