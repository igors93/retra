"""Regression tests: JSON serializer raises on non-serializable inputs."""

from __future__ import annotations

import pytest

from retra.exceptions import SerializationError
from retra.serializers.json import JsonSerializer


def test_string_keys_round_trip() -> None:
    s = JsonSerializer()
    original = {"a": 1, "b": [2, 3]}
    assert s.loads(s.dumps(original)) == original


def test_nested_string_keys_round_trip() -> None:
    s = JsonSerializer()
    original = {"outer": {"inner": True}}
    assert s.loads(s.dumps(original)) == original


def test_integer_key_raises_serialization_error() -> None:
    """Non-string mapping key must raise SerializationError, not silently coerce."""
    s = JsonSerializer()
    with pytest.raises(SerializationError, match="string mapping keys"):
        s.dumps({1: "value"})


def test_tuple_key_raises_serialization_error() -> None:
    s = JsonSerializer()
    with pytest.raises(SerializationError, match="string mapping keys"):
        s.dumps({(1, 2): "pair"})


def test_nested_integer_key_raises_serialization_error() -> None:
    s = JsonSerializer()
    with pytest.raises(SerializationError, match="string mapping keys"):
        s.dumps({"outer": {42: "inner"}})


def test_tuple_is_encoded_as_list() -> None:
    """Tuples are re-encoded as JSON arrays (lossy but explicit)."""
    s = JsonSerializer()
    payload = s.dumps((1, 2, 3))
    assert s.loads(payload) == [1, 2, 3]


def test_frozenset_is_encoded_as_sorted_list() -> None:
    s = JsonSerializer()
    payload = s.dumps(frozenset({3, 1, 2}))
    result = s.loads(payload)
    assert sorted(result) == [1, 2, 3]


def test_non_serializable_type_raises_serialization_error() -> None:
    s = JsonSerializer()

    class Opaque:
        pass

    with pytest.raises(SerializationError):
        s.dumps(Opaque())


def test_corrupted_payload_raises_serialization_error() -> None:
    s = JsonSerializer()
    with pytest.raises(SerializationError):
        s.loads(b"not valid json {{{")
