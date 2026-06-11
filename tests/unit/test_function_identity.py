"""Regression tests: distinct function objects never share cache entries."""

from __future__ import annotations

from retra import Cache


def make_adder(n: int):
    def add(x: int) -> int:
        return x + n

    return add


def test_closures_with_same_qualname_do_not_share_cache() -> None:
    """Two closures from the same factory have the same __qualname__.

    Before the identity fix, both would resolve to the same cache key prefix and
    the second closure would return a stale hit from the first closure's entry.
    add1(10) = 11, add2(10) = 12; if broken add2 returns 11 (add1's cached result).
    """
    cache = Cache.memory(concurrency="single", value_mode="reference", stats="exact")
    add1 = cache.cached()(make_adder(1))
    add2 = cache.cached()(make_adder(2))

    assert add1(10) == 11
    assert add2(10) == 12, "add2 must compute independently — must not return add1's cached 11"


def test_closures_with_same_qualname_record_separate_hits() -> None:
    cache = Cache.memory(concurrency="single", value_mode="reference", stats="exact")
    calls: dict[str, int] = {"a": 0, "b": 0}

    def make_counter(name: str):
        def fn(x: int) -> int:
            calls[name] += 1
            return x

        return fn

    fa = cache.cached()(make_counter("a"))
    fb = cache.cached()(make_counter("b"))

    fa(1)
    fa(1)  # hit
    fb(1)
    fb(1)  # hit

    assert calls["a"] == 1, "fa should have been computed exactly once"
    assert calls["b"] == 1, "fb should have been computed exactly once"


def test_lambdas_with_same_qualname_do_not_share_cache() -> None:
    """Lambdas defined in the same scope share __qualname__ == '<locals>.<lambda>'.

    Each must be decorated independently and receive its own identity.
    """
    cache = Cache.memory(concurrency="single", value_mode="reference", stats="exact")
    fns = [cache.cached()(lambda x, _i=i: x * _i) for i in range(3)]

    assert fns[0](5) == 0
    assert fns[1](5) == 5
    assert fns[2](5) == 10


def test_same_function_object_decorated_twice_shares_cache() -> None:
    """Decorating the *same* function object twice intentionally shares the same cache.

    Both wrappers have the same id(function) so they resolve to the same identity — by design.
    This is different from two distinct closures that happen to have the same qualname.
    """
    cache = Cache.memory(concurrency="single", value_mode="reference", stats="exact")
    calls = 0

    def base(x: int) -> int:
        nonlocal calls
        calls += 1
        return x

    decorated_a = cache.cached()(base)
    decorated_b = cache.cached()(base)

    assert decorated_a(7) == 7
    assert calls == 1
    assert decorated_b(7) == 7, "same function identity → shared cache hit"
    assert calls == 1, "both wrappers share the same cache entry"
