# Retra Architecture

Retra is a complete rewrite of the original Retra experiment. The old design routed memory,
file, and SQLite operations through nearly identical serialized records. That made the code easy to
organize, but it made memory hits pay for work that only persistent storage needs.

The architecture starts from the opposite direction: optimize the memory hit path first, then
place slower and less frequent work behind explicit boundaries.

## Design goal

For a decorated function with a valid memory entry, Retra should do only this:

1. Build an exact key using a preselected key plan.
2. Check the one-entry inline slot.
3. Check the selected memory engine if the inline slot misses.
4. Prove generation and deadline validity.
5. Return the already prepared Python object.

The hit path must not perform signature inspection, serialization, persistent I/O, cache-policy
selection, miss locking, logging callbacks, or global cleanup.

## Main components

```text
Decorated function
       |
       v
CompiledCallPlan -----> exact key
       |
       v
InlineSlot
       |
       v
Memory engine or explicit persistent store
       |
       v
CacheRecord
```

### CompiledCallPlan

A function signature is inspected once when `@cache.cached()` is applied. Retra renders a wrapper
with the original call signature and embeds the chosen key and validity operations in generated
Python source. Calls with signatures that cannot be safely rendered use a generic fallback.

### Key plans

Retra selects one plan at decoration time:

- constant plan for no-argument functions;
- scalar plan for one key parameter;
- tuple plan for several parameters;
- canonical plan for mutable or complex values;
- custom plan when the user supplies a key function.

Types are part of exact keys. `True`, `1`, `1.0`, `0.0`, and `-0.0` are distinct by default.

### InlineSlot

Every compiled function may keep its last key and record in a one-entry slot. Workloads that repeat
one key can avoid even the main dictionary lookup. The full key and all validity metadata are still
checked, so the inline slot cannot weaken correctness.

### CacheRecord

A record contains:

```text
value
created_ns
deadline_ns
namespace_generation
function_generation
dependency_versions
```

Memory stores keep `value` as the original prepared Python object. Persistent stores serialize only
when writing outside process memory.

## Memory engines

Retra provides three engines because no synchronization strategy is optimal for every workload.
The engine is chosen when the cache is built, not during each request.

### SingleThreadEngine

- no locks;
- mutable bounded table;
- fastest pure-Python mode;
- caller must guarantee single-thread access.

### SnapshotEngine

- lock-free reads;
- immutable shard snapshots;
- copy-on-write updates;
- intended for many reads and relatively few writes;
- FIFO eviction, because exact LRU would mutate on every hit.

### LockedEngine

- lock per shard;
- portable thread-safe behavior;
- supports FIFO and exact LRU;
- intended for mixed read/write workloads.

## Invalidation

Retra uses generation counters. Clearing a decorated function increments its function generation;
invalidating the entire cache increments the namespace generation. Old entries remain physically
present until overwritten or pruned, but every lookup rejects them immediately.

This makes logical group invalidation O(1).

External dependencies can be represented by named `Generation` objects. Retra snapshots the
versions before computation and checks them again afterwards. If a dependency changes during the
computation, Retra retries. Repeated changes raise `GenerationRaceError` rather than caching a
result whose validity cannot be proved.

## Miss coordination

Hits never acquire a miss lock. On a miss:

1. a striped lock is selected from the exact key hash;
2. the entry is checked again after acquiring the lock;
3. one caller computes and stores the result;
4. waiting callers read the newly stored result.

The number of locks is fixed, so lock bookkeeping cannot grow with the cache.

## Persistence

Persistence is explicit.

- `MemoryStore` keeps Python objects directly.
- `SQLiteStore` stores canonical keys, serialized payloads, metadata, and checksums.
- `FileStore` stores a binary, versioned envelope with atomic replacement.
- `TieredStore` explicitly combines a memory front and persistent backing store.

A tiered store may perform I/O after a front miss. A memory-only cache never does hidden I/O.

## Error model

`ErrorMode.RAISE` is the default because silently returning an uncertain result conflicts with the
precision goal. `ErrorMode.CONTINUE` is available for non-critical caches where infrastructure
failure should become a miss.

Function exceptions are never treated as store errors and are never cached automatically.
