"""JSON serializer for interoperable values."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from ..exceptions import SerializationError
from ..policies.freezing import FrozenDict


def _json_value(value: Any) -> Any:
    if isinstance(value, FrozenDict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, frozenset):
        return [_json_value(item) for item in sorted(value, key=repr)]
    return value


class JsonSerializer:
    __slots__ = ("ensure_ascii",)
    name = "json"

    def __init__(self, *, ensure_ascii: bool = False) -> None:
        self.ensure_ascii = ensure_ascii

    def dumps(self, value: Any) -> bytes:
        try:
            return json.dumps(
                _json_value(value),
                ensure_ascii=self.ensure_ascii,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise SerializationError(f"could not encode JSON value: {exc}") from exc

    def loads(self, payload: bytes) -> Any:
        try:
            return json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SerializationError(f"could not decode JSON value: {exc}") from exc
