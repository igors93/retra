"""Data model shared by every cache backend."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CacheEntry:
    """Serialized cache value and its expiration metadata."""

    key: str
    payload: bytes
    created_at: float
    expires_at: float | None = None

    def is_expired(self, now: float) -> bool:
        """Return whether the entry has reached its expiration time."""

        return self.expires_at is not None and now >= self.expires_at
