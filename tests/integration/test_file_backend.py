from __future__ import annotations

from pathlib import Path

from retra import Cache
from retra.backends import FileBackend
from retra.serializers import JsonSerializer


def test_file_cache_persists_between_instances(tmp_path: Path) -> None:
    directory = tmp_path / "cache"

    first = Cache(FileBackend(directory), serializer=JsonSerializer())
    first.set("profile", {"name": "Ada"})
    first.close()

    second = Cache(FileBackend(directory), serializer=JsonSerializer())
    try:
        assert second.get("profile") == {"name": "Ada"}
    finally:
        second.close()
