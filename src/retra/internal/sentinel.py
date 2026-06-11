"""Internal sentinel values."""

from __future__ import annotations


class _Missing:
    __slots__ = ()

    def __repr__(self) -> str:
        return "MISSING"


MISSING = _Missing()
