from __future__ import annotations

from pathlib import Path

from retra import Cache
from retra.backends import SQLiteBackend


def test_sqlite_cache_persists_between_connections(tmp_path: Path) -> None:
    path = tmp_path / "cache.db"

    first = Cache(SQLiteBackend(path))
    first.set("result", [1, 2, 3])
    first.close()

    second = Cache(SQLiteBackend(path))
    try:
        assert second.get("result") == [1, 2, 3]
    finally:
        second.close()


def test_sqlite_can_delete_expired_rows(tmp_path: Path) -> None:
    backend = SQLiteBackend(tmp_path / "cache.db")
    try:
        cache = Cache(backend)
        cache.set("short", "value", ttl=1)
        assert backend.delete_expired(10**20) == 1
        assert cache.get("short") is None
    finally:
        backend.close()
