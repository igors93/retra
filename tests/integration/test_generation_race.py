from __future__ import annotations

import pytest

from retra import Cache, GenerationRaceError


def test_generation_change_during_compute_retries() -> None:
    cache = Cache.memory(
        concurrency="single",
        value_mode="reference",
        generation_retries=1,
    )
    dependency = cache.generation("market")
    calls = 0

    @cache.cached(dependencies=(dependency,))
    def value() -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            dependency.advance()
        return calls

    assert value() == 2
    assert calls == 2


def test_repeated_generation_changes_raise() -> None:
    cache = Cache.memory(
        concurrency="single",
        value_mode="reference",
        generation_retries=1,
    )
    dependency = cache.generation("market")

    @cache.cached(dependencies=(dependency,))
    def value() -> int:
        dependency.advance()
        return 1

    with pytest.raises(GenerationRaceError):
        value()
