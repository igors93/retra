"""Deterministic binary encoding used for complex and persistent keys."""

from __future__ import annotations

import dataclasses
import struct
from collections.abc import Mapping, Set
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID

from ..exceptions import KeyGenerationError

_U32 = struct.Struct(">I")
_I64 = struct.Struct(">q")
_F64 = struct.Struct(">d")


def canonical_bytes(value: Any) -> bytes:
    """Encode a supported value without relying on Python's randomized hash."""

    return _encode(value, seen=set())


def _length_prefixed(tag: bytes, payload: bytes) -> bytes:
    return tag + _U32.pack(len(payload)) + payload


def _qualified_name(value_type: type[Any]) -> bytes:
    return f"{value_type.__module__}.{value_type.__qualname__}".encode()


def _encode(value: Any, *, seen: set[int]) -> bytes:
    value_type = type(value)
    if value is None:
        return b"N"
    if value_type is bool:
        return b"B1" if value else b"B0"
    if value_type is int:
        return _length_prefixed(b"I", str(value).encode("ascii"))
    if value_type is float:
        return b"F" + _F64.pack(value)
    if value_type is complex:
        return b"X" + _F64.pack(value.real) + _F64.pack(value.imag)
    if value_type is str:
        return _length_prefixed(b"S", value.encode("utf-8"))
    if value_type is bytes:
        return _length_prefixed(b"Y", value)
    if value_type is bytearray:
        return _length_prefixed(b"A", bytes(value))
    if value_type is Decimal:
        return _length_prefixed(b"M", str(value).encode("ascii"))
    if value_type is UUID:
        return b"U" + bytes(value.bytes)
    if isinstance(value, Path):
        return _length_prefixed(b"P", str(value).encode("utf-8"))
    if isinstance(value, type):
        return _length_prefixed(b"C", _qualified_name(value))
    if isinstance(value, datetime):
        return _length_prefixed(b"Z", value.isoformat().encode("utf-8"))
    if isinstance(value, date):
        return _length_prefixed(b"D", value.isoformat().encode("ascii"))
    if isinstance(value, time):
        return _length_prefixed(b"R", value.isoformat().encode("ascii"))
    if isinstance(value, Enum):
        enum_payload = _qualified_name(type(value)) + _encode(value.value, seen=seen)
        return _length_prefixed(b"E", enum_payload)

    object_id = id(value)
    if object_id in seen:
        raise KeyGenerationError("cyclic key values are not supported")
    seen.add(object_id)
    try:
        custom_key = getattr(value, "__cache_key__", None)
        if callable(custom_key):
            custom_payload = _qualified_name(type(value)) + _encode(custom_key(), seen=seen)
            return _length_prefixed(b"K", custom_payload)

        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            dataclass_payload = bytearray(_qualified_name(type(value)))
            dataclass_payload.extend(_U32.pack(len(dataclasses.fields(value))))
            for field in dataclasses.fields(value):
                dataclass_payload.extend(_length_prefixed(b"n", field.name.encode("utf-8")))
                dataclass_payload.extend(_encode(getattr(value, field.name), seen=seen))
            return _length_prefixed(b"G", bytes(dataclass_payload))

        if isinstance(value, tuple):
            tuple_payload = b"".join(
                _length_prefixed(b"i", _encode(item, seen=seen)) for item in value
            )
            return b"T" + _U32.pack(len(value)) + tuple_payload

        if isinstance(value, list):
            list_payload = b"".join(
                _length_prefixed(b"i", _encode(item, seen=seen)) for item in value
            )
            return b"L" + _U32.pack(len(value)) + list_payload

        if isinstance(value, Mapping):
            items = [
                (_encode(key, seen=seen), _encode(item, seen=seen)) for key, item in value.items()
            ]
            items.sort(key=lambda pair: pair[0])
            mapping_payload = b"".join(
                _length_prefixed(b"k", key) + _length_prefixed(b"v", item) for key, item in items
            )
            return b"Q" + _U32.pack(len(items)) + mapping_payload

        if isinstance(value, Set):
            set_items = sorted(_encode(item, seen=seen) for item in value)
            set_payload = b"".join(_length_prefixed(b"i", item) for item in set_items)
            tag = b"H" if isinstance(value, frozenset) else b"O"
            return tag + _U32.pack(len(set_items)) + set_payload
    finally:
        seen.remove(object_id)

    raise KeyGenerationError(
        "unsupported key type; provide __cache_key__ or a custom key function: "
        f"{type(value).__module__}.{type(value).__qualname__}"
    )
