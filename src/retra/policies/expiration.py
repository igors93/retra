"""TTL parsing and deadline helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Final, TypeAlias

from ..exceptions import ConfigurationError

TTL: TypeAlias = int | float | str | timedelta | None

_DURATION_RE: Final = re.compile(
    r"^\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>ns|us|µs|ms|s|m|h|d)\s*$",
    re.IGNORECASE,
)
_UNIT_TO_NS: Final = {
    "ns": 1,
    "us": 1_000,
    "µs": 1_000,
    "ms": 1_000_000,
    "s": 1_000_000_000,
    "m": 60_000_000_000,
    "h": 3_600_000_000_000,
    "d": 86_400_000_000_000,
}


def ttl_to_ns(ttl: TTL) -> int:
    """Convert a public TTL value to nanoseconds.

    Zero means "do not expire" at the record level. Callers that want "do not cache" must make
    that choice before constructing a record.
    """

    if ttl is None:
        return 0
    if isinstance(ttl, bool):
        raise ConfigurationError("ttl must not be a boolean")
    if isinstance(ttl, timedelta):
        seconds = ttl.total_seconds()
        if seconds < 0:
            raise ConfigurationError("ttl must be non-negative")
        return int(seconds * 1_000_000_000)
    if isinstance(ttl, (int, float)):
        if ttl < 0:
            raise ConfigurationError("ttl must be non-negative")
        return int(float(ttl) * 1_000_000_000)
    if isinstance(ttl, str):
        match = _DURATION_RE.match(ttl)
        if match is None:
            raise ConfigurationError(f"invalid ttl string: {ttl!r}")
        value = float(match.group("value"))
        unit = match.group("unit").lower()
        return int(value * _UNIT_TO_NS[unit])
    raise ConfigurationError(f"unsupported ttl type: {type(ttl).__name__}")


@dataclass(frozen=True, slots=True)
class ExpirationPolicy:
    """Precompiled expiration policy used by one cache or decorated function."""

    ttl_ns: int
    cache_zero_ttl: bool = False

    @classmethod
    def from_ttl(cls, ttl: TTL) -> ExpirationPolicy:
        return cls(ttl_ns=ttl_to_ns(ttl))

    @property
    def enabled(self) -> bool:
        return self.ttl_ns > 0

    def deadline(self, now_ns: int) -> int:
        return now_ns + self.ttl_ns if self.ttl_ns else 0
