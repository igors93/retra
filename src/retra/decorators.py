"""Public typing contracts for decorated functions."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ParamSpec, Protocol, TypeVar

if TYPE_CHECKING:
    from .cache import Cache

P = ParamSpec("P")
R = TypeVar("R")


class CachedCallable(Protocol[P, R]):
    """A callable enriched with cache administration methods."""

    __wrapped__: Callable[P, R]
    cache_instance: Cache

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R: ...

    def cache_key(self, *args: P.args, **kwargs: P.kwargs) -> object: ...

    def peek(self, *args: P.args, **kwargs: P.kwargs) -> R | Any: ...

    def contains(self, *args: P.args, **kwargs: P.kwargs) -> bool: ...

    def invalidate(self, *args: P.args, **kwargs: P.kwargs) -> bool: ...

    def refresh(self, *args: P.args, **kwargs: P.kwargs) -> R: ...

    def bypass(self, *args: P.args, **kwargs: P.kwargs) -> R: ...

    def clear(self) -> None: ...
