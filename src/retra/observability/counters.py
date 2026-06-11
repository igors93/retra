"""Low-overhead cache counters."""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from threading import Lock
from typing import Literal

from ..config import StatsMode

CounterName = Literal[
    "hits",
    "misses",
    "writes",
    "deletions",
    "expirations",
    "evictions",
    "errors",
    "lock_waits",
    "promotions",
]


@dataclass(frozen=True, slots=True)
class StatsSnapshot:
    hits: int = 0
    misses: int = 0
    writes: int = 0
    deletions: int = 0
    expirations: int = 0
    evictions: int = 0
    errors: int = 0
    lock_waits: int = 0
    promotions: int = 0

    @property
    def requests(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        return self.hits / self.requests if self.requests else 0.0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


class Counters:
    """Counters whose update strategy is selected once at construction time.

    ``basic`` counters are intentionally approximate under heavy multi-threaded mutation so they
    avoid a shared lock on every hit. ``exact`` uses a lock. ``sampled`` scales sampled events when
    a snapshot is requested and is intended for trend monitoring rather than accounting.
    """

    __slots__ = ("_data", "_increment", "_lock", "_mode", "_sample_rate")

    _NAMES = (
        "hits",
        "misses",
        "writes",
        "deletions",
        "expirations",
        "evictions",
        "errors",
        "lock_waits",
        "promotions",
    )

    def __init__(self, mode: StatsMode, sample_rate: float = 0.01) -> None:
        self._mode = mode
        self._sample_rate = sample_rate
        self._data = dict.fromkeys(self._NAMES, 0)
        self._lock = Lock()
        if mode is StatsMode.OFF:
            self._increment = self._increment_off
        elif mode is StatsMode.EXACT:
            self._increment = self._increment_exact
        elif mode is StatsMode.SAMPLED:
            self._increment = self._increment_sampled
        else:
            self._increment = self._increment_basic

    def increment(self, name: CounterName, amount: int = 1) -> None:
        self._increment(name, amount)

    def _increment_off(self, name: CounterName, amount: int) -> None:
        return None

    def _increment_basic(self, name: CounterName, amount: int) -> None:
        self._data[name] += amount

    def _increment_exact(self, name: CounterName, amount: int) -> None:
        with self._lock:
            self._data[name] += amount

    def _increment_sampled(self, name: CounterName, amount: int) -> None:
        if random.random() <= self._sample_rate:
            self._data[name] += amount

    def snapshot(self) -> StatsSnapshot:
        if self._mode is StatsMode.EXACT:
            with self._lock:
                data = dict(self._data)
        else:
            data = dict(self._data)
        if self._mode is StatsMode.SAMPLED:
            scale = 1 / self._sample_rate
            data = {name: round(value * scale) for name, value in data.items()}
        return StatsSnapshot(**data)

    def reset(self) -> None:
        if self._mode is StatsMode.EXACT:
            with self._lock:
                for name in self._NAMES:
                    self._data[name] = 0
            return
        for name in self._NAMES:
            self._data[name] = 0
