# Architecture

Retra separates cache coordination from storage and serialization.

```text
Decorated function or manual API
              |
              v
            Cache
       /       |       \
KeyBuilder  Serializer  Clock
              |
              v
          CacheEntry
              |
              v
           Backend
```

## Responsibilities

### Cache

`Cache` owns the behavior shared by every storage strategy:

- namespace qualification;
- TTL calculation and expiration checks;
- serialization and deserialization;
- hit, miss, write, deletion, expiration, and error statistics;
- fail-open error handling;
- per-key thread locking for `get_or_set` and decorated functions.

### Backend

A backend stores and retrieves `CacheEntry` objects. It does not execute functions,
serialize Python values, generate function keys, or decide whether an entry is expired.

### Serializer

A serializer converts Python values to bytes and restores them. Keeping serialization out of
the backends means one backend can be used with JSON, Pickle, or a future custom format.

### KeyBuilder

A key builder converts a function identity and its bound arguments into a deterministic key.
The default implementation normalizes common Python values and hashes the result with SHA-256.

## Dependency direction

High-level modules depend on protocols rather than concrete backends. New backends should
implement `Backend` without requiring changes to `Cache` or the decorator.

## Concurrency model

Memory, file, and SQLite backends protect their own state with thread locks. `Cache.get_or_set`
also uses a per-key lock, which prevents duplicate computation among threads sharing one cache
instance. Independent processes are not coordinated by this lock.
