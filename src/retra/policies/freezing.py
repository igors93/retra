"""Value preservation policies.

Freezing happens on cache writes so repeated reads can return the same immutable object without
paying for a defensive copy on every hit.
"""

from __future__ import annotations

import copy
from collections.abc import Iterator, Mapping
from dataclasses import fields, is_dataclass
from enum import StrEnum
from typing import Any, TypeVar

from ..exceptions import ConfigurationError

K = TypeVar("K")
V = TypeVar("V")


class ValueMode(StrEnum):
    REFERENCE = "reference"
    FROZEN = "frozen"
    COPY = "copy"


class FrozenDict(Mapping[K, V]):
    """A compact immutable mapping with deterministic iteration order."""

    __slots__ = ("_hash", "_items", "_lookup")

    def __init__(self, items: Iterator[tuple[K, V]] | list[tuple[K, V]]) -> None:
        materialized = tuple(items)
        self._items = materialized
        self._lookup = dict(materialized)
        self._hash: int | None = None

    def __getitem__(self, key: K) -> V:
        return self._lookup[key]

    def __iter__(self) -> Iterator[K]:
        return (key for key, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __hash__(self) -> int:
        cached = self._hash
        if cached is None:
            cached = hash(frozenset(self._items))
            self._hash = cached
        return cached

    def __repr__(self) -> str:
        return f"FrozenDict({dict(self._items)!r})"


def freeze(value: Any, *, _seen: set[int] | None = None) -> Any:
    """Recursively convert common mutable containers to immutable equivalents."""

    if value is None or isinstance(value, (bool, int, float, complex, str, bytes, frozenset)):
        return value
    if isinstance(value, tuple):
        seen = _seen if _seen is not None else set()
        return tuple(freeze(item, _seen=seen) for item in value)

    seen = _seen if _seen is not None else set()
    object_id = id(value)
    if object_id in seen:
        raise ValueError("cyclic values cannot be frozen")
    seen.add(object_id)
    try:
        if isinstance(value, Mapping):
            return FrozenDict(
                [(freeze(key, _seen=seen), freeze(item, _seen=seen)) for key, item in value.items()]
            )
        if isinstance(value, list):
            return tuple(freeze(item, _seen=seen) for item in value)
        if isinstance(value, set):
            return frozenset(freeze(item, _seen=seen) for item in value)
        if isinstance(value, bytearray):
            return bytes(value)
        if is_dataclass(value) and not isinstance(value, type):
            # Reconstructing arbitrary dataclasses as immutable classes would alter their type.
            # A FrozenDict preserves the data while making the cached result safe to share.
            return FrozenDict(
                [
                    (field.name, freeze(getattr(value, field.name), _seen=seen))
                    for field in fields(value)
                ]
            )
        return value
    finally:
        seen.remove(object_id)


def prepare_value(value: Any, mode: ValueMode) -> Any:
    if mode is ValueMode.REFERENCE:
        return value
    if mode is ValueMode.FROZEN:
        return freeze(value)
    if mode is ValueMode.COPY:
        return copy.deepcopy(value)
    raise ConfigurationError(f"unsupported value mode: {mode!r}")


def return_value(value: Any, mode: ValueMode) -> Any:
    """Apply the read-side value policy."""

    if mode is ValueMode.COPY:
        return copy.deepcopy(value)
    return value
