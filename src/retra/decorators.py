"""Function decorators backed by :class:`retra.Cache`."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar, cast

from .cache import Cache
from .exceptions import KeyGenerationError
from .internal.sentinel import MISSING

P = ParamSpec("P")
R = TypeVar("R")


def cached(
    cache: Cache,
    *,
    ttl: float | None | object = MISSING,
    key: Callable[P, str] | None = None,
    version: str | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Cache calls to a synchronous function.

    ``key`` may be supplied when function arguments require domain-specific key
    construction. It must return a non-empty string.
    """

    def decorator(function: Callable[P, R]) -> Callable[P, R]:
        if inspect.iscoroutinefunction(function):
            raise TypeError("async functions are not supported by cached() yet")

        def build_key(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
            if key is not None:
                generated = key(*args, **kwargs)
                if not isinstance(generated, str) or not generated:
                    raise KeyGenerationError("custom key function must return a non-empty string")
                identity = f"{function.__module__}.{function.__qualname__}"
                version_part = version or "1"
                return f"function:{identity}:{version_part}:custom:{generated}"

            return cache.key_builder.build(function, args, kwargs, version=version)

        @wraps(function)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            generated_key = build_key(cast(tuple[Any, ...], args), cast(dict[str, Any], kwargs))
            return cache.get_or_set(
                generated_key,
                lambda: function(*args, **kwargs),
                ttl=ttl,
            )

        def cache_key(*args: P.args, **kwargs: P.kwargs) -> str:
            """Return the unqualified Retra key for one function call."""

            return build_key(cast(tuple[Any, ...], args), cast(dict[str, Any], kwargs))

        def cache_invalidate(*args: P.args, **kwargs: P.kwargs) -> bool:
            """Delete the cached result for one function call."""

            return cache.delete(cache_key(*args, **kwargs))

        wrapper.cache_key = cache_key
        wrapper.cache_invalidate = cache_invalidate
        wrapper.cache_clear = cache.clear
        wrapper.cache_instance = cache
        return wrapper

    return decorator
