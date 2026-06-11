"""Use a domain-specific function key."""

from dataclasses import dataclass

from retra import Cache
from retra.backends import MemoryBackend


@dataclass(frozen=True)
class User:
    identifier: int
    name: str


cache = Cache(MemoryBackend())


@cache.cached(key=lambda user: str(user.identifier), ttl=60)
def build_profile(user: User) -> dict[str, object]:
    return {"id": user.identifier, "display_name": user.name.upper()}


print(build_profile(User(7, "Ada")))
