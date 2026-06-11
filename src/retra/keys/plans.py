"""Key plans selected once for manual and decorated cache operations."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from ..exceptions import KeyGenerationError
from .exact import FunctionToken, exact_component, native_component


class KeyPlan:
    """Base class for function key plans."""

    __slots__ = ("token", "typed")

    def __init__(self, token: FunctionToken, *, typed: bool) -> None:
        self.token = token
        self.typed = typed

    def component(self, value: Any) -> object:
        return exact_component(value) if self.typed else native_component(value)

    def build_values(self, values: Sequence[Any]) -> object:
        raise NotImplementedError


class ConstantKeyPlan(KeyPlan):
    __slots__ = ("_key",)

    def __init__(self, token: FunctionToken, *, typed: bool) -> None:
        super().__init__(token, typed=typed)
        self._key = (token,)

    def build_values(self, values: Sequence[Any]) -> object:
        return self._key


class ScalarKeyPlan(KeyPlan):
    __slots__ = ()

    def build_values(self, values: Sequence[Any]) -> object:
        return (self.token, self.component(values[0]))


class TupleKeyPlan(KeyPlan):
    __slots__ = ()

    def build_values(self, values: Sequence[Any]) -> object:
        return (self.token, *(self.component(value) for value in values))


class CustomKeyPlan(KeyPlan):
    __slots__ = ("_custom",)

    def __init__(
        self,
        token: FunctionToken,
        custom: Callable[..., object],
        *,
        typed: bool,
    ) -> None:
        super().__init__(token, typed=typed)
        self._custom = custom

    def build_call(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> object:
        generated = self._custom(*args, **kwargs)
        if generated is None:
            raise KeyGenerationError("custom key functions must not return None")
        return (self.token, self.component(generated))

    def build_values(self, values: Sequence[Any]) -> object:
        raise KeyGenerationError("custom key plans require the original call shape")


def choose_key_plan(
    token: FunctionToken,
    parameter_count: int,
    *,
    typed: bool,
    custom: Callable[..., object] | None = None,
) -> KeyPlan:
    if custom is not None:
        return CustomKeyPlan(token, custom, typed=typed)
    if parameter_count == 0:
        return ConstantKeyPlan(token, typed=typed)
    if parameter_count == 1:
        return ScalarKeyPlan(token, typed=typed)
    return TupleKeyPlan(token, typed=typed)
