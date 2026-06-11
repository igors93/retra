"""Retra public API."""

from .cache import Cache
from .config import CacheConfig
from .decorators import cached
from .entry import CacheEntry
from .exceptions import (
    BackendError,
    ConfigurationError,
    CorruptedEntryError,
    KeyGenerationError,
    RetraError,
    SerializationError,
)
from .stats import CacheStatsSnapshot

__version__ = "0.1.0"

__all__ = [
    "BackendError",
    "Cache",
    "CacheConfig",
    "CacheEntry",
    "CacheStatsSnapshot",
    "ConfigurationError",
    "CorruptedEntryError",
    "KeyGenerationError",
    "RetraError",
    "SerializationError",
    "cached",
]
