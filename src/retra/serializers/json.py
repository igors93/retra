"""JSON serializer implementation."""

from __future__ import annotations

import json
from typing import Any

from ..exceptions import SerializationError


class JsonSerializer:
    """Serialize JSON-compatible values as UTF-8 bytes."""

    def __init__(self, *, ensure_ascii: bool = False) -> None:
        self._ensure_ascii = ensure_ascii

    def dumps(self, value: Any) -> bytes:
        try:
            return json.dumps(
                value,
                ensure_ascii=self._ensure_ascii,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise SerializationError(f"could not serialize value as JSON: {exc}") from exc

    def loads(self, payload: bytes) -> Any:
        try:
            return json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SerializationError(f"could not deserialize JSON payload: {exc}") from exc
