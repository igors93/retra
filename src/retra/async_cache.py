"""Async Retra cache with compiled coroutine wrappers."""

from __future__ import annotations

import functools
import inspect
import struct
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, ParamSpec, TypeVar, cast

from .cache import Cache, _dependency_expression
from .compiler import InlineSlot, compile_async_wrapper, compile_call_plan, component_function
from .concurrency import AsyncMissGate
from .config import StatsMode
from .generation import Generation
from .internal.sentinel import MISSING
from .policies.expiration import TTL
from .policies.freezing import ValueMode, prepare_value, return_value
from .records import CacheRecord

P = ParamSpec("P")
R = TypeVar("R")
_FLOAT_PACK = struct.Struct(">d").pack


class AsyncCache(Cache):
    """Cache for asynchronous functions.

    Store operations remain synchronous because memory stores are the intended low-latency use
    case. Applications using persistent stores from an event loop should isolate disk operations
    in their own executor or use a memory-fronted tier explicitly.
    """

    __slots__ = ("_async_gate",)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._async_gate = AsyncMissGate(self._config.miss_locks, self._counters)

    def cached(  # type: ignore[override]
        self,
        *,
        ttl: TTL | object = MISSING,
        key: Callable[..., object] | None = None,
        version: str | None = None,
        ignore_parameters: Sequence[str] = (),
        dependencies: Sequence[Generation] = (),
        cache_if: Callable[[Any], bool] | None = None,
    ) -> Callable[[Callable[P, Awaitable[R]]], Any]:
        """Create a compiled async cache decorator."""

        def decorator(function: Callable[P, Awaitable[R]]) -> Any:
            if not inspect.iscoroutinefunction(function):
                raise TypeError("AsyncCache.cached() requires an async function")
            plan = compile_call_plan(
                function,
                version=version,
                typed=self._config.typed_keys,
                ignore_parameters=ignore_parameters,
                custom_key=key,
                persistent_store=self._store.persistent,
            )
            function_generation = Generation(f"function:{plan.token.identity}:{plan.token.version}")
            dependency_tuple = tuple(dependencies)
            slot = InlineSlot()
            cacheable, ttl_ns = self._resolve_ttl(ttl)

            def current_dependencies() -> tuple[int, ...]:
                return tuple(dependency.value for dependency in dependency_tuple)

            def is_valid(record: CacheRecord[Any]) -> bool:
                return (
                    record.namespace_generation == self._namespace_generation.value
                    and record.function_generation == function_generation.value
                    and record.dependency_versions == current_dependencies()
                    and (record.deadline_ns == 0 or self._store.clock.now_ns() < record.deadline_ns)
                )

            async def compute_and_store(
                call_key: object,
                factory: Callable[[], Awaitable[R]],
                *,
                allow_existing: bool,
            ) -> R:
                async with self._async_gate.acquire(call_key):
                    if allow_existing:
                        existing = self._get_record(call_key)
                        if existing is not None and is_valid(existing):
                            self._counters.increment("hits")
                            if self._config.inline_cache:
                                slot.key = call_key
                                slot.record = existing
                                slot.store_version = _store_version_fn()
                            return cast(R, return_value(existing.value, self._config.value_mode))

                    if allow_existing:
                        self._counters.increment("misses")
                    for _attempt in range(self._config.generation_retries + 1):
                        before_namespace = self._namespace_generation.value
                        before_function = function_generation.value
                        before_dependencies = current_dependencies()
                        computed = await factory()
                        if (
                            before_namespace == self._namespace_generation.value
                            and before_function == function_generation.value
                            and before_dependencies == current_dependencies()
                        ):
                            break
                    else:
                        from .exceptions import GenerationRaceError

                        raise GenerationRaceError(
                            "cache dependencies changed repeatedly while computing "
                            f"{plan.token.identity}"
                        )

                    if not cacheable or (cache_if is not None and not cache_if(computed)):
                        return computed
                    prepared = prepare_value(computed, self._config.value_mode)
                    now_ns = self._store.clock.now_ns()
                    record = CacheRecord(
                        value=prepared,
                        created_ns=now_ns,
                        deadline_ns=now_ns + ttl_ns if ttl_ns else 0,
                        namespace_generation=before_namespace,
                        function_generation=before_function,
                        dependency_versions=before_dependencies,
                    )
                    written = self._write_record(call_key, record)
                    if written and self._config.inline_cache:
                        slot.key = call_key
                        slot.record = record
                        slot.store_version = _store_version_fn()
                    return cast(R, return_value(prepared, self._config.value_mode))

            async def miss_handler(
                call_key: object,
                factory: Callable[[], Awaitable[R]],
            ) -> R:
                self._ensure_open()
                return await compute_and_store(call_key, factory, allow_existing=True)

            _store_version_fn: Callable[[], int]
            if hasattr(self._store, "version") and callable(self._store.version):  # type: ignore[union-attr]
                _store_version_fn = self._store.version  # type: ignore[union-attr]
            else:
                _store_version_fn = lambda: 0  # noqa: E731

            dependency_expression = _dependency_expression(len(dependency_tuple))
            validity_parts = [
                "_record.namespace_generation == _namespace.value",
                "_record.function_generation == _function_generation.value",
                f"_record.dependency_versions == {dependency_expression}",
            ]
            if ttl_ns:
                validity_parts.append("_record.deadline_ns > _now_ns()")
            hit_statement = "_hit()" if self._config.stats is not StatsMode.OFF else "pass"
            return_expression = (
                "_copy_value(_record.value)"
                if self._config.value_mode is ValueMode.COPY
                else "_record.value"
            )
            namespace: dict[str, Any] = {
                "_component": component_function(self._config.typed_keys),
                "_bool_type": bool,
                "_bytes_type": bytes,
                "_float_pack": _FLOAT_PACK,
                "_float_type": float,
                "_int_type": int,
                "_str_type": str,
                "_constant_key": (plan.token,),
                "_copy_value": lambda value: return_value(value, ValueMode.COPY),
                "_custom": key,
                "_function": function,
                "_function_generation": function_generation,
                "_get_record": self._get_record,
                "_hit": lambda: self._counters.increment("hits"),
                "_is_valid": is_valid,
                "_miss": miss_handler,
                "_namespace": self._namespace_generation,
                "_now_ns": self._store.clock.now_ns,
                "_on_hit": lambda: self._counters.increment("hits"),
                "_read_value": lambda value: return_value(value, self._config.value_mode),
                "_slot": slot,
                "_store_version": _store_version_fn,
                "_token": plan.token,
            }
            for index, dependency in enumerate(dependency_tuple):
                namespace[f"_dep{index}"] = dependency

            wrapper = compile_async_wrapper(
                plan,
                namespace=namespace,
                validity_expression=" and ".join(validity_parts),
                hit_statement=hit_statement,
                return_expression=return_expression,
                inline_enabled=self._config.inline_cache,
            )
            functools.update_wrapper(wrapper, function)
            wrapper_any = cast(Any, wrapper)
            wrapper_any.__signature__ = plan.signature

            def cache_key(*args: P.args, **kwargs: P.kwargs) -> object:
                return plan.build_generic(cast(tuple[Any, ...], args), cast(dict[str, Any], kwargs))

            def peek(*args: P.args, **kwargs: P.kwargs) -> Any:
                call_key = cache_key(*args, **kwargs)
                record = self._get_record(call_key)
                if record is None or not is_valid(record):
                    return MISSING
                return return_value(record.value, self._config.value_mode)

            def contains(*args: P.args, **kwargs: P.kwargs) -> bool:
                call_key = cache_key(*args, **kwargs)
                metadata = self._get_metadata(call_key)
                return metadata is not None and is_valid(metadata)

            def invalidate(*args: P.args, **kwargs: P.kwargs) -> bool:
                call_key = cache_key(*args, **kwargs)
                if slot.key == call_key:
                    slot.clear()
                return self._delete_record(call_key)

            async def refresh(*args: P.args, **kwargs: P.kwargs) -> R:
                call_key = cache_key(*args, **kwargs)
                return await compute_and_store(
                    call_key,
                    lambda: function(*args, **kwargs),
                    allow_existing=False,
                )

            async def bypass(*args: P.args, **kwargs: P.kwargs) -> R:
                return await function(*args, **kwargs)

            def clear_function() -> None:
                function_generation.advance()
                slot.clear()

            wrapper_any.cache_key = cache_key
            wrapper_any.peek = peek
            wrapper_any.contains = contains
            wrapper_any.invalidate = invalidate
            wrapper_any.refresh = refresh
            wrapper_any.bypass = bypass
            wrapper_any.clear = clear_function
            wrapper_any.cache_instance = self
            wrapper_any.call_plan = plan
            wrapper_any.function_generation = function_generation
            return wrapper

        return decorator
