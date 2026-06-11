"""Pickle serializer implementation."""

from __future__ import annotations

import pickle
from typing import Any

from ..exceptions import SerializationError


class PickleSerializer:
    """Serialize Python values with Pickle.

    Pickle must only be used with trusted cache storage because loading malicious
    Pickle data can execute arbitrary code.
    """

    def __init__(self, *, protocol: int = pickle.HIGHEST_PROTOCOL) -> None:
        self._protocol = protocol

    def dumps(self, value: Any) -> bytes:
        try:
            return pickle.dumps(value, protocol=self._protocol)
        except (pickle.PickleError, TypeError, AttributeError) as exc:
            raise SerializationError(f"could not pickle value: {exc}") from exc

    def loads(self, payload: bytes) -> Any:
        try:
            return pickle.loads(payload)
        except (pickle.PickleError, EOFError, AttributeError, ImportError, IndexError) as exc:
            raise SerializationError(f"could not unpickle payload: {exc}") from exc
