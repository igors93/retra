"""Pickle serializer for trusted local persistence."""

from __future__ import annotations

import pickle
from typing import Any

from ..exceptions import SerializationError


class PickleSerializer:
    """Serialize arbitrary Python objects with Pickle.

    Pickle payloads must only be loaded from storage trusted by the application. Pickle is not a
    safe format for data that an untrusted user can modify.
    """

    __slots__ = ("protocol",)
    name = "pickle"

    def __init__(self, protocol: int = pickle.HIGHEST_PROTOCOL) -> None:
        self.protocol = protocol

    def dumps(self, value: Any) -> bytes:
        try:
            return pickle.dumps(value, protocol=self.protocol)
        except Exception as exc:
            raise SerializationError(f"could not pickle value: {exc}") from exc

    def loads(self, payload: bytes) -> Any:
        try:
            return pickle.loads(payload)
        except Exception as exc:
            raise SerializationError(f"could not unpickle value: {exc}") from exc
