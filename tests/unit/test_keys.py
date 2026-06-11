from __future__ import annotations

from dataclasses import dataclass

import pytest

from retra.exceptions import KeyGenerationError
from retra.keys import canonical_bytes, exact_component


def test_exact_keys_distinguish_equal_values_of_different_types() -> None:
    assert exact_component(True) != exact_component(1)
    assert exact_component(1) != exact_component(1.0)
    assert exact_component(0.0) != exact_component(-0.0)


def test_mapping_order_does_not_change_canonical_key() -> None:
    assert canonical_bytes({"a": 1, "b": 2}) == canonical_bytes({"b": 2, "a": 1})


def test_mutable_key_is_snapshotted() -> None:
    value = [1, 2]
    key = exact_component(value)
    value.append(3)
    assert key != exact_component(value)


@dataclass
class Data:
    left: int
    right: str


def test_dataclass_keys_are_deterministic() -> None:
    assert canonical_bytes(Data(1, "x")) == canonical_bytes(Data(1, "x"))


class Unsupported:
    pass


def test_unsupported_objects_require_an_explicit_cache_key() -> None:
    with pytest.raises(KeyGenerationError):
        canonical_bytes(Unsupported())


class Supported:
    def __init__(self, identifier: int) -> None:
        self.identifier = identifier

    def __cache_key__(self) -> int:
        return self.identifier


def test_custom_cache_key_protocol_is_supported() -> None:
    assert canonical_bytes(Supported(10)) == canonical_bytes(Supported(10))
