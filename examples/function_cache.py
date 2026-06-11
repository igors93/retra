"""Cache repeated calls to a synchronous function."""

from retra import Cache

cache = Cache.memory(concurrency="single", stats="basic")


@cache.cached(ttl="30s")
def fibonacci(number: int) -> int:
    if number < 2:
        return number
    return fibonacci(number - 1) + fibonacci(number - 2)


print(fibonacci(30))
print(cache.stats())
