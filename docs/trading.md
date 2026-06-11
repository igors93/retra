# Low-Latency and Trading Guidance

Retra is pure Python. It can minimize library overhead, but it cannot guarantee hard real-time
latency or replace a native market-data, risk, or order-state engine.

## Appropriate uses

- deterministic derived calculations;
- feature and indicator memoization;
- instrument metadata;
- conversion tables;
- local strategy intermediates;
- repeatable pure-function results.

## Inappropriate uses as the sole source of truth

- official positions;
- order lifecycle state;
- risk limits;
- balances;
- exchange sequence state;
- unreconstructable transactional state.

## Recommended configuration for one strategy thread

```python
cache = Cache.memory(
    profile="speed",
    max_items=200_000,
)
```

Use immutable return types or ensure callers never mutate references. Use integer ticks and lots for
financial values. Model market, risk, and configuration changes with generation counters instead of
relying only on time-based expiration.

## Fail closed

The default error mode raises store failures. Critical applications should not switch to
`ErrorMode.CONTINUE` unless a cache miss has a well-defined safe behavior.

## Warm-up

Before a latency-sensitive phase:

- create caches and decorated functions;
- populate frequently used keys;
- run representative calls;
- avoid persistent tiers on the critical path;
- measure on the target Python build and hardware;
- monitor tail latency, not only averages.
