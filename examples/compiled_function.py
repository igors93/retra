from __future__ import annotations

from retra import Cache

cache = Cache.memory(profile="speed", max_items=10_000)


@cache.cached()
def notional(price_ticks: int, quantity: int, multiplier: int = 1) -> int:
    print("computing")
    return price_ticks * quantity * multiplier


print(notional(125_500, 4))
print(notional(125_500, 4))
print(notional.__source__)
