# API

## Cache

```python
Cache(
    backend,
    *,
    serializer=None,
    config=None,
    key_builder=None,
    clock=None,
)
```

The default serializer is `PickleSerializer`, the default configuration is `CacheConfig()`, and
the default key builder is `FunctionKeyBuilder()`.

### Manual operations

```python
cache.set("key", value, ttl=60)
value = cache.get("key", default=None)
exists = cache.contains("key")
deleted = cache.delete("key")
cache.clear()
```

`ttl=None` means no expiration. A TTL of zero skips storage. Negative values are rejected.

### Compute-on-miss

```python
value = cache.get_or_set("report", build_report, ttl=300)
```

The factory is called only after two cache checks under a per-key lock.

### Decorator

```python
@cache.cached(ttl=30, version="2")
def calculate(value: int) -> int:
    return value * 2
```

Decorated functions receive helper attributes:

```python
calculate.cache_key(10)
calculate.cache_invalidate(10)
calculate.cache_clear()
calculate.cache_instance
```

These attributes are attached dynamically and are intended for runtime use.

### Statistics

```python
snapshot = cache.stats()
print(snapshot.hits)
print(snapshot.misses)
print(snapshot.hit_rate)
```

Use `cache.reset_stats()` to reset all counters.
