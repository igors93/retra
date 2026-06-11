"""Generated wrappers for the Retra hit path."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from ..records import CacheRecord
from .call_plan import CompiledCallPlan


class InlineSlot:
    """One-entry inline cache owned by a decorated function."""

    __slots__ = ("key", "record")

    def __init__(self) -> None:
        self.key: object | None = None
        self.record: CacheRecord[Any] | None = None

    def clear(self) -> None:
        self.key = None
        self.record = None


def compile_sync_wrapper(
    plan: CompiledCallPlan,
    *,
    namespace: dict[str, Any],
    validity_expression: str,
    hit_statement: str,
    return_expression: str,
    inline_enabled: bool,
) -> Callable[..., Any]:
    """Compile an exact-signature wrapper when possible."""

    rendered = plan.rendered
    if not rendered.compilable:
        return _generic_sync_wrapper(plan, namespace)

    key_expression = plan.key_expression()
    inline_source = ""
    inline_update = ""
    if inline_enabled:
        inline_source = f"""
    _record = _slot.record
    if _slot.key == _key and _record is not None and ({validity_expression}):
        {hit_statement}
        return {return_expression}
"""
        inline_update = "\n        _slot.key = _key\n        _slot.record = _record"

    source = f"""
def wrapper({rendered.parameters}):
    _key = {key_expression}
{inline_source.rstrip()}
    _record = _get_record(_key)
    if _record is not None and ({validity_expression}):{inline_update}
        {hit_statement}
        return {return_expression}
    return _miss(_key, lambda: _function({rendered.call_arguments}))
"""
    execution_namespace = dict(namespace)
    execution_namespace.update(rendered.namespace)
    exec(compile(source, f"<retra:{plan.token.identity}>", "exec"), execution_namespace)
    wrapper = cast(Callable[..., Any], execution_namespace["wrapper"])
    cast(Any, wrapper).__source__ = source
    return wrapper


def _generic_sync_wrapper(
    plan: CompiledCallPlan,
    namespace: dict[str, Any],
) -> Callable[..., Any]:
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        key = plan.build_generic(args, kwargs)
        record = namespace["_get_record"](key)
        if record is not None and namespace["_is_valid"](record):
            namespace["_on_hit"]()
            return namespace["_read_value"](record.value)
        return namespace["_miss"](key, lambda: plan.function(*args, **kwargs))

    return wrapper


def compile_async_wrapper(
    plan: CompiledCallPlan,
    *,
    namespace: dict[str, Any],
    validity_expression: str,
    hit_statement: str,
    return_expression: str,
    inline_enabled: bool,
) -> Callable[..., Any]:
    """Compile an exact-signature async wrapper when possible."""

    rendered = plan.rendered
    if not rendered.compilable:
        return _generic_async_wrapper(plan, namespace)

    key_expression = plan.key_expression()
    inline_source = ""
    inline_update = ""
    if inline_enabled:
        inline_source = f"""
    _record = _slot.record
    if _slot.key == _key and _record is not None and ({validity_expression}):
        {hit_statement}
        return {return_expression}
"""
        inline_update = "\n        _slot.key = _key\n        _slot.record = _record"

    source = f"""
async def wrapper({rendered.parameters}):
    _key = {key_expression}
{inline_source.rstrip()}
    _record = _get_record(_key)
    if _record is not None and ({validity_expression}):{inline_update}
        {hit_statement}
        return {return_expression}
    return await _miss(_key, lambda: _function({rendered.call_arguments}))
"""
    execution_namespace = dict(namespace)
    execution_namespace.update(rendered.namespace)
    exec(compile(source, f"<retra-async:{plan.token.identity}>", "exec"), execution_namespace)
    wrapper = cast(Callable[..., Any], execution_namespace["wrapper"])
    cast(Any, wrapper).__source__ = source
    return wrapper


async def _await_factory(factory: Callable[[], Any]) -> Any:
    return await factory()


def _generic_async_wrapper(
    plan: CompiledCallPlan,
    namespace: dict[str, Any],
) -> Callable[..., Any]:
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        key = plan.build_generic(args, kwargs)
        record = namespace["_get_record"](key)
        if record is not None and namespace["_is_valid"](record):
            namespace["_on_hit"]()
            return namespace["_read_value"](record.value)
        return await namespace["_miss"](key, lambda: plan.function(*args, **kwargs))

    return wrapper
