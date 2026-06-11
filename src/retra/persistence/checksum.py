"""Checksums for persistent entries."""

from __future__ import annotations

import hashlib


def checksum(data: bytes) -> bytes:
    """Return a compact corruption-detection digest."""

    return hashlib.blake2b(data, digest_size=16).digest()
