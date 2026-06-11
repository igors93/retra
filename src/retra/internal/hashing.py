"""Hash helpers for deterministic shard selection and persistence."""

from __future__ import annotations

import hashlib

_MASK_64 = (1 << 64) - 1


def stable_hash64(data: bytes) -> int:
    """Return a deterministic unsigned 64-bit digest for persisted keys."""

    return int.from_bytes(hashlib.blake2b(data, digest_size=8).digest(), "big")


def shard_index(key: object, mask: int) -> int:
    """Map a Python key to a power-of-two shard count."""

    return hash(key) & mask


def mix_hash(value: int) -> int:
    """Mix Python's process-local hash before selecting a striped lock."""

    value &= _MASK_64
    value ^= value >> 30
    value = (value * 0xBF58476D1CE4E5B9) & _MASK_64
    value ^= value >> 27
    value = (value * 0x94D049BB133111EB) & _MASK_64
    value ^= value >> 31
    return value
