# Concurrency

## Selecting an engine

Use `concurrency="single"` when one thread owns the cache. It has no synchronization and provides
the shortest path.

Use `concurrency="read_heavy"` when readers dominate and writes are uncommon. Readers take an
immutable shard snapshot without a lock. Writers copy and publish one shard.

Use `concurrency="balanced"` for portable thread-safe mixed workloads. Operations lock only the
selected shard.

## Miss gates

A hit does not acquire a miss gate. Multiple callers missing the same key coordinate through a
fixed array of striped locks. A caller always checks the store again after acquiring a lock.

This pattern suppresses duplicate computation without allocating one lock per key.

## Async functions

`AsyncCache` uses `asyncio.Lock` stripes. The decorated function is awaited only by the winning
caller; waiters read the stored result afterwards.

Persistent stores use synchronous standard-library I/O. Do not place a disk-backed `AsyncCache`
directly on a latency-sensitive event loop. Use a memory cache, isolate I/O in an executor, or use
an explicit tier whose misses are acceptable.

## Snapshot consistency

A snapshot-engine reader observes either the state published before a write or the state published
after it. It never observes a partially updated dictionary. This is appropriate for a cache: a
concurrent invalidation may win immediately after a reader captured the previous snapshot, but that
reader's result was valid at the linearization point where it captured the state.

## Process boundaries

The in-memory engines coordinate threads inside one process. They do not synchronize separate
Python processes. SQLite safely persists values, but Retra does not currently provide a
cross-process single-flight lease. Applications that require one computation across processes must
coordinate above Retra or use process-local caches.
