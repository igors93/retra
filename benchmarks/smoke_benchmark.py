"""Small, non-scientific benchmark used as a local development smoke test."""

from __future__ import annotations

import functools
import platform
import statistics
import sys
import timeit

from retra import Cache


@functools.cache
def stdlib_add(left: int, right: int) -> int:
    return left + right


speed = Cache.memory(profile="speed", max_items=1_024)


@speed.cached()
def retra_add(left: int, right: int) -> int:
    return left + right


stdlib_add(10, 20)
retra_add(10, 20)


def measure(statement: str, namespace: dict[str, object]) -> tuple[float, float]:
    samples = timeit.repeat(statement, globals=namespace, number=1_000_000, repeat=5)
    nanoseconds = [sample / 1_000_000 * 1_000_000_000 for sample in samples]
    return statistics.median(nanoseconds), min(nanoseconds)


def main() -> None:
    namespace = {"stdlib_add": stdlib_add, "retra_add": retra_add}
    stdlib_median, stdlib_best = measure("stdlib_add(10, 20)", namespace)
    retra_median, retra_best = measure("retra_add(10, 20)", namespace)
    print(f"Python: {sys.version.split()[0]}")
    print(f"Platform: {platform.platform()}")
    print(f"functools.cache median: {stdlib_median:.1f} ns; best: {stdlib_best:.1f} ns")
    print(f"Retra speed median:    {retra_median:.1f} ns; best: {retra_best:.1f} ns")
    print(f"Retra / functools median ratio: {retra_median / stdlib_median:.2f}x")


if __name__ == "__main__":
    main()
