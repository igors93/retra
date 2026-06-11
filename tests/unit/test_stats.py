from retra.stats import CacheStats


def test_stats_snapshot_and_hit_rate() -> None:
    stats = CacheStats()
    stats.increment("hits", 3)
    stats.increment("misses")

    snapshot = stats.snapshot()

    assert snapshot.requests == 4
    assert snapshot.hit_rate == 0.75
    assert snapshot.as_dict()["hits"] == 3


def test_stats_can_be_reset() -> None:
    stats = CacheStats()
    stats.increment("writes", 2)

    stats.reset()

    assert stats.snapshot().writes == 0
