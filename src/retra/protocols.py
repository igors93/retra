"""Structural contracts for Retra components."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol, TypeVar, runtime_checkable

from .internal.clock import Clock
from .records import CacheRecord

T = TypeVar("T")


@runtime_checkable
class Store(Protocol):
    """Object-level storage contract used by the cache coordinator."""

    persistent: bool

    @property
    def clock(self) -> Clock:
        """Return the clock used for entry deadlines."""

    def get_record(self, key: object) -> CacheRecord[Any] | None:
        """Return a record without applying function-generation validation."""

    def get_metadata(self, key: object) -> CacheRecord[None] | None:
        """Return entry metadata without deserializing the stored value when possible."""

    def set_record(self, key: object, record: CacheRecord[Any]) -> int:
        """Insert or replace a record and return the number of evictions."""

    def delete(self, key: object) -> bool:
        """Delete one key and report whether it existed."""

    def clear(self) -> None:
        """Remove all physical records."""

    def contains_key(self, key: object) -> bool:
        """Check physical key presence without loading a value when possible."""

    def get_many(self, keys: Iterable[object]) -> dict[object, CacheRecord[Any]]:
        """Return the records found for the supplied keys."""

    def set_many(self, records: Mapping[object, CacheRecord[Any]]) -> int:
        """Insert records and return the number of evictions."""

    def delete_many(self, keys: Iterable[object]) -> int:
        """Delete keys and return the number removed."""

    def prune(self) -> int:
        """Remove expired or excess records and return the number removed."""

    def close(self) -> None:
        """Release resources."""


@runtime_checkable
class Serializer(Protocol):
    """Convert Python objects to bytes and restore them."""

    name: str

    def dumps(self, value: Any) -> bytes:
        """Serialize a Python object."""

    def loads(self, payload: bytes) -> Any:
        """Deserialize a Python object."""
