from __future__ import annotations

from dataclasses import dataclass

import pytest


@dataclass
class FakeClock:
    value: int = 1_000_000_000

    def now_ns(self) -> int:
        return self.value

    def advance(self, nanoseconds: int) -> None:
        self.value += nanoseconds


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()
