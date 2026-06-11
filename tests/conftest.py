from __future__ import annotations

from dataclasses import dataclass

import pytest


@dataclass
class FakeClock:
    current: float = 1_000.0

    def now(self) -> float:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += seconds


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()
