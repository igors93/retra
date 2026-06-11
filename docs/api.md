# API Guide

## Memory cache

```python
from retra import Cache

cache = Cache.memory(
    profile="balanced",
    max_items=100_000,
)
```

## Manual operations

```python
cache.set("user:42", {"name": "Ada"}, ttl="5m")
value = cache.get("user:42")
exists = cache.contains("user:42")
cache.delete("user:42")
```

`get()` returns `MISSING` by default when no valid value exists. This keeps a cached `None` distinct
from a miss.

Batch operations:

```python
cache.set_many({"a": 1, "b": 2}, ttl="10s")
values = cache.get_many(["a", "b", "c"])
removed = cache.delete_many(["a", "b"])
```

## Decorators

```python
@cache.cached(ttl="50ms")
def calculate(price: int, quantity: int = 1) -> int:
    return price * quantity
```

The returned callable provides:

```python
calculate.cache_key(100, 2)
calculate.peek(100, 2)
calculate.contains(100, 2)
calculate.invalidate(100, 2)
calculate.refresh(100, 2)
calculate.bypass(100, 2)
calculate.clear()
```

`refresh()` always recomputes. `bypass()` neither reads nor writes the cache. `clear()` increments the
function generation and invalidates every call of that function in O(1).

## Dependencies

```python
market = cache.generation("market")
risk = cache.generation("risk")

@cache.cached(dependencies=(market, risk))
def signal(instrument_id: int) -> int:
    ...

market.advance()
```

## Custom keys and ignored parameters

```python
@cache.cached(
    key=lambda order, trace_id=None: order.identifier,
    ignore_parameters=("trace_id",),
)
def process(order, trace_id=None):
    ...
```

Use either a custom key or ignored parameters deliberately. Ignoring a parameter is correct only
when it cannot affect the result.

## Lifetimes

```python
from retra import DO_NOT_CACHE, NEVER_EXPIRE

cache.set("a", 1, ttl=NEVER_EXPIRE)
cache.set("b", 2, ttl=DO_NOT_CACHE)
```

Numeric `ttl=0` also skips storage. `None` means no expiration.

## Async

```python
from retra import AsyncCache

cache = AsyncCache.memory(profile="balanced")

@cache.cached(ttl="1s")
async def fetch(identifier: int):
    ...
```
