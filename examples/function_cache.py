"""Cache repeated calls to a synchronous function."""

from retra import Cache
from retra.backends import MemoryBackend

cache = Cache(MemoryBackend())


@cache.cached(ttl=30)
def fibonacci(number: int) -> int:
    if number < 2:
        return number
    return fibonacci(number - 1) + fibonacci(number - 2)


print(fibonacci(30))
print(cache.stats().as_dict())
