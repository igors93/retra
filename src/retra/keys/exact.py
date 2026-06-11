"""Exact in-memory key components."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from .canonical import canonical_bytes

_F64 = struct.Struct(">d")


@dataclass(frozen=True, slots=True)
class FunctionToken:
    """Stable identity for a decorated function."""

    identity: str
    version: str


@dataclass(frozen=True, slots=True)
class ManualToken:
    """Identity for manually managed cache keys."""

    namespace: str


def exact_component(value: Any) -> object:
    """Return a hashable component that preserves exact Python type identity."""

    value_type = type(value)
    if value is None:
        return (type(None), None)
    if value_type in (bool, int, str, bytes):
        return (value_type, value)
    if value_type is float:
        return (float, _F64.pack(value))
    if value_type is complex:
        return (complex, _F64.pack(value.real), _F64.pack(value.imag))
    if value_type is Decimal:
        return (Decimal, value.as_tuple())
    if value_type is UUID:
        return (UUID, value.int)
    if value_type is Path:
        return (Path, str(value))
    if value_type is tuple:
        return (tuple, tuple(exact_component(item) for item in value))
    if value_type is frozenset:
        return (frozenset, frozenset(exact_component(item) for item in value))

    # Complex or mutable values are snapshotted into a canonical byte representation. This is
    # slower than primitive keys, but it prevents a key from changing after insertion.
    return (value_type, canonical_bytes(value))


def native_component(value: Any) -> object:
    """Use Python's native equality where possible, with a canonical fallback."""

    try:
        hash(value)
    except TypeError:
        return canonical_bytes(value)
    return value
