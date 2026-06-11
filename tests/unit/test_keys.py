from __future__ import annotations

from dataclasses import dataclass

import pytest

from retra import KeyGenerationError
from retra.keys import FunctionKeyBuilder


def sample(a: int, b: int = 2, *, options: dict[str, int] | None = None) -> int:
    return a + b + sum((options or {}).values())


def test_keyword_order_does_not_change_key() -> None:
    builder = FunctionKeyBuilder()

    first = builder.build(sample, (1,), {"b": 3, "options": {"x": 1, "y": 2}})
    second = builder.build(sample, (1,), {"options": {"y": 2, "x": 1}, "b": 3})

    assert first == second


def test_default_arguments_are_applied() -> None:
    builder = FunctionKeyBuilder()

    assert builder.build(sample, (1,), {}) == builder.build(sample, (1, 2), {"options": None})


def test_version_changes_key() -> None:
    builder = FunctionKeyBuilder()

    assert builder.build(sample, (1,), {}, version="1") != builder.build(
        sample, (1,), {}, version="2"
    )


@dataclass
class User:
    identifier: int
    name: str


def test_dataclasses_have_stable_keys() -> None:
    builder = FunctionKeyBuilder()

    first = builder.build(lambda user: user.identifier, (User(1, "Ada"),), {})
    second = builder.build(lambda user: user.identifier, (User(1, "Ada"),), {})

    assert first == second


def test_cyclic_values_are_rejected() -> None:
    builder = FunctionKeyBuilder()
    values: list[object] = []
    values.append(values)

    with pytest.raises(KeyGenerationError):
        builder.build(lambda value: value, (values,), {})
