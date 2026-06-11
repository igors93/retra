"""Store and retrieve values manually."""

from retra import Cache
from retra.backends import MemoryBackend

cache = Cache(MemoryBackend())
cache.set("user:42", {"name": "Ada Lovelace"}, ttl=60)

print(cache.get("user:42"))
print(cache.stats().as_dict())
