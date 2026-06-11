"""Binary file store with atomic replacement and collision verification."""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Iterable, Mapping
from contextlib import suppress
from pathlib import Path
from threading import RLock
from typing import Any

from ..exceptions import CorruptedEntryError, StoreError
from ..internal.clock import WallClock
from ..keys import canonical_bytes
from ..persistence import decode_envelope, encode_envelope
from ..protocols import Serializer
from ..records import CacheRecord
from ..serializers import PickleSerializer


class FileStore:
    """Persist each entry as a versioned binary envelope.

    A digest selects a small collision directory. The canonical key stored inside every candidate
    proves identity, so a digest collision can never return another key's value.
    """

    __slots__ = ("_directory", "_lock", "_max_items", "_serializer", "clock")
    persistent = True

    def __init__(
        self,
        directory: str | os.PathLike[str],
        *,
        serializer: Serializer | None = None,
        max_items: int | None = None,
    ) -> None:
        if max_items is not None and max_items <= 0:
            raise ValueError("max_items must be greater than zero")
        self.clock = WallClock()
        self._serializer = serializer or PickleSerializer()
        self._max_items = max_items
        self._directory = Path(directory).expanduser().resolve()
        self._directory.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    @property
    def directory(self) -> Path:
        return self._directory

    @staticmethod
    def _digest(key: bytes) -> str:
        return hashlib.blake2b(key, digest_size=16).hexdigest()

    def _bucket(self, canonical_key: bytes) -> Path:
        digest = self._digest(canonical_key)
        return self._directory / digest[:2] / digest[2:]

    def _candidates(self, canonical_key: bytes) -> list[Path]:
        bucket = self._bucket(canonical_key)
        return sorted(bucket.glob("*.rtr")) if bucket.exists() else []

    def get_record(self, key: object) -> CacheRecord[Any] | None:
        canonical_key = canonical_bytes(key)
        now_ns = self.clock.now_ns()
        with self._lock:
            for path in self._candidates(canonical_key):
                try:
                    decoded = decode_envelope(path.read_bytes())
                except OSError as exc:
                    raise StoreError(f"could not read cache file {path}: {exc}") from exc
                if decoded.canonical_key != canonical_key:
                    continue
                metadata = decoded.record_metadata
                if metadata.is_expired(now_ns):
                    path.unlink(missing_ok=True)
                    return None
                value = self._serializer.loads(decoded.payload)
                return CacheRecord(
                    value=value,
                    created_ns=metadata.created_ns,
                    deadline_ns=metadata.deadline_ns,
                    namespace_generation=metadata.namespace_generation,
                    function_generation=metadata.function_generation,
                    dependency_versions=metadata.dependency_versions,
                )
        return None

    def get_metadata(self, key: object) -> CacheRecord[None] | None:
        canonical_key = canonical_bytes(key)
        now_ns = self.clock.now_ns()
        with self._lock:
            for path in self._candidates(canonical_key):
                decoded = decode_envelope(path.read_bytes())
                if decoded.canonical_key != canonical_key:
                    continue
                metadata = decoded.record_metadata
                if metadata.is_expired(now_ns):
                    return None
                return metadata
        return None

    def set_record(self, key: object, record: CacheRecord[Any]) -> int:
        canonical_key = canonical_bytes(key)
        payload = self._serializer.dumps(record.value)
        data = encode_envelope(canonical_key, payload, record)
        with self._lock:
            bucket = self._bucket(canonical_key)
            bucket.mkdir(parents=True, exist_ok=True)
            target: Path | None = None
            candidates = self._candidates(canonical_key)
            for path in candidates:
                try:
                    decoded = decode_envelope(path.read_bytes())
                except CorruptedEntryError:
                    # A corrupted candidate is quarantined by replacing its suffix. It will never be
                    # considered by future lookups but remains available for diagnosis.
                    path.replace(path.with_suffix(".corrupt"))
                    continue
                if decoded.canonical_key == canonical_key:
                    target = path
                    break
            if target is None:
                used = {path.stem for path in candidates}
                index = 0
                while str(index) in used:
                    index += 1
                target = bucket / f"{index}.rtr"
            self._atomic_write(target, data)
            evicted = self._enforce_limit()
            return evicted

    def set_many(self, records: Mapping[object, CacheRecord[Any]]) -> int:
        return sum(self.set_record(key, record) for key, record in records.items())

    def delete(self, key: object) -> bool:
        canonical_key = canonical_bytes(key)
        with self._lock:
            for path in self._candidates(canonical_key):
                decoded = decode_envelope(path.read_bytes())
                if decoded.canonical_key == canonical_key:
                    path.unlink()
                    self._remove_empty_parents(path.parent)
                    return True
        return False

    def delete_many(self, keys: Iterable[object]) -> int:
        return sum(self.delete(key) for key in keys)

    def contains_key(self, key: object) -> bool:
        canonical_key = canonical_bytes(key)
        now_ns = self.clock.now_ns()
        with self._lock:
            for path in self._candidates(canonical_key):
                decoded = decode_envelope(path.read_bytes())
                if decoded.canonical_key == canonical_key:
                    return not decoded.record_metadata.is_expired(now_ns)
        return False

    def get_many(self, keys: Iterable[object]) -> dict[object, CacheRecord[Any]]:
        found: dict[object, CacheRecord[Any]] = {}
        for key in keys:
            record = self.get_record(key)
            if record is not None:
                found[key] = record
        return found

    def clear(self) -> None:
        with self._lock:
            for path in self._directory.rglob("*.rtr"):
                path.unlink(missing_ok=True)
            for directory in sorted(
                (item for item in self._directory.rglob("*") if item.is_dir()), reverse=True
            ):
                with suppress(OSError):
                    directory.rmdir()

    def prune(self) -> int:
        now_ns = self.clock.now_ns()
        removed = 0
        with self._lock:
            for path in self._directory.rglob("*.rtr"):
                try:
                    decoded = decode_envelope(path.read_bytes())
                except CorruptedEntryError:
                    path.replace(path.with_suffix(".corrupt"))
                    removed += 1
                    continue
                if decoded.record_metadata.is_expired(now_ns):
                    path.unlink(missing_ok=True)
                    removed += 1
            removed += self._enforce_limit()
        return removed

    def close(self) -> None:
        return None

    def _enforce_limit(self) -> int:
        if self._max_items is None:
            return 0
        files = list(self._directory.rglob("*.rtr"))
        excess = len(files) - self._max_items
        if excess <= 0:
            return 0
        files.sort(key=lambda path: path.stat().st_mtime_ns)
        for path in files[:excess]:
            path.unlink(missing_ok=True)
        return excess

    @staticmethod
    def _atomic_write(path: Path, data: bytes) -> None:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def _remove_empty_parents(self, directory: Path) -> None:
        current = directory
        while current != self._directory:
            try:
                current.rmdir()
            except OSError:
                return
            current = current.parent
