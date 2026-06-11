from __future__ import annotations

from pathlib import Path

import pytest

from retra import Cache, CorruptedEntryError
from retra.stores import FileStore


def test_sqlite_values_survive_cache_restart(tmp_path: Path) -> None:
    path = tmp_path / "cache.db"
    with Cache.sqlite(path, value_mode="reference") as first:
        first.set("key", {"value": 10})
    with Cache.sqlite(path, value_mode="reference") as second:
        assert second.get("key") == {"value": 10}


def test_file_values_survive_cache_restart(tmp_path: Path) -> None:
    directory = tmp_path / "files"
    with Cache.file(directory, value_mode="reference") as first:
        first.set("key", [1, 2, 3])
    with Cache.file(directory, value_mode="reference") as second:
        assert second.get("key") == [1, 2, 3]


def test_file_checksum_detects_corruption(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "files")
    cache = Cache(store)
    cache.set("key", "value")
    file_path = next((tmp_path / "files").rglob("*.rtr"))
    data = bytearray(file_path.read_bytes())
    data[-1] ^= 0x01
    file_path.write_bytes(data)
    with pytest.raises(CorruptedEntryError):
        cache.get("key")


class CountingSerializer:
    name = "counting"

    def __init__(self) -> None:
        self.loads_count = 0

    def dumps(self, value):
        import pickle

        return pickle.dumps(value)

    def loads(self, payload):
        import pickle

        self.loads_count += 1
        return pickle.loads(payload)


def test_sqlite_contains_does_not_deserialize_payload(tmp_path: Path) -> None:
    serializer = CountingSerializer()
    cache = Cache.sqlite(
        tmp_path / "metadata.db",
        serializer=serializer,
        value_mode="reference",
    )
    cache.set("key", {"large": list(range(100))})
    assert cache.contains("key")
    assert serializer.loads_count == 0
    assert cache.get("key") == {"large": list(range(100))}
    assert serializer.loads_count == 1
    cache.close()
