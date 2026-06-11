"""Run stable hot-path benchmarks with pyperf.

Execute from the project root after installing the development dependencies:

    python benchmarks/bench_hot_path.py
"""

from __future__ import annotations

import functools

import pyperf

from retra import Cache

DIRECT = {("f", int, 10, int, 20): 30}


@functools.cache
def stdlib_add(left: int, right: int) -> int:
    return left + right


speed_cache = Cache.memory(profile="speed", max_items=1024)


@speed_cache.cached()
def retra_add(left: int, right: int) -> int:
    return left + right


balanced_cache = Cache.memory(profile="balanced", max_items=1024)


@balanced_cache.cached()
def balanced_add(left: int, right: int) -> int:
    return left + right


stdlib_add(10, 20)
retra_add(10, 20)
balanced_add(10, 20)


def direct_dict_lookup() -> int:
    return DIRECT[("f", int, 10, int, 20)]


def main() -> None:
    runner = pyperf.Runner()
    runner.metadata["description"] = "Retra memory-hit comparison"
    runner.bench_func("dict-hit", direct_dict_lookup)
    runner.bench_func("functools-cache-hit", stdlib_add, 10, 20)
    runner.bench_func("retra-speed-hit", retra_add, 10, 20)
    runner.bench_func("retra-balanced-hit", balanced_add, 10, 20)


if __name__ == "__main__":
    main()
