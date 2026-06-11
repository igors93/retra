"""Structural contracts implemented by Retra components."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol, runtime_checkable

from .entry import CacheEntry


@runtime_checkable
class Backend(Protocol):
    """Storage contract implemented by every backend."""

    def get(self, key: str) -> CacheEntry | None:
        """Return an entry or ``None`` when the key does not exist."""

    def set(self, entry: CacheEntry) -> None:
        """Insert or replace one entry."""

    def delete(self, key: str) -> bool:
        """Delete one key and report whether it existed."""

    def clear(self) -> None:
        """Remove all entries owned by this backend."""

    def close(self) -> None:
        """Release backend resources."""


@runtime_checkable
class Serializer(Protocol):
    """Convert Python objects to bytes and back."""

    def dumps(self, value: Any) -> bytes:
        """Serialize one value."""

    def loads(self, payload: bytes) -> Any:
        """Deserialize one value."""


@runtime_checkable
class KeyBuilder(Protocol):
    """Build deterministic keys for function calls."""

    def build(
        self,
        function: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: Mapping[str, Any],
        *,
        version: str | None = None,
    ) -> str:
        """Return a stable key for a function invocation."""


@runtime_checkable
class Clock(Protocol):
    """Clock abstraction used to make expiration logic testable."""

    def now(self) -> float:
        """Return the current wall-clock timestamp."""
