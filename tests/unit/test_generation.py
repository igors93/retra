from __future__ import annotations

import pytest

from retra import Generation


def test_generation_advances_monotonically() -> None:
    generation = Generation("market")
    assert generation.value == 0
    assert generation.advance() == 1
    assert generation.advance(2) == 3


def test_generation_rejects_non_positive_advances() -> None:
    generation = Generation("market")
    with pytest.raises(ValueError):
        generation.advance(0)
