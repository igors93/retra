from __future__ import annotations

from retra import Cache

cache = Cache.memory(profile="precise")
market = cache.generation("market")
model = cache.generation("model")


@cache.cached(dependencies=(market, model))
def signal(instrument_id: int) -> int:
    print("recomputing signal")
    return instrument_id * 10


print(signal(7))
print(signal(7))
market.advance()
print(signal(7))
