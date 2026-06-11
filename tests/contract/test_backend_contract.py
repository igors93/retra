from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Callable

import pytest

from retra.backends import FileBackend, MemoryBackend, SQLiteBackend
from retra.entry import CacheEntry
from retra.protocols import Backend


@contextmanager
def _backend(factory: Callable[[], Backend]) -> Iterator[Backend]:
    backend = factory()
    try:
        yield backend
    finally:
        backend.close()


@pytest.fixture(params=["memory", "file", "sqlite"])
def backend_factory(request, tmp_path: Path) -> Callable[[], Backend]:
    if request.param == "memory":
        return MemoryBackend
    if request.param == "file":
        return lambda: FileBackend(tmp_path / "files")
    return lambda: SQLiteBackend(tmp_path / "cache.db")


def _entry(key: str, payload: bytes = b"value") -> CacheEntry:
    return CacheEntry(key=key, payload=payload, created_at=100.0, expires_at=200.0)


def test_missing_key_returns_none(backend_factory: Callable[[], Backend]) -> None:
    with _backend(backend_factory) as backend:
        assert backend.get("missing") is None


def test_entry_can_be_stored_and_retrieved(backend_factory: Callable[[], Backend]) -> None:
    with _backend(backend_factory) as backend:
        entry = _entry("key", b"payload")

        backend.set(entry)

        assert backend.get("key") == entry


def test_entry_can_be_overwritten(backend_factory: Callable[[], Backend]) -> None:
    with _backend(backend_factory) as backend:
        backend.set(_entry("key", b"first"))
        backend.set(_entry("key", b"second"))

        assert backend.get("key") == _entry("key", b"second")


def test_delete_reports_whether_key_existed(backend_factory: Callable[[], Backend]) -> None:
    with _backend(backend_factory) as backend:
        backend.set(_entry("key"))

        assert backend.delete("key") is True
        assert backend.delete("key") is False
        assert backend.get("key") is None


def test_clear_removes_all_entries(backend_factory: Callable[[], Backend]) -> None:
    with _backend(backend_factory) as backend:
        backend.set(_entry("first"))
        backend.set(_entry("second"))

        backend.clear()

        assert backend.get("first") is None
        assert backend.get("second") is None
