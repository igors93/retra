"""Configuration objects used by the cache coordinator."""

from __future__ import annotations

from dataclasses import dataclass

from .exceptions import ConfigurationError


@dataclass(frozen=True, slots=True)
class CacheConfig:
    """Immutable settings shared by one :class:`retra.Cache` instance."""

    default_ttl: float | None = None
    namespace: str = "retra"
    fail_open: bool = True
    cache_none: bool = True

    def __post_init__(self) -> None:
        if self.default_ttl is not None and self.default_ttl < 0:
            raise ConfigurationError("default_ttl must be non-negative or None")
        if not self.namespace or not self.namespace.strip():
            raise ConfigurationError("namespace must be a non-empty string")
        if ":" in self.namespace:
            raise ConfigurationError("namespace must not contain ':'")
