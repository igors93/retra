"""Regression tests: generation counters survive SQLite store restart."""

from __future__ import annotations

import pytest

from retra import MISSING, Cache


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "cache.db"


def test_namespace_generation_survives_restart(db_path) -> None:
    """After invalidate_all() + close, reopening the store must restore the generation."""
    cache1 = Cache.sqlite(db_path, value_mode="reference")
    cache1.set("key", "value")
    assert cache1.get("key") == "value"

    cache1.invalidate_all()
    assert cache1.get("key") is MISSING, "entry must be logically invisible after invalidate_all"
    cache1.close()

    cache2 = Cache.sqlite(db_path, value_mode="reference")
    # Old entry is physically present but namespace generation has advanced — must be invisible.
    assert cache2.get("key") is MISSING, (
        "entry written before invalidate_all must remain invisible after restart"
    )
    cache2.close()


def test_function_generation_survives_restart(db_path) -> None:
    """After fn.clear() + close, reopening must keep the function generation advanced."""
    cache1 = Cache.sqlite(db_path, value_mode="reference")
    calls = 0

    @cache1.cached()
    def compute(x: int) -> int:
        nonlocal calls
        calls += 1
        return x * 2

    compute(5)
    assert calls == 1
    compute.clear()  # advances function generation and persists it
    cache1.close()

    cache2 = Cache.sqlite(db_path, value_mode="reference")
    calls = 0

    @cache2.cached()
    def compute(x: int) -> int:
        nonlocal calls
        calls += 1
        return x * 2

    compute(5)  # old entry from cache1 has stale function_generation → recompute
    assert calls == 1, "compute must have been called once (old entry was invalidated)"
    cache2.close()


def test_two_namespaces_on_same_db_do_not_share_entries(db_path) -> None:
    """Different namespace strings must produce disjoint logical key spaces."""
    cache_a = Cache.sqlite(db_path, namespace="alpha", value_mode="reference")
    cache_b = Cache.sqlite(db_path, namespace="beta", value_mode="reference")

    cache_a.set("shared_key", "from_alpha")
    assert cache_b.get("shared_key") is MISSING, (
        "namespace beta must not see entries written by namespace alpha"
    )

    cache_b.set("shared_key", "from_beta")
    assert cache_a.get("shared_key") == "from_alpha", "namespace alpha must keep its own value"
    assert cache_b.get("shared_key") == "from_beta"

    cache_a.close()
    cache_b.close()


def test_invalidate_all_on_one_namespace_does_not_affect_other(db_path) -> None:
    """invalidate_all() must only advance its own namespace generation."""
    cache_a = Cache.sqlite(db_path, namespace="alpha", value_mode="reference")
    cache_b = Cache.sqlite(db_path, namespace="beta", value_mode="reference")

    cache_a.set("k", 1)
    cache_b.set("k", 2)

    cache_a.invalidate_all()

    assert cache_a.get("k") is MISSING, "alpha entry must be logically invisible"
    assert cache_b.get("k") == 2, "beta entry must be unaffected by alpha invalidation"

    cache_a.close()
    cache_b.close()


def test_new_entries_after_restart_are_visible(db_path) -> None:
    """Entries written after reopening are visible with the restored generation."""
    cache1 = Cache.sqlite(db_path, value_mode="reference")
    cache1.invalidate_all()
    cache1.close()

    cache2 = Cache.sqlite(db_path, value_mode="reference")
    cache2.set("new_key", "new_value")
    assert cache2.get("new_key") == "new_value"
    cache2.close()
