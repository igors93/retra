from retra import CacheEntry


def test_entry_without_expiration_never_expires() -> None:
    entry = CacheEntry(key="key", payload=b"value", created_at=10.0)

    assert entry.is_expired(1_000.0) is False


def test_entry_expires_at_boundary() -> None:
    entry = CacheEntry(key="key", payload=b"value", created_at=10.0, expires_at=20.0)

    assert entry.is_expired(19.999) is False
    assert entry.is_expired(20.0) is True
