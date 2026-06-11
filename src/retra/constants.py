"""Explicit cache lifetime constants."""

from __future__ import annotations


class _LifetimeConstant:
    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return self.name


NEVER_EXPIRE = _LifetimeConstant("NEVER_EXPIRE")
DO_NOT_CACHE = _LifetimeConstant("DO_NOT_CACHE")
