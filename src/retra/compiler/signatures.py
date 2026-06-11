"""Safe rendering of Python function signatures for compiled wrappers."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RenderedSignature:
    parameters: str
    call_arguments: str
    value_names: tuple[str, ...]
    namespace: dict[str, Any]
    compilable: bool


def render_signature(signature: inspect.Signature) -> RenderedSignature:
    """Render a signature without embedding user representations in generated source."""

    namespace: dict[str, Any] = {}
    parts: list[str] = []
    positional_only_count = 0
    saw_varargs = False
    inserted_keyword_marker = False
    call_parts: list[str] = []
    value_names: list[str] = []

    try:
        parameters = list(signature.parameters.values())
        for index, parameter in enumerate(parameters):
            name = parameter.name
            if not name.isidentifier():
                return RenderedSignature("*args, **kwargs", "*args, **kwargs", (), {}, False)
            value_names.append(name)
            default = ""
            if parameter.default is not inspect.Parameter.empty:
                default_name = f"_default_{index}"
                namespace[default_name] = parameter.default
                default = f"={default_name}"

            if parameter.kind is inspect.Parameter.POSITIONAL_ONLY:
                parts.append(f"{name}{default}")
                positional_only_count += 1
                call_parts.append(name)
            elif parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD:
                if positional_only_count and len(parts) == positional_only_count:
                    parts.append("/")
                parts.append(f"{name}{default}")
                call_parts.append(name)
            elif parameter.kind is inspect.Parameter.VAR_POSITIONAL:
                if positional_only_count and "/" not in parts:
                    parts.append("/")
                parts.append(f"*{name}")
                saw_varargs = True
                inserted_keyword_marker = True
                call_parts.append(f"*{name}")
            elif parameter.kind is inspect.Parameter.KEYWORD_ONLY:
                if positional_only_count and "/" not in parts:
                    parts.append("/")
                if not saw_varargs and not inserted_keyword_marker:
                    parts.append("*")
                    inserted_keyword_marker = True
                parts.append(f"{name}{default}")
                call_parts.append(f"{name}={name}")
            elif parameter.kind is inspect.Parameter.VAR_KEYWORD:
                if positional_only_count and "/" not in parts:
                    parts.append("/")
                parts.append(f"**{name}")
                call_parts.append(f"**{name}")

        if positional_only_count and "/" not in parts:
            parts.append("/")
        return RenderedSignature(
            parameters=", ".join(parts),
            call_arguments=", ".join(call_parts),
            value_names=tuple(value_names),
            namespace=namespace,
            compilable=True,
        )
    except Exception:
        return RenderedSignature("*args, **kwargs", "*args, **kwargs", (), {}, False)
