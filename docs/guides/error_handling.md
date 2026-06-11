# Error handling

Retra distinguishes configuration, key generation, serialization, backend, and corrupted-entry
errors through subclasses of `RetraError`.

## Fail-open mode

`CacheConfig(fail_open=True)` is the default. Backend and serialization failures are logged,
counted in statistics, and treated as cache misses or skipped writes. The wrapped application
function can continue to operate without the cache.

## Strict mode

Use strict mode when cache failures must be visible to the caller:

```python
from retra import Cache, CacheConfig

cache = Cache(
    backend,
    config=CacheConfig(fail_open=False),
)
```

Known Retra exceptions are propagated. Unexpected storage failures are wrapped in `BackendError`.

## Function errors

Exceptions raised by the original function are never cached. They propagate normally because the
factory must finish successfully before Retra serializes and stores its result.
