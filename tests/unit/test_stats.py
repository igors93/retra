from retra.config import StatsMode
from retra.observability import Counters, StatsSnapshot


def test_stats_snapshot_and_hit_rate() -> None:
    counters = Counters(StatsMode.EXACT)
    counters.increment("hits", 3)
    counters.increment("misses")

    snapshot = counters.snapshot()

    assert snapshot.requests == 4
    assert snapshot.hit_rate == 0.75
    assert snapshot.as_dict()["hits"] == 3


def test_stats_can_be_reset() -> None:
    counters = Counters(StatsMode.EXACT)
    counters.increment("writes", 2)

    counters.reset()

    assert counters.snapshot().writes == 0


def test_stats_snapshot_is_frozen_dataclass() -> None:
    snapshot = StatsSnapshot(hits=5, misses=2)
    assert snapshot.requests == 7
    assert abs(snapshot.hit_rate - 5 / 7) < 1e-9
