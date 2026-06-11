"""Deterministic key generation for cached function calls."""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import inspect
import json
import math
from collections.abc import Callable, Mapping, Sequence, Set
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID

from .exceptions import KeyGenerationError


class FunctionKeyBuilder:
    """Build stable keys from function identity and normalized arguments.

    Parameters listed in ``ignore_parameters`` are omitted from the key. Ignoring
    ``self`` or ``cls`` can be useful, but is only safe when the result does not
    depend on instance or class state.
    """

    def __init__(self, *, ignore_parameters: Sequence[str] = ()) -> None:
        self._ignore_parameters = frozenset(ignore_parameters)

    def build(
        self,
        function: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: Mapping[str, Any],
        *,
        version: str | None = None,
    ) -> str:
        try:
            signature = inspect.signature(function)
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()

            arguments = {
                name: value
                for name, value in bound.arguments.items()
                if name not in self._ignore_parameters
            }
            normalized = _normalize(arguments, seen=set())
            encoded = json.dumps(
                normalized,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        except KeyGenerationError:
            raise
        except Exception as exc:
            raise KeyGenerationError(
                f"could not generate a key for {function.__qualname__}: {exc}"
            ) from exc

        digest = hashlib.sha256(encoded).hexdigest()
        identity = f"{function.__module__}.{function.__qualname__}"
        version_part = version or "1"
        return f"function:{identity}:{version_part}:{digest}"


def _normalize(value: Any, *, seen: set[int]) -> Any:
    """Convert supported values into a deterministic JSON-compatible structure."""

    if value is None or isinstance(value, (bool, int, str)):
        return value

    if isinstance(value, float):
        if math.isnan(value):
            return {"__type__": "float", "value": "nan"}
        if math.isinf(value):
            return {"__type__": "float", "value": "inf" if value > 0 else "-inf"}
        return {"__type__": "float", "value": value.hex()}

    if isinstance(value, bytes):
        return {
            "__type__": "bytes",
            "value": base64.b64encode(value).decode("ascii"),
        }

    if isinstance(value, bytearray):
        return {
            "__type__": "bytearray",
            "value": base64.b64encode(bytes(value)).decode("ascii"),
        }

    if isinstance(value, (datetime, date, time)):
        return {
            "__type__": type(value).__name__,
            "value": value.isoformat(),
        }

    if isinstance(value, (Decimal, UUID, Path)):
        return {
            "__type__": f"{type(value).__module__}.{type(value).__qualname__}",
            "value": str(value),
        }

    if isinstance(value, Enum):
        return {
            "__type__": f"{type(value).__module__}.{type(value).__qualname__}",
            "value": _normalize(value.value, seen=seen),
        }

    object_id = id(value)
    if object_id in seen:
        raise KeyGenerationError("cyclic arguments are not supported")

    seen.add(object_id)
    try:
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            fields = {
                field.name: _normalize(getattr(value, field.name), seen=seen)
                for field in dataclasses.fields(value)
            }
            return {
                "__type__": f"{type(value).__module__}.{type(value).__qualname__}",
                "fields": fields,
            }

        custom_key = getattr(value, "__cache_key__", None)
        if callable(custom_key):
            return {
                "__type__": f"{type(value).__module__}.{type(value).__qualname__}",
                "cache_key": _normalize(custom_key(), seen=seen),
            }

        if isinstance(value, Mapping):
            items = [
                (
                    _normalize(key, seen=seen),
                    _normalize(item_value, seen=seen),
                )
                for key, item_value in value.items()
            ]
            items.sort(key=lambda item: _canonical_json(item[0]))
            return {"__type__": "mapping", "items": items}

        if isinstance(value, tuple):
            return {
                "__type__": "tuple",
                "items": [_normalize(item, seen=seen) for item in value],
            }

        if isinstance(value, list):
            return {
                "__type__": "list",
                "items": [_normalize(item, seen=seen) for item in value],
            }

        if isinstance(value, Set):
            items = [_normalize(item, seen=seen) for item in value]
            items.sort(key=_canonical_json)
            return {
                "__type__": "frozenset" if isinstance(value, frozenset) else "set",
                "items": items,
            }

        if hasattr(value, "__dict__"):
            attributes = {
                name: _normalize(attribute, seen=seen)
                for name, attribute in vars(value).items()
                if not name.startswith("__")
            }
            return {
                "__type__": f"{type(value).__module__}.{type(value).__qualname__}",
                "attributes": attributes,
            }
    finally:
        seen.remove(object_id)

    raise KeyGenerationError(
        f"unsupported argument type: {type(value).__module__}.{type(value).__qualname__}"
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
