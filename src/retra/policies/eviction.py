"""Eviction choices for bounded memory stores."""

from __future__ import annotations

from enum import StrEnum


class EvictionPolicy(StrEnum):
    """Policies supported by the pure-Python memory engines."""

    FIFO = "fifo"
    LRU = "lru"
