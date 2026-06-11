# Retra

Retra is a precision-first cache and memoization library written entirely in Python.
It is designed so that a memory-cache hit performs only the work required to prove that the
cached value still belongs to the exact call and is still valid.

> **Status: alpha — 0.1.0.** This is the first PyPI-ready release of the current
> architecture. APIs may still change before 1.0. Not recommended for production use without
> pinning the exact version.

## Core principles

- Python objects are stored directly in memory; memory hits never serialize or deserialize.
- Function signatures are inspected once, when a decorator is created.
- Decorated wrappers use compiled call plans and specialized key plans.
- Exact typed keys keep `True`, `1`, `1.0`, `0.0`, and `-0.0` distinct.
- Full keys prove identity; digests are only persistent-storage indexes.
- Generation counters invalidate groups of values in O(1).
- Locks are kept out of the normal hit path whenever the selected engine permits it.
- Persistent stores are explicit and never hidden behind a memory-only cache.

## Installation

```bash
python -m pip install -e ".[dev]"
```

## Fast memory cache

```python
from retra import Cache

cache = Cache.memory(
    max_items=100_000,
    concurrency="single",
    value_mode="frozen",
    stats="off",
)

@cache.cached()
def notional(price_ticks: int, quantity: int) -> int:
    return price_ticks * quantity

assert notional(125_500, 4) == 502_000
assert notional(125_500, 4) == 502_000  # Memory hit.
```

## Generation-based invalidation

```python
market = cache.generation("market")

@cache.cached(dependencies=(market,))
def signal(instrument_id: int) -> int:
    return instrument_id * 10

signal(7)
market.advance()  # Every dependent result becomes invalid immediately.
signal(7)         # Recomputed.
```

## Persistent cache

```python
from retra import Cache

cache = Cache.sqlite(".cache/retra.db")
cache.set("report:today", {"status": "ready"}, ttl="5m")
```

## Explicit two-tier cache

```python
cache = Cache.tiered(
    front=Cache.memory_store(max_items=10_000),
    backing=Cache.sqlite_store(".cache/retra.db"),
)
```

A tiered cache may perform disk I/O on a front-cache miss. Use a memory-only cache when a
request must never touch persistent storage.

## Development

```bash
pytest
ruff check .
mypy
python benchmarks/bench_hot_path.py
```

Read `docs/architecture.md`, `docs/performance.md`, and `docs/precision.md` before changing
the hot path.
