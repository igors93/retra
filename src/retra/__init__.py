"""Retra public API."""

from .async_cache import AsyncCache
from .cache import Cache
from .config import CacheConfig, ConcurrencyMode, StatsMode
from .constants import DO_NOT_CACHE, NEVER_EXPIRE
from .decorators import CachedCallable
from .exceptions import (
    CacheClosedError,
    ConfigurationError,
    CorruptedEntryError,
    GenerationRaceError,
    KeyGenerationError,
    RetraError,
    SerializationError,
    StoreError,
)
from .generation import Generation
from .internal.sentinel import MISSING
from .observability import CacheEvent, EventBuffer, EventKind, StatsSnapshot
from .policies.errors import ErrorMode
from .policies.eviction import EvictionPolicy
from .policies.freezing import FrozenDict, ValueMode
from .serializers import JsonSerializer, PickleSerializer
from .stores import FileStore, MemoryStore, SQLiteStore, TieredStore

__version__ = "0.1.0"

__all__ = [
    "DO_NOT_CACHE",
    "MISSING",
    "NEVER_EXPIRE",
    "AsyncCache",
    "Cache",
    "CacheClosedError",
    "CacheConfig",
    "CacheEvent",
    "CachedCallable",
    "ConcurrencyMode",
    "ConfigurationError",
    "CorruptedEntryError",
    "ErrorMode",
    "EventBuffer",
    "EventKind",
    "EvictionPolicy",
    "FileStore",
    "FrozenDict",
    "Generation",
    "GenerationRaceError",
    "JsonSerializer",
    "KeyGenerationError",
    "MemoryStore",
    "PickleSerializer",
    "RetraError",
    "SQLiteStore",
    "SerializationError",
    "StatsMode",
    "StatsSnapshot",
    "StoreError",
    "TieredStore",
    "ValueMode",
]
