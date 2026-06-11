from __future__ import annotations

import asyncio

from retra import AsyncCache

cache = AsyncCache.memory(profile="balanced")


@cache.cached(ttl="1s")
async def fetch(identifier: int) -> dict[str, int]:
    print("fetching")
    await asyncio.sleep(0.05)
    return {"id": identifier}


async def main() -> None:
    print(await asyncio.gather(fetch(1), fetch(1), fetch(1)))


asyncio.run(main())
