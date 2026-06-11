# Retra

Retra is a small, modular cache library for Python. It stores computed values in memory,
individual files, or SQLite so repeated work can be avoided.

> Status: early alpha. The public API is intentionally small, but may still change before 1.0.

## Features

- Manual `get`, `set`, `delete`, and `clear` operations.
- Function caching through `@cache.cached(...)`.
- Time-to-live (TTL) support.
- Memory, file, and SQLite backends.
- JSON and Pickle serializers.
- Deterministic function keys.
- Per-key locks to reduce duplicate work inside one process.
- Basic hit, miss, write, expiration, deletion, and error statistics.
- Fail-open behavior when cache infrastructure is unavailable.

## Installation

From the project directory:

```bash
python -m pip install -e .
```

For development:

```bash
python -m pip install -e ".[dev]"
pytest
```

## Basic usage

```python
from retra import Cache
from retra.backends import MemoryBackend

cache = Cache(MemoryBackend())

cache.set("user:42", {"name": "Ada"}, ttl=60)
print(cache.get("user:42"))
```

## Function caching

```python
from retra import Cache
from retra.backends import MemoryBackend

cache = Cache(MemoryBackend())

@cache.cached(ttl=30)
def expensive_sum(left: int, right: int) -> int:
    return left + right

assert expensive_sum(2, 3) == 5
assert expensive_sum(2, 3) == 5  # Returned from cache.
```

## Persistent cache

```python
from retra import Cache
from retra.backends import SQLiteBackend

with Cache(SQLiteBackend(".cache/retra.db")) as cache:
    cache.set("report:today", {"status": "ready"}, ttl=300)
```

## Serialization warning

`PickleSerializer` supports many Python objects, but Pickle data must only be loaded from
trusted storage. Use `JsonSerializer` when interoperability and safer data handling matter
more than support for arbitrary Python objects.

## Current limitations

- Decorated asynchronous functions are not supported yet.
- Per-key locking coordinates threads in one process, not independent processes.
- File backend writes are atomic, but process-wide lock coordination is intentionally left to
  a future release.

See the `docs/` directory for architecture and API details.
