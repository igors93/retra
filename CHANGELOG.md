# Changelog

## 0.1.0 (2026-06-11)

First PyPI-ready release. Complete rewrite from the ground up.

### Added
- Compiled-call architecture: decorator generates a specialised Python function once at
  decoration time using `compile()` / `exec()`, eliminating per-call overhead.
- Exact typed keys that keep `True`, `1`, `1.0`, `0.0`, and `-0.0` distinct.
- One-entry inline cache per decorated function for sub-microsecond repeated hits.
- Single-thread, snapshot/read-heavy, and locked (sharded) memory engines.
- O(1) generation-based invalidation (`invalidate_all()`, per-function `clear()`).
- Reference, frozen (deep-immutable), and copy value modes.
- Striped `MissGate` and `AsyncMissGate` for miss-stampede suppression.
- Direct-object `MemoryStore` with no serialization overhead.
- `SQLiteStore` with WAL mode, canonical-key collision detection, and checksum validation.
- `FileStore` with atomic replacement and BLAKE2b checksums.
- `TieredStore` combining any memory front with any persistent backing.
- Off, basic, sampled, and exact statistics modes.
- Compiled async decorators via `AsyncCache`.
- Generation persistence across restarts for `SQLiteStore`.

### Fixed
- Closures and lambdas with the same `__qualname__` no longer share cache entries in
  memory stores (each decoration gets a unique identity based on `id(function)`).
- Inline cache slot is invalidated after eviction, deletion, or `clear()` via a
  monotonic `store_version` counter on `MemoryStore`.
- `max_items` is truly honoured: `_effective_shards()` clamps shard count so total
  capacity never exceeds the configured limit.
- `close()` now consistently raises `CacheClosedError` on decorated-function misses.
- `JsonSerializer` raises `SerializationError` on non-string mapping keys instead of
  silently converting them to strings.
- `SQLiteStore` persists namespace and function generation counters so `invalidate_all()`
  and `fn.clear()` survive process restarts.
