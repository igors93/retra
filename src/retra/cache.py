"""Retra cache coordinator and compiled decorator factory."""

from __future__ import annotations

import functools
import inspect
import logging
import struct
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, ParamSpec, TypeVar, cast

from .compiler import InlineSlot, compile_call_plan, compile_sync_wrapper, component_function
from .concurrency import MissGate
from .config import CacheConfig, ConcurrencyMode, StatsMode
from .constants import DO_NOT_CACHE, NEVER_EXPIRE
from .exceptions import CacheClosedError, GenerationRaceError, RetraError, StoreError
from .generation import Generation
from .internal.sentinel import MISSING
from .keys import ManualToken, exact_component, native_component
from .observability import CacheEvent, Counters, EventBuffer, EventKind, StatsSnapshot
from .policies.errors import ErrorMode
from .policies.expiration import TTL, ttl_to_ns
from .policies.freezing import ValueMode, prepare_value, return_value
from .protocols import Serializer, Store
from .records import CacheRecord
from .stores import FileStore, MemoryStore, SQLiteStore, TieredStore

P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")

logger = logging.getLogger(__name__)
_FLOAT_PACK = struct.Struct(">d").pack


class Cache:
    """Coordinate exact keys, validity, miss suppression, and object storage."""

    __slots__ = (
        "_closed",
        "_component",
        "_config",
        "_counters",
        "_default_ttl",
        "_events",
        "_gate",
        "_generations",
        "_manual_token",
        "_namespace_generation",
        "_store",
    )

    def __init__(
        self,
        store: Store,
        *,
        config: CacheConfig | None = None,
        default_ttl: TTL | object = NEVER_EXPIRE,
        event_buffer: EventBuffer | None = None,
    ) -> None:
        self._config = config or CacheConfig()
        self._store = store
        self._default_ttl = default_ttl
        self._counters = Counters(self._config.stats, self._config.stats_sample_rate)
        self._events = event_buffer
        self._gate = MissGate(self._config.miss_locks, self._counters)
        ns_key = f"namespace:{self._config.namespace}"
        initial_ns = self._load_generation(ns_key)
        self._namespace_generation = Generation(ns_key, initial=initial_ns)
        self._generations: dict[str, Generation] = {}
        self._manual_token = ManualToken(self._config.namespace)
        self._component = component_function(self._config.typed_keys)
        self._closed = False

    # Store factories are exposed separately so tiered storage remains explicit.
    @staticmethod
    def memory_store(
        *,
        max_items: int = 100_000,
        concurrency: ConcurrencyMode | str = ConcurrencyMode.BALANCED,
        shards: int = 64,
        eviction: str = "fifo",
    ) -> MemoryStore:
        from .policies.eviction import EvictionPolicy

        effective = _effective_shards(max_items, shards)
        return MemoryStore(
            max_items=max_items,
            concurrency=ConcurrencyMode(concurrency),
            shards=effective,
            eviction=EvictionPolicy(eviction),
        )

    @staticmethod
    def sqlite_store(
        path: str | Path,
        *,
        serializer: Serializer | None = None,
        max_items: int | None = None,
        timeout: float = 5.0,
    ) -> SQLiteStore:
        return SQLiteStore(
            path,
            serializer=serializer,
            max_items=max_items,
            timeout=timeout,
        )

    @staticmethod
    def file_store(
        directory: str | Path,
        *,
        serializer: Serializer | None = None,
        max_items: int | None = None,
    ) -> FileStore:
        return FileStore(directory, serializer=serializer, max_items=max_items)

    @classmethod
    def memory(
        cls,
        *,
        profile: str | None = None,
        max_items: int = 100_000,
        concurrency: ConcurrencyMode | str = ConcurrencyMode.BALANCED,
        shards: int = 64,
        miss_locks: int = 256,
        eviction: str = "fifo",
        value_mode: ValueMode | str = ValueMode.FROZEN,
        stats: StatsMode | str = StatsMode.BASIC,
        typed_keys: bool = True,
        inline_cache: bool = True,
        namespace: str = "retra",
        default_ttl: TTL | object = NEVER_EXPIRE,
        error_mode: ErrorMode | str = ErrorMode.RAISE,
        generation_retries: int = 2,
    ) -> Cache:
        from .policies.eviction import EvictionPolicy

        if profile is not None:
            normalized_profile = profile.lower()
            if normalized_profile == "speed":
                concurrency = ConcurrencyMode.SINGLE
                value_mode = ValueMode.REFERENCE
                stats = StatsMode.OFF
                eviction = "fifo"
                error_mode = ErrorMode.RAISE
                typed_keys = True
                inline_cache = True
            elif normalized_profile == "precise":
                concurrency = ConcurrencyMode.BALANCED
                value_mode = ValueMode.FROZEN
                stats = StatsMode.EXACT
                eviction = "fifo"
                error_mode = ErrorMode.RAISE
                typed_keys = True
                inline_cache = True
            elif normalized_profile == "balanced":
                concurrency = ConcurrencyMode.BALANCED
                value_mode = ValueMode.FROZEN
                stats = StatsMode.BASIC
                eviction = "fifo"
                error_mode = ErrorMode.RAISE
                typed_keys = True
                inline_cache = True
            else:
                raise ValueError("profile must be 'speed', 'precise', or 'balanced'")

        effective = _effective_shards(max_items, shards)
        config = CacheConfig(
            namespace=namespace,
            concurrency=ConcurrencyMode(concurrency),
            max_items=max_items,
            shards=effective,
            miss_locks=miss_locks,
            eviction=EvictionPolicy(eviction),
            value_mode=ValueMode(value_mode),
            stats=StatsMode(stats),
            error_mode=ErrorMode(error_mode),
            typed_keys=typed_keys,
            inline_cache=inline_cache,
            generation_retries=generation_retries,
        )
        store = MemoryStore(
            max_items=max_items,
            concurrency=config.concurrency,
            shards=effective,
            eviction=config.eviction,
        )
        return cls(store, config=config, default_ttl=default_ttl)

    @classmethod
    def sqlite(
        cls,
        path: str | Path,
        *,
        serializer: Serializer | None = None,
        max_items: int | None = None,
        namespace: str = "retra",
        default_ttl: TTL | object = NEVER_EXPIRE,
        value_mode: ValueMode | str = ValueMode.FROZEN,
        stats: StatsMode | str = StatsMode.BASIC,
        typed_keys: bool = True,
        error_mode: ErrorMode | str = ErrorMode.RAISE,
    ) -> Cache:
        config = CacheConfig(
            namespace=namespace,
            value_mode=ValueMode(value_mode),
            stats=StatsMode(stats),
            typed_keys=typed_keys,
            error_mode=ErrorMode(error_mode),
        )
        return cls(
            SQLiteStore(path, serializer=serializer, max_items=max_items),
            config=config,
            default_ttl=default_ttl,
        )

    @classmethod
    def file(
        cls,
        directory: str | Path,
        *,
        serializer: Serializer | None = None,
        max_items: int | None = None,
        namespace: str = "retra",
        default_ttl: TTL | object = NEVER_EXPIRE,
        value_mode: ValueMode | str = ValueMode.FROZEN,
        stats: StatsMode | str = StatsMode.BASIC,
        typed_keys: bool = True,
        error_mode: ErrorMode | str = ErrorMode.RAISE,
    ) -> Cache:
        config = CacheConfig(
            namespace=namespace,
            value_mode=ValueMode(value_mode),
            stats=StatsMode(stats),
            typed_keys=typed_keys,
            error_mode=ErrorMode(error_mode),
        )
        return cls(
            FileStore(directory, serializer=serializer, max_items=max_items),
            config=config,
            default_ttl=default_ttl,
        )

    @classmethod
    def tiered(
        cls,
        *,
        front: MemoryStore,
        backing: Store,
        namespace: str = "retra",
        default_ttl: TTL | object = NEVER_EXPIRE,
        value_mode: ValueMode | str = ValueMode.FROZEN,
        stats: StatsMode | str = StatsMode.BASIC,
        typed_keys: bool = True,
        error_mode: ErrorMode | str = ErrorMode.RAISE,
    ) -> Cache:
        config = CacheConfig(
            namespace=namespace,
            value_mode=ValueMode(value_mode),
            stats=StatsMode(stats),
            typed_keys=typed_keys,
            error_mode=ErrorMode(error_mode),
        )
        return cls(
            TieredStore(front, backing),
            config=config,
            default_ttl=default_ttl,
        )

    @property
    def config(self) -> CacheConfig:
        return self._config

    @property
    def store(self) -> Store:
        return self._store

    def generation(self, name: str) -> Generation:
        """Return a named invalidation token, creating it once when necessary."""

        generation = self._generations.get(name)
        if generation is None:
            generation = Generation(name)
            self._generations[name] = generation
        return generation

    def get(self, key: object, default: T | object = MISSING) -> Any | T:
        self._ensure_open()
        storage_key = self._manual_key(key)
        record = self._get_record(storage_key)
        if record is not None and self._manual_record_valid(record):
            self._counters.increment("hits")
            self._event(EventKind.HIT, storage_key)
            return return_value(record.value, self._config.value_mode)
        self._counters.increment("misses")
        self._event(EventKind.MISS, storage_key)
        return default

    def peek(self, key: object) -> Any:
        """Return a valid value without changing hit/miss counters."""

        self._ensure_open()
        record = self._get_record(self._manual_key(key))
        if record is None or not self._manual_record_valid(record):
            return MISSING
        return return_value(record.value, self._config.value_mode)

    def contains(self, key: object) -> bool:
        self._ensure_open()
        metadata = self._get_metadata(self._manual_key(key))
        return metadata is not None and self._manual_record_valid(metadata)

    def set(
        self,
        key: object,
        value: Any,
        *,
        ttl: TTL | object = MISSING,
    ) -> bool:
        self._ensure_open()
        cacheable, ttl_ns = self._resolve_ttl(ttl)
        if not cacheable:
            return False
        now_ns = self._store.clock.now_ns()
        prepared = prepare_value(value, self._config.value_mode)
        record = CacheRecord(
            value=prepared,
            created_ns=now_ns,
            deadline_ns=now_ns + ttl_ns if ttl_ns else 0,
            namespace_generation=self._namespace_generation.value,
            function_generation=0,
        )
        return self._write_record(self._manual_key(key), record)

    def get_or_set(
        self,
        key: object,
        factory: Callable[[], T],
        *,
        ttl: TTL | object = MISSING,
    ) -> T:
        storage_key = self._manual_key(key)
        record = self._get_record(storage_key)
        if record is not None and self._manual_record_valid(record):
            self._counters.increment("hits")
            return cast(T, return_value(record.value, self._config.value_mode))
        with self._gate.acquire(storage_key):
            record = self._get_record(storage_key)
            if record is not None and self._manual_record_valid(record):
                self._counters.increment("hits")
                return cast(T, return_value(record.value, self._config.value_mode))
            self._counters.increment("misses")
            value = factory()
            self.set(key, value, ttl=ttl)
            cached = self.peek(key)
            return value if cached is MISSING else cast(T, cached)

    def delete(self, key: object) -> bool:
        self._ensure_open()
        deleted = self._delete_record(self._manual_key(key))
        if deleted:
            self._counters.increment("deletions")
        return deleted

    def get_many(self, keys: Iterable[object]) -> dict[object, Any]:
        result: dict[object, Any] = {}
        for key in keys:
            value = self.peek(key)
            if value is not MISSING:
                result[key] = value
        return result

    def set_many(
        self,
        values: Mapping[object, Any],
        *,
        ttl: TTL | object = MISSING,
    ) -> int:
        self._ensure_open()
        cacheable, ttl_ns = self._resolve_ttl(ttl)
        if not cacheable:
            return 0
        now_ns = self._store.clock.now_ns()
        records = {
            self._manual_key(key): CacheRecord(
                value=prepare_value(value, self._config.value_mode),
                created_ns=now_ns,
                deadline_ns=now_ns + ttl_ns if ttl_ns else 0,
                namespace_generation=self._namespace_generation.value,
                function_generation=0,
            )
            for key, value in values.items()
        }
        try:
            evicted = self._store.set_many(records)
        except Exception as exc:
            self._handle_store_error("could not write cache records", exc)
            return 0
        self._counters.increment("writes", len(records))
        if evicted:
            self._counters.increment("evictions", evicted)
        return len(records)

    def delete_many(self, keys: Iterable[object]) -> int:
        internal = tuple(self._manual_key(key) for key in keys)
        try:
            deleted = self._store.delete_many(internal)
        except Exception as exc:
            self._handle_store_error("could not delete cache records", exc)
            return 0
        self._counters.increment("deletions", deleted)
        return deleted

    def invalidate_all(self) -> int:
        """Logically invalidate all entries in O(1) without walking the store."""

        new_value = self._namespace_generation.advance()
        self._save_generation(self._namespace_generation.name, new_value)
        return new_value

    def clear(self) -> None:
        """Physically remove all records and advance the namespace generation."""

        self._ensure_open()
        new_value = self._namespace_generation.advance()
        self._save_generation(self._namespace_generation.name, new_value)
        try:
            self._store.clear()
        except Exception as exc:
            self._handle_store_error("could not clear cache store", exc)

    def prune(self) -> int:
        self._ensure_open()
        try:
            removed = self._store.prune()
        except Exception as exc:
            self._handle_store_error("could not prune cache store", exc)
            return 0
        if removed:
            self._counters.increment("expirations", removed)
        return removed

    def stats(self) -> StatsSnapshot:
        return self._counters.snapshot()

    def reset_stats(self) -> None:
        self._counters.reset()

    def cached(
        self,
        *,
        ttl: TTL | object = MISSING,
        key: Callable[..., object] | None = None,
        version: str | None = None,
        ignore_parameters: Sequence[str] = (),
        dependencies: Sequence[Generation] = (),
        cache_if: Callable[[Any], bool] | None = None,
    ) -> Callable[[Callable[P, R]], Any]:
        """Create a compiled synchronous cache decorator."""

        def decorator(function: Callable[P, R]) -> Any:
            if inspect.iscoroutinefunction(function):
                raise TypeError("async functions require AsyncCache.cached()")
            plan = compile_call_plan(
                function,
                version=version,
                typed=self._config.typed_keys,
                ignore_parameters=ignore_parameters,
                custom_key=key,
                persistent_store=self._store.persistent,
            )
            func_gen_name = f"function:{plan.token.identity}:{plan.token.version}"
            initial_func_gen = self._load_generation(func_gen_name)
            function_generation = Generation(func_gen_name, initial=initial_func_gen)
            dependency_tuple = tuple(dependencies)
            slot = InlineSlot()
            cacheable, ttl_ns = self._resolve_ttl(ttl)

            def current_dependencies() -> tuple[int, ...]:
                return tuple(dependency.value for dependency in dependency_tuple)

            def is_valid(record: CacheRecord[Any]) -> bool:
                if record.namespace_generation != self._namespace_generation.value:
                    return False
                if record.function_generation != function_generation.value:
                    return False
                if record.dependency_versions != current_dependencies():
                    return False
                return record.deadline_ns == 0 or self._store.clock.now_ns() < record.deadline_ns

            def compute_and_store(
                call_key: object,
                factory: Callable[[], R],
                *,
                allow_existing: bool,
            ) -> R:
                with self._gate.acquire(call_key):
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
                        computed = factory()
                        if (
                            before_namespace == self._namespace_generation.value
                            and before_function == function_generation.value
                            and before_dependencies == current_dependencies()
                        ):
                            break
                    else:
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

            def miss_handler(call_key: object, factory: Callable[[], R]) -> R:
                self._ensure_open()
                return compute_and_store(call_key, factory, allow_existing=True)

            # For memory stores the version counter tracks structural changes so the inline
            # slot is automatically invalidated after eviction, deletion, or clear.
            _store_version_fn: Callable[[], int]
            store_version_attr = getattr(self._store, "version", None)
            if callable(store_version_attr):
                _store_version_fn = store_version_attr
            else:
                _store_version_fn = lambda: 0  # noqa: E731

            # Also update the slot in the existing-record path inside compute_and_store.
            # The closure above already uses _store_version_fn, so the lambda below closes
            # over the same function object.

            component = component_function(self._config.typed_keys)
            dependency_expression = _dependency_expression(len(dependency_tuple))
            validity_parts = [
                "_record.namespace_generation == _namespace.value",
                "_record.function_generation == _function_generation.value",
                f"_record.dependency_versions == {dependency_expression}",
            ]
            if ttl_ns:
                validity_parts.append("_record.deadline_ns > _now_ns()")
            validity_expression = " and ".join(validity_parts)
            hit_statement = "_hit()" if self._config.stats is not StatsMode.OFF else "pass"
            return_expression = (
                "_copy_value(_record.value)"
                if self._config.value_mode is ValueMode.COPY
                else "_record.value"
            )
            namespace: dict[str, Any] = {
                "_component": component,
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

            wrapper = compile_sync_wrapper(
                plan,
                namespace=namespace,
                validity_expression=validity_expression,
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

            def refresh(*args: P.args, **kwargs: P.kwargs) -> R:
                call_key = cache_key(*args, **kwargs)
                return compute_and_store(
                    call_key,
                    lambda: function(*args, **kwargs),
                    allow_existing=False,
                )

            def bypass(*args: P.args, **kwargs: P.kwargs) -> R:
                return function(*args, **kwargs)

            def clear_function() -> None:
                new_val = function_generation.advance()
                self._save_generation(function_generation.name, new_val)
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

    def close(self) -> None:
        if self._closed:
            return
        try:
            self._store.close()
        finally:
            self._closed = True

    def __enter__(self) -> Cache:
        self._ensure_open()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def _manual_key(self, key: object) -> object:
        component = exact_component(key) if self._config.typed_keys else native_component(key)
        return (self._manual_token, component)

    def _manual_record_valid(self, record: CacheRecord[Any]) -> bool:
        if record.namespace_generation != self._namespace_generation.value:
            return False
        if record.function_generation != 0 or record.dependency_versions:
            return False
        if record.is_expired(self._store.clock.now_ns()):
            self._counters.increment("expirations")
            return False
        return True

    def _resolve_ttl(self, ttl: TTL | object) -> tuple[bool, int]:
        resolved = self._default_ttl if ttl is MISSING else ttl
        if resolved is DO_NOT_CACHE:
            return False, 0
        if resolved is NEVER_EXPIRE or resolved is None:
            return True, 0
        if isinstance(resolved, (int, float)) and not isinstance(resolved, bool) and resolved == 0:
            return False, 0
        return True, ttl_to_ns(cast(TTL, resolved))

    def _get_record(self, key: object) -> CacheRecord[Any] | None:
        try:
            return self._store.get_record(key)
        except Exception as exc:
            self._handle_store_error(f"could not read cache key {key!r}", exc)
            return None

    def _get_metadata(self, key: object) -> CacheRecord[None] | None:
        try:
            return self._store.get_metadata(key)
        except Exception as exc:
            self._handle_store_error(f"could not read cache metadata for {key!r}", exc)
            return None

    def _write_record(self, key: object, record: CacheRecord[Any]) -> bool:
        try:
            evicted = self._store.set_record(key, record)
        except Exception as exc:
            self._handle_store_error(f"could not write cache key {key!r}", exc)
            return False
        self._counters.increment("writes")
        if evicted:
            self._counters.increment("evictions", evicted)
        self._event(EventKind.WRITE, key)
        return True

    def _delete_record(self, key: object) -> bool:
        try:
            return self._store.delete(key)
        except Exception as exc:
            self._handle_store_error(f"could not delete cache key {key!r}", exc)
            return False

    def _handle_store_error(self, message: str, error: Exception) -> None:
        self._counters.increment("errors")
        self._event(EventKind.ERROR, "store", f"{message}: {error}")
        if self._config.error_mode is ErrorMode.RAISE:
            if isinstance(error, RetraError):
                raise error
            raise StoreError(f"{message}: {error}") from error
        logger.warning("%s: %s", message, error, exc_info=True)

    def _event(self, kind: EventKind, key: object, detail: str | None = None) -> None:
        if self._events is not None:
            self._events.append(CacheEvent(kind, key, detail))

    def _ensure_open(self) -> None:
        if self._closed:
            raise CacheClosedError("cache is closed")

    def _load_generation(self, name: str) -> int:
        """Return the persisted generation value from the store, if supported."""
        get_gen = getattr(self._store, "get_generation", None)
        if callable(get_gen):
            try:
                return int(get_gen(name))
            except Exception:
                pass
        return 0

    def _save_generation(self, name: str, value: int) -> None:
        """Persist a generation value to the store, if supported."""
        set_gen = getattr(self._store, "set_generation", None)
        if callable(set_gen):
            try:
                set_gen(name, value)
            except Exception as exc:
                logger.warning("could not persist generation %r: %s", name, exc)


def _effective_shards(max_items: int, requested_shards: int) -> int:
    """Return the largest power of two that is at most both max_items and requested_shards.

    When max_items < requested_shards, using all shards would give each shard a capacity of 1
    but produce a total capacity much greater than max_items. Clamping ensures the store
    actually respects the configured limit.
    """
    cap = min(max_items, requested_shards)
    if cap <= 0:
        return 1
    # Round down to the nearest power of two.
    result = 1
    while result * 2 <= cap:
        result *= 2
    return result


def _dependency_expression(count: int) -> str:
    if count == 0:
        return "()"
    names = ", ".join(f"_dep{index}.value" for index in range(count))
    if count == 1:
        names += ","
    return f"({names})"
