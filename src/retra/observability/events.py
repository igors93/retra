"""Optional bounded event recording kept separate from callbacks."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from threading import Lock


class EventKind(StrEnum):
    HIT = "hit"
    MISS = "miss"
    WRITE = "write"
    DELETE = "delete"
    EXPIRE = "expire"
    EVICT = "evict"
    ERROR = "error"
    PROMOTE = "promote"


@dataclass(frozen=True, slots=True)
class CacheEvent:
    kind: EventKind
    key: object
    detail: str | None = None


class EventBuffer:
    """A bounded diagnostic buffer.

    Event recording is disabled unless a buffer is explicitly attached. No user callback is ever
    executed from the cache hit path.
    """

    __slots__ = ("_events", "_lock")

    def __init__(self, capacity: int = 1_024) -> None:
        if capacity <= 0:
            raise ValueError("event buffer capacity must be greater than zero")
        self._events: deque[CacheEvent] = deque(maxlen=capacity)
        self._lock = Lock()

    def append(self, event: CacheEvent) -> None:
        with self._lock:
            self._events.append(event)

    def drain(self) -> list[CacheEvent]:
        with self._lock:
            events = list(self._events)
            self._events.clear()
            return events

    def __len__(self) -> int:
        with self._lock:
            return len(self._events)
