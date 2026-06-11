from __future__ import annotations

import copy

import pytest

from retra import FrozenDict
from retra.policies.freezing import ValueMode, freeze, prepare_value, return_value


def test_nested_mutable_values_are_frozen_once() -> None:
    frozen = freeze({"items": [1, 2], "tags": {"a", "b"}})
    assert isinstance(frozen, FrozenDict)
    assert frozen["items"] == (1, 2)
    assert frozen["tags"] == frozenset({"a", "b"})


def test_copy_mode_returns_independent_values() -> None:
    original = {"items": [1]}
    stored = prepare_value(original, ValueMode.COPY)
    first = return_value(stored, ValueMode.COPY)
    second = return_value(stored, ValueMode.COPY)
    assert first == second
    assert first is not second
    assert copy.deepcopy(first) == first


def test_cycles_are_rejected_by_freeze() -> None:
    value: list[object] = []
    value.append(value)
    with pytest.raises(ValueError):
        freeze(value)
