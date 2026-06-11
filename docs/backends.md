# Backends

## MemoryBackend

`MemoryBackend` uses a dictionary protected by a re-entrant lock. It is the fastest backend,
but values disappear when the process exits and are not shared between processes.

## FileBackend

`FileBackend` stores one JSON envelope per cache entry. Payload bytes are Base64 encoded. File
names are SHA-256 hashes of storage keys and are distributed into subdirectories.

Writes follow this sequence:

1. write to a temporary file in the destination directory;
2. flush and synchronize the file;
3. atomically replace the final path with `os.replace`.

This prevents readers from observing partial writes. Cross-process writes use last-writer-wins
semantics; explicit inter-process locking is not included in version 0.1.

## SQLiteBackend

`SQLiteBackend` stores entries in a `retra_entries` table and uses an upsert for writes. WAL mode
is enabled for file databases by default. A re-entrant lock protects the shared connection from
concurrent thread access.

`delete_expired(now)` is available for opportunistic maintenance. Normal cache reads also remove
an expired entry when it is encountered.

## Adding a backend

A custom backend must implement:

```python
def get(key: str) -> CacheEntry | None: ...
def set(entry: CacheEntry) -> None: ...
def delete(key: str) -> bool: ...
def clear() -> None: ...
def close() -> None: ...
```

Run the backend contract tests against every new implementation.
