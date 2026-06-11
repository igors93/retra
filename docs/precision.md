# Precision and Correctness

Retra uses "precision" to mean that a hit is returned only when the library can prove that the
stored value belongs to the exact key and remains valid under the configured rules.

## Exact typed keys

Python normally considers some values equal across types:

```python
True == 1
1 == 1.0
0.0 == -0.0
```

Retra exact keys include type identity. Floating-point values are represented by their binary bits,
which also keeps positive and negative zero distinct.

For monetary calculations, applications should still prefer integer ticks or a deliberate decimal
model. Cache key precision cannot fix imprecise arithmetic performed by the cached function.

## Full-key verification

Persistent stores use a digest to find candidate rows or files, but they also store the complete
canonical key. A digest collision therefore produces another comparison, not a false hit.

## Mutable arguments

Lists, mappings, sets, dataclasses, and custom values are snapshotted into canonical key bytes.
Unsupported domain objects must provide `__cache_key__()` or a custom decorator key function.
Retra does not inspect arbitrary `__dict__` data because that can include unstable or irrelevant
state.

## Mutable results

`value_mode="frozen"` converts common mutable containers once on the miss path:

- `dict` becomes `FrozenDict`;
- `list` becomes `tuple`;
- `set` becomes `frozenset`;
- `bytearray` becomes `bytes`.

Hits can then return the same protected object without a copy. `reference` is faster but requires
callers not to mutate the value. `copy` provides compatibility at the cost of copying on every read.

## Validity

A decorated entry may depend on:

- namespace generation;
- function generation;
- explicit external generations;
- TTL deadline.

All configured checks must pass. TTL uses monotonic nanoseconds for process-local memory stores and
wall-clock nanoseconds for persistent stores.

## Generation races

Retra snapshots generations before calling the original function and validates them afterwards.
When a dependency changed during computation, Retra retries. When stability cannot be obtained
within the configured retry count, it raises `GenerationRaceError` and stores nothing.

## Corruption

Persistent entries carry checksums. Corrupted entries raise `CorruptedEntryError` in the default
error mode. File writes use temporary files, flush, `fsync`, and atomic replacement.
