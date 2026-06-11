from __future__ import annotations

from retra import Cache

# One strategy thread owns this cache. Prices and quantities use integer ticks/lots.
cache = Cache.memory(profile="speed", max_items=200_000)
market_generation = cache.generation("market")
risk_generation = cache.generation("risk")


@cache.cached(dependencies=(market_generation, risk_generation))
def order_notional(price_ticks: int, quantity_lots: int, contract_multiplier: int) -> int:
    return price_ticks * quantity_lots * contract_multiplier


print(order_notional(125_500, 4, 1))
market_generation.advance()
print(order_notional(125_500, 4, 1))
