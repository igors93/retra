"""Error behavior for cache infrastructure failures."""

from __future__ import annotations

from enum import StrEnum


class ErrorMode(StrEnum):
    """Choose whether infrastructure errors are raised or converted to misses."""

    RAISE = "raise"
    CONTINUE = "continue"
