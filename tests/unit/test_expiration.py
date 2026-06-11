from __future__ import annotations

from datetime import timedelta

import pytest

from retra.exceptions import ConfigurationError
from retra.policies.expiration import ttl_to_ns


def test_ttl_strings_are_converted_to_nanoseconds() -> None:
    assert ttl_to_ns("50ms") == 50_000_000
    assert ttl_to_ns("2s") == 2_000_000_000
    assert ttl_to_ns("1.5m") == 90_000_000_000


def test_numeric_ttl_is_interpreted_as_seconds() -> None:
    assert ttl_to_ns(0.5) == 500_000_000
    assert ttl_to_ns(timedelta(seconds=2)) == 2_000_000_000


def test_invalid_ttl_is_rejected() -> None:
    with pytest.raises(ConfigurationError):
        ttl_to_ns("later")
    with pytest.raises(ConfigurationError):
        ttl_to_ns(-1)
    with pytest.raises(ConfigurationError):
        ttl_to_ns(True)
