import pytest

from retra import CacheConfig, ConfigurationError


def test_default_configuration() -> None:
    config = CacheConfig()

    assert config.default_ttl is None
    assert config.namespace == "retra"
    assert config.fail_open is True
    assert config.cache_none is True


@pytest.mark.parametrize("namespace", ["", "   ", "invalid:name"])
def test_invalid_namespace_is_rejected(namespace: str) -> None:
    with pytest.raises(ConfigurationError):
        CacheConfig(namespace=namespace)


def test_negative_default_ttl_is_rejected() -> None:
    with pytest.raises(ConfigurationError):
        CacheConfig(default_ttl=-1)
