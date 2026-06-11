# Performance Model

Retra optimizes the shape of work rather than promising one universal latency number.
Performance depends on Python version, CPU, operating system, argument types, selected engine,
value policy, and cache hit distribution.

## Hot-path rules

A memory hit should avoid:

- `inspect.signature()`;
- `Signature.bind()`;
- Pickle or JSON;
- SQLite and file access;
- miss locks;
- cleanup scans;
- synchronous callbacks;
- copying values unless `value_mode="copy"` was explicitly selected;
- clock reads when a decorated function has no TTL.

## Profiles

### `profile="speed"`

- single-thread engine;
- reference value mode;
- exact typed keys;
- FIFO eviction;
- inline cache enabled;
- statistics disabled;
- errors raised.

Use this only when one thread owns the cache and callers do not mutate cached values.

### `profile="balanced"`

- shard-locked engine;
- frozen values;
- basic approximate counters;
- exact typed keys;
- FIFO eviction.

### `profile="precise"`

- shard-locked engine;
- frozen values;
- exact counters;
- exact typed keys;
- fail-closed store errors.

Exact counters add synchronization and are intended for validation or lower-volume systems.

## Key cost

Primitive keys such as integers, strings, bytes, and tuples take the fast exact path. Mutable and
complex values are converted to deterministic binary components. That conversion is intentionally
more expensive because it snapshots the key and prevents later mutation from changing its meaning.

A custom key function can reduce key cost for domain objects:

```python
@cache.cached(key=lambda order: order.identifier)
def price_order(order):
    ...
```

## Eviction cost

FIFO does not update recency on hits and is therefore the default. Exact LRU can improve hit rate
for some workloads but requires mutation on every hit and may increase contention.

## Measuring correctly

Use `pyperf` for stable measurements and compare at least:

- direct dictionary lookup;
- `functools.cache`;
- Retra speed profile;
- Retra balanced profile;
- hit and miss separately;
- primitive and canonical keys;
- p50, p99, and maximum in the actual application.

`benchmarks/bench_hot_path.py` provides a starting point. Do not publish numbers from virtualized
or power-saving environments without explaining the limitations.

## Performance regression policy

Changes to the following modules should include benchmark results:

- `compiler/`;
- `keys/`;
- `engines/`;
- `stores/memory.py`;
- generation validity checks.

A slower hot path may still be accepted when it fixes correctness, but the tradeoff must be explicit.
