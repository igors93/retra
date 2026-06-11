"""High-level cache coordinator."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, TypeVar, cast

from .config import CacheConfig
from .entry import CacheEntry
from .exceptions import BackendError, RetraError, SerializationError
from .internal.clock import SystemClock
from .internal.locks import KeyLockRegistry
from .internal.sentinel import MISSING
from .keys import FunctionKeyBuilder
from .protocols import Backend, Clock, KeyBuilder, Serializer
from .serializers import PickleSerializer
from .stats import CacheStats, CacheStatsSnapshot

T = TypeVar("T")
logger = logging.getLogger(__name__)


class Cache:
    """Coordinate key namespacing, serialization, expiration, and storage."""

    def __init__(
        self,
        backend: Backend,
        *,
        serializer: Serializer | None = None,
        config: CacheConfig | None = None,
        key_builder: KeyBuilder | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._backend = backend
        self._serializer = serializer or PickleSerializer()
        self._config = config or CacheConfig()
        self._key_builder = key_builder or FunctionKeyBuilder()
        self._clock = clock or SystemClock()
        self._stats = CacheStats()
        self._locks = KeyLockRegistry()
        self._closed = False

    @property
    def backend(self) -> Backend:
        return self._backend

    @property
    def serializer(self) -> Serializer:
        return self._serializer

    @property
    def config(self) -> CacheConfig:
        return self._config

    @property
    def key_builder(self) -> KeyBuilder:
        return self._key_builder

    def get(self, key: str, default: T | None = None) -> Any | T | None:
        """Return a cached value or ``default`` when the key is unavailable."""

        self._ensure_open()
        found, value = self._lookup_storage(self._storage_key(key), record_stats=True)
        return value if found else default

    def contains(self, key: str) -> bool:
        """Return whether a valid value exists for ``key``."""

        self._ensure_open()
        found, _ = self._lookup_storage(self._storage_key(key), record_stats=False)
        return found

    def set(self, key: str, value: Any, *, ttl: float | None | object = MISSING) -> bool:
        """Store a value and return whether it was written.

        A TTL of zero intentionally skips storage. Negative TTL values are rejected.
        """

        self._ensure_open()
        return self._set_storage(key, value, ttl=ttl)

    def get_or_set(
        self,
        key: str,
        factory: Callable[[], T],
        *,
        ttl: float | None | object = MISSING,
    ) -> T:
        """Return an existing value or compute and store a new one.

        The factory executes under a per-key lock. This prevents duplicate work among
        threads using the same :class:`Cache` instance.
        """

        self._ensure_open()
        storage_key = self._storage_key(key)

        found, value = self._lookup_storage(storage_key, record_stats=False)
        if found:
            self._stats.increment("hits")
            return cast(T, value)

        with self._locks.acquire(storage_key):
            # Another thread may have populated the cache while this thread waited.
            found, value = self._lookup_storage(storage_key, record_stats=False)
            if found:
                self._stats.increment("hits")
                return cast(T, value)

            self._stats.increment("misses")
            computed = factory()
            self._set_storage(storage_key, computed, ttl=ttl, already_qualified=True)
            return computed

    def delete(self, key: str) -> bool:
        """Delete one key and return whether it existed."""

        self._ensure_open()
        return self._delete_storage(self._storage_key(key), record_stats=True)

    def clear(self) -> None:
        """Remove every entry owned by the backend."""

        self._ensure_open()
        try:
            self._backend.clear()
        except Exception as exc:
            self._handle_error("could not clear cache", exc, BackendError)

    def stats(self) -> CacheStatsSnapshot:
        """Return an immutable snapshot of cache counters."""

        return self._stats.snapshot()

    def reset_stats(self) -> None:
        """Reset cache counters."""

        self._stats.reset()

    def cached(
        self,
        *,
        ttl: float | None | object = MISSING,
        key: Callable[..., str] | None = None,
        version: str | None = None,
    ) -> Callable[[Callable[..., T]], Callable[..., T]]:
        """Return a decorator bound to this cache instance."""

        from .decorators import cached

        return cached(self, ttl=ttl, key=key, version=version)

    def close(self) -> None:
        """Release backend resources. Calling this method more than once is safe."""

        if self._closed:
            return
        try:
            self._backend.close()
        except Exception as exc:
            self._handle_error("could not close cache backend", exc, BackendError)
        finally:
            self._closed = True

    def __enter__(self) -> Cache:
        self._ensure_open()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def _storage_key(self, key: str) -> str:
        if not isinstance(key, str) or not key:
            raise ValueError("cache key must be a non-empty string")
        return f"{self._config.namespace}:{key}"

    def _lookup_storage(self, storage_key: str, *, record_stats: bool) -> tuple[bool, Any]:
        try:
            entry = self._backend.get(storage_key)
        except Exception as exc:
            self._handle_error(f"could not read cache key {storage_key!r}", exc, BackendError)
            if record_stats:
                self._stats.increment("misses")
            return False, None

        if entry is None:
            if record_stats:
                self._stats.increment("misses")
            return False, None

        if entry.is_expired(self._clock.now()):
            self._stats.increment("expirations")
            self._delete_storage(storage_key, record_stats=False)
            if record_stats:
                self._stats.increment("misses")
            return False, None

        try:
            value = self._serializer.loads(entry.payload)
        except Exception as exc:
            self._handle_error(
                f"could not deserialize cache key {storage_key!r}",
                exc,
                SerializationError,
            )
            # Invalid payloads are removed so future reads can recover naturally.
            self._delete_storage(storage_key, record_stats=False)
            if record_stats:
                self._stats.increment("misses")
            return False, None

        if record_stats:
            self._stats.increment("hits")
        return True, value

    def _set_storage(
        self,
        key: str,
        value: Any,
        *,
        ttl: float | None | object,
        already_qualified: bool = False,
    ) -> bool:
        if value is None and not self._config.cache_none:
            return False

        resolved_ttl = self._resolve_ttl(ttl)
        if resolved_ttl == 0:
            return False

        storage_key = key if already_qualified else self._storage_key(key)
        now = self._clock.now()
        expires_at = None if resolved_ttl is None else now + resolved_ttl

        try:
            payload = self._serializer.dumps(value)
        except Exception as exc:
            self._handle_error(
                f"could not serialize cache key {storage_key!r}",
                exc,
                SerializationError,
            )
            return False

        entry = CacheEntry(
            key=storage_key,
            payload=payload,
            created_at=now,
            expires_at=expires_at,
        )

        try:
            self._backend.set(entry)
        except Exception as exc:
            self._handle_error(f"could not write cache key {storage_key!r}", exc, BackendError)
            return False

        self._stats.increment("writes")
        return True

    def _delete_storage(self, storage_key: str, *, record_stats: bool) -> bool:
        try:
            deleted = self._backend.delete(storage_key)
        except Exception as exc:
            self._handle_error(f"could not delete cache key {storage_key!r}", exc, BackendError)
            return False

        if deleted and record_stats:
            self._stats.increment("deletions")
        return deleted

    def _resolve_ttl(self, ttl: float | None | object) -> float | None:
        resolved = self._config.default_ttl if ttl is MISSING else ttl
        if resolved is None:
            return None
        if not isinstance(resolved, (int, float)) or isinstance(resolved, bool):
            raise TypeError("ttl must be a number, None, or omitted")
        if resolved < 0:
            raise ValueError("ttl must be non-negative")
        return float(resolved)

    def _handle_error(
        self,
        message: str,
        error: Exception,
        error_type: type[RetraError],
    ) -> None:
        self._stats.increment("errors")
        if not self._config.fail_open:
            if isinstance(error, RetraError):
                raise error
            raise error_type(f"{message}: {error}") from error
        logger.warning("%s: %s", message, error, exc_info=True)

    def _ensure_open(self) -> None:
        if self._closed:
            raise BackendError("cache is closed")
