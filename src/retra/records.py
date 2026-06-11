"""Compact records shared by stores and compiled wrappers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class CacheRecord(Generic[T]):
    """One cached value and the metadata required to prove validity."""

    value: T
    created_ns: int
    deadline_ns: int
    namespace_generation: int
    function_generation: int
    dependency_versions: tuple[int, ...] = ()

    def is_expired(self, now_ns: int) -> bool:
        return self.deadline_ns != 0 and now_ns >= self.deadline_ns

    def matches_generations(
        self,
        namespace_generation: int,
        function_generation: int,
        dependency_versions: tuple[int, ...],
    ) -> bool:
        return (
            self.namespace_generation == namespace_generation
            and self.function_generation == function_generation
            and self.dependency_versions == dependency_versions
        )
