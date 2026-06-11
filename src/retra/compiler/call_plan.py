"""Function call plans compiled once at decoration time."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, get_type_hints

from ..keys.exact import FunctionToken, exact_component, native_component
from ..keys.plans import CustomKeyPlan, KeyPlan, choose_key_plan
from .signatures import RenderedSignature, render_signature


@dataclass(frozen=True, slots=True)
class CompiledCallPlan:
    function: Callable[..., Any]
    signature: inspect.Signature
    rendered: RenderedSignature
    token: FunctionToken
    key_plan: KeyPlan
    key_parameter_names: tuple[str, ...]
    ignored_parameters: frozenset[str]
    custom_key: Callable[..., object] | None
    resolved_types: dict[str, type[Any]]

    def build_generic(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> object:
        """Build a key for helper methods outside the compiled hit path."""

        if isinstance(self.key_plan, CustomKeyPlan):
            return self.key_plan.build_call(args, kwargs)
        bound = self.signature.bind(*args, **kwargs)
        bound.apply_defaults()
        values = [
            bound.arguments[name] for name in self.key_parameter_names if name in bound.arguments
        ]
        return self.key_plan.build_values(values)

    def key_expression(self) -> str:
        if isinstance(self.key_plan, CustomKeyPlan):
            return f"(_token, _component(_custom({self.rendered.call_arguments})))"
        names = [name for name in self.key_parameter_names if name not in self.ignored_parameters]
        if not names:
            return "_constant_key"
        components = ", ".join(self._component_expression(name) for name in names)
        return f"(_token, {components})"

    def _component_expression(self, name: str) -> str:
        if not self.key_plan.typed:
            return f"_component({name})"
        expected = self.resolved_types.get(name)
        if expected is None:
            return f"_component({name})"
        primitive_names: dict[type[Any], str] = {
            int: "_int_type",
            bool: "_bool_type",
            str: "_str_type",
            bytes: "_bytes_type",
        }
        namespace_name = primitive_names.get(expected)
        if namespace_name is not None:
            return (
                f"(({namespace_name}, {name}) if type({name}) is {namespace_name} "
                f"else _component({name}))"
            )
        if expected is float:
            return (
                f"((_float_type, _float_pack({name})) if type({name}) is _float_type "
                f"else _component({name}))"
            )
        return f"_component({name})"


def compile_call_plan(
    function: Callable[..., Any],
    *,
    version: str | None,
    typed: bool,
    ignore_parameters: Sequence[str],
    custom_key: Callable[..., object] | None,
) -> CompiledCallPlan:
    signature = inspect.signature(function)
    ignored = frozenset(ignore_parameters)
    unknown = ignored.difference(signature.parameters)
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"ignored parameters are not present in the function signature: {names}")
    token = FunctionToken(
        identity=f"{function.__module__}.{function.__qualname__}",
        version=version or "1",
    )
    key_names = tuple(name for name in signature.parameters if name not in ignored)
    plan = choose_key_plan(
        token,
        len(key_names),
        typed=typed,
        custom=custom_key,
    )
    try:
        hints = get_type_hints(function)
    except Exception:
        hints = {}
    resolved_types = {
        name: hint
        for name, hint in hints.items()
        if name in signature.parameters and isinstance(hint, type)
    }
    return CompiledCallPlan(
        function=function,
        signature=signature,
        rendered=render_signature(signature),
        token=token,
        key_plan=plan,
        key_parameter_names=key_names,
        ignored_parameters=ignored,
        custom_key=custom_key,
        resolved_types=resolved_types,
    )


def component_function(typed: bool) -> Callable[[Any], object]:
    return exact_component if typed else native_component
