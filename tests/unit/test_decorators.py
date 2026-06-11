from __future__ import annotations

import inspect

from retra import MISSING, Cache


def test_compiled_wrapper_preserves_signature_and_caches_defaults() -> None:
    cache = Cache.memory(concurrency="single", value_mode="reference", stats="exact")
    calls = 0

    @cache.cached()
    def add(left: int, right: int = 1, *, scale: int = 1) -> int:
        nonlocal calls
        calls += 1
        return (left + right) * scale

    assert str(inspect.signature(add)) == (
        "(left: 'int', right: 'int' = 1, *, scale: 'int' = 1) -> 'int'"
    )
    assert add(2, scale=2) == 6
    assert add(left=2, right=1, scale=2) == 6
    assert calls == 1
    assert "inspect" not in add.__source__


def test_compiled_wrapper_distinguishes_bool_int_and_float() -> None:
    cache = Cache.memory(concurrency="single", value_mode="reference", stats="off")
    calls = 0

    @cache.cached()
    def identity(value):
        nonlocal calls
        calls += 1
        return type(value).__name__

    assert identity(True) == "bool"
    assert identity(1) == "int"
    assert identity(1.0) == "float"
    assert calls == 3


def test_zero_and_negative_zero_are_distinct_keys() -> None:
    cache = Cache.memory(concurrency="single", value_mode="reference", stats="off")
    calls = 0

    @cache.cached()
    def sign(value: float) -> str:
        nonlocal calls
        calls += 1
        return value.hex()

    assert sign(0.0) != sign(-0.0)
    assert calls == 2


def test_decorator_tools_work_without_executing_function() -> None:
    cache = Cache.memory(concurrency="single", value_mode="reference")
    calls = 0

    @cache.cached()
    def double(value: int) -> int:
        nonlocal calls
        calls += 1
        return value * 2

    assert double.peek(2) is MISSING
    assert double(2) == 4
    assert double.contains(2)
    assert double.peek(2) == 4
    assert double.invalidate(2)
    assert double.peek(2) is MISSING
    assert double.bypass(2) == 4
    assert calls == 2


def test_refresh_forces_recomputation() -> None:
    cache = Cache.memory(concurrency="single", value_mode="reference")
    calls = 0

    @cache.cached()
    def value() -> int:
        nonlocal calls
        calls += 1
        return calls

    assert value() == 1
    assert value() == 1
    assert value.refresh() == 2
    assert value() == 2


def test_function_clear_uses_generation_invalidation() -> None:
    cache = Cache.memory(concurrency="single", value_mode="reference")
    calls = 0

    @cache.cached()
    def value(number: int) -> int:
        nonlocal calls
        calls += 1
        return number

    value(1)
    value.clear()
    value(1)
    assert calls == 2


def test_dependency_generation_invalidates_result() -> None:
    cache = Cache.memory(concurrency="single", value_mode="reference")
    market = cache.generation("market")
    calls = 0

    @cache.cached(dependencies=(market,))
    def signal(instrument: int) -> int:
        nonlocal calls
        calls += 1
        return instrument * calls

    assert signal(10) == 10
    assert signal(10) == 10
    market.advance()
    assert signal(10) == 20


def test_cache_if_can_reject_a_result() -> None:
    cache = Cache.memory(concurrency="single", value_mode="reference")
    calls = 0

    @cache.cached(cache_if=lambda result: result is not None)
    def maybe_value() -> None:
        nonlocal calls
        calls += 1
        return None

    maybe_value()
    maybe_value()
    assert calls == 2


def test_ignored_parameter_is_not_part_of_key() -> None:
    cache = Cache.memory(concurrency="single", value_mode="reference")
    calls = 0

    @cache.cached(ignore_parameters=("trace_id",))
    def calculate(value: int, trace_id: str) -> int:
        nonlocal calls
        calls += 1
        return value * 2

    assert calculate(2, "a") == 4
    assert calculate(2, "b") == 4
    assert calls == 1


def test_custom_key_plan() -> None:
    cache = Cache.memory(concurrency="single", value_mode="reference")
    calls = 0

    @cache.cached(key=lambda user_id, verbose=False: user_id)
    def user(user_id: int, verbose: bool = False) -> tuple[int, bool]:
        nonlocal calls
        calls += 1
        return user_id, verbose

    assert user(1, False) == (1, False)
    assert user(1, True) == (1, False)
    assert calls == 1
