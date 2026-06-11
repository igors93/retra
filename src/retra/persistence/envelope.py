"""Versioned binary envelope used by the file store."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from ..exceptions import CorruptedEntryError
from ..records import CacheRecord
from .checksum import checksum

_MAGIC = b"RTRP"
_VERSION = 1
_HEADER = struct.Struct(">4sBBHqqqqIII16s")
_DEPENDENCY = struct.Struct(">q")


@dataclass(frozen=True, slots=True)
class DecodedEnvelope:
    canonical_key: bytes
    payload: bytes
    record_metadata: CacheRecord[None]


def encode_envelope(canonical_key: bytes, payload: bytes, record: CacheRecord[object]) -> bytes:
    dependencies = b"".join(_DEPENDENCY.pack(value) for value in record.dependency_versions)
    body = canonical_key + dependencies + payload
    digest = checksum(
        struct.pack(
            ">qqqqI",
            record.created_ns,
            record.deadline_ns,
            record.namespace_generation,
            record.function_generation,
            len(record.dependency_versions),
        )
        + body
    )
    header = _HEADER.pack(
        _MAGIC,
        _VERSION,
        0,
        0,
        record.created_ns,
        record.deadline_ns,
        record.namespace_generation,
        record.function_generation,
        len(record.dependency_versions),
        len(canonical_key),
        len(payload),
        digest,
    )
    return header + body


def decode_envelope(data: bytes) -> DecodedEnvelope:
    if len(data) < _HEADER.size:
        raise CorruptedEntryError("cache file is shorter than its header")
    (
        magic,
        version,
        _flags,
        _reserved,
        created_ns,
        deadline_ns,
        namespace_generation,
        function_generation,
        dependency_count,
        key_length,
        payload_length,
        stored_checksum,
    ) = _HEADER.unpack_from(data)
    if magic != _MAGIC:
        raise CorruptedEntryError("invalid cache file magic")
    if version != _VERSION:
        raise CorruptedEntryError(f"unsupported cache file version: {version}")
    dependency_bytes = dependency_count * _DEPENDENCY.size
    expected_length = _HEADER.size + key_length + dependency_bytes + payload_length
    if len(data) != expected_length:
        raise CorruptedEntryError("cache file length does not match its header")

    offset = _HEADER.size
    canonical_key = data[offset : offset + key_length]
    offset += key_length
    dependencies = tuple(
        _DEPENDENCY.unpack_from(data, offset + index * _DEPENDENCY.size)[0]
        for index in range(dependency_count)
    )
    offset += dependency_bytes
    payload = data[offset : offset + payload_length]
    body = canonical_key + data[_HEADER.size + key_length :]
    actual_checksum = checksum(
        struct.pack(
            ">qqqqI",
            created_ns,
            deadline_ns,
            namespace_generation,
            function_generation,
            dependency_count,
        )
        + body
    )
    if actual_checksum != stored_checksum:
        raise CorruptedEntryError("cache file checksum mismatch")
    metadata = CacheRecord(
        value=None,
        created_ns=created_ns,
        deadline_ns=deadline_ns,
        namespace_generation=namespace_generation,
        function_generation=function_generation,
        dependency_versions=dependencies,
    )
    return DecodedEnvelope(canonical_key, payload, metadata)
