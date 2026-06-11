from __future__ import annotations

from dataclasses import dataclass

from retra import Cache

cache = Cache.memory(profile="balanced")


@dataclass
class Order:
    identifier: int
    payload: dict[str, object]


@cache.cached(key=lambda order: order.identifier)
def normalize(order: Order) -> int:
    return order.identifier


print(normalize(Order(10, {"large": "payload"})))
