from __future__ import annotations

import pytest

from retra import CacheConfig
from retra.exceptions import ConfigurationError


def test_config_requires_power_of_two_shards() -> None:
    with pytest.raises(ConfigurationError):
        CacheConfig(shards=3)


def test_config_rejects_invalid_capacity() -> None:
    with pytest.raises(ConfigurationError):
        CacheConfig(max_items=0)
