"""Validated cache configuration selected outside the hot path."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .exceptions import ConfigurationError
from .policies.errors import ErrorMode
from .policies.eviction import EvictionPolicy
from .policies.freezing import ValueMode


class ConcurrencyMode(StrEnum):
    SINGLE = "single"
    READ_HEAVY = "read_heavy"
    BALANCED = "balanced"


class StatsMode(StrEnum):
    OFF = "off"
    BASIC = "basic"
    SAMPLED = "sampled"
    EXACT = "exact"


@dataclass(frozen=True, slots=True)
class CacheConfig:
    """Settings shared by one cache instance."""

    namespace: str = "retra"
    concurrency: ConcurrencyMode = ConcurrencyMode.BALANCED
    max_items: int = 100_000
    shards: int = 64
    miss_locks: int = 256
    eviction: EvictionPolicy = EvictionPolicy.FIFO
    value_mode: ValueMode = ValueMode.FROZEN
    stats: StatsMode = StatsMode.BASIC
    stats_sample_rate: float = 0.01
    error_mode: ErrorMode = ErrorMode.RAISE
    typed_keys: bool = True
    inline_cache: bool = True
    generation_retries: int = 2

    def __post_init__(self) -> None:
        if not self.namespace or not self.namespace.strip():
            raise ConfigurationError("namespace must be a non-empty string")
        if self.max_items <= 0:
            raise ConfigurationError("max_items must be greater than zero")
        _validate_power_of_two("shards", self.shards)
        _validate_power_of_two("miss_locks", self.miss_locks)
        if self.generation_retries < 0:
            raise ConfigurationError("generation_retries must be non-negative")
        if not 0 < self.stats_sample_rate <= 1:
            raise ConfigurationError("stats_sample_rate must be in the interval (0, 1]")


def _validate_power_of_two(name: str, value: int) -> None:
    if value <= 0 or value & (value - 1):
        raise ConfigurationError(f"{name} must be a positive power of two")
