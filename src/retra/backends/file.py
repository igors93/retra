"""File-system backend with one atomically-written file per entry."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
from pathlib import Path
from threading import RLock
from typing import Any

from ..entry import CacheEntry
from ..exceptions import BackendError, CorruptedEntryError

_FORMAT_VERSION = 1
_SUFFIX = ".cache"


class FileBackend:
    """Persist entries as files below a dedicated root directory.

    Writes use ``os.replace`` so readers never observe partially-written files.
    The in-process lock protects threads, while the atomic replacement provides a
    safe last-writer-wins behavior across processes.
    """

    def __init__(self, directory: str | os.PathLike[str]) -> None:
        self._directory = Path(directory).expanduser().resolve()
        self._lock = RLock()
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise BackendError(f"could not create cache directory: {exc}") from exc

    @property
    def directory(self) -> Path:
        return self._directory

    def get(self, key: str) -> CacheEntry | None:
        path = self._path_for(key)
        with self._lock:
            try:
                raw = path.read_bytes()
            except FileNotFoundError:
                return None
            except OSError as exc:
                raise BackendError(f"could not read cache entry {path}: {exc}") from exc

        try:
            document = json.loads(raw.decode("utf-8"))
            return self._decode_document(document, expected_key=key)
        except CorruptedEntryError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
            raise CorruptedEntryError(f"cache entry {path} is corrupted: {exc}") from exc

    def set(self, entry: CacheEntry) -> None:
        path = self._path_for(entry.key)
        document = {
            "version": _FORMAT_VERSION,
            "key": entry.key,
            "payload": base64.b64encode(entry.payload).decode("ascii"),
            "created_at": entry.created_at,
            "expires_at": entry.expires_at,
        }
        data = json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")

        with self._lock:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                self._atomic_write(path, data)
            except OSError as exc:
                raise BackendError(f"could not write cache entry {path}: {exc}") from exc

    def delete(self, key: str) -> bool:
        path = self._path_for(key)
        with self._lock:
            try:
                path.unlink()
            except FileNotFoundError:
                return False
            except OSError as exc:
                raise BackendError(f"could not delete cache entry {path}: {exc}") from exc
            else:
                self._remove_empty_parent(path.parent)
                return True

    def clear(self) -> None:
        with self._lock:
            try:
                for path in self._directory.rglob(f"*{_SUFFIX}"):
                    path.unlink(missing_ok=True)
                for directory in sorted(
                    (path for path in self._directory.rglob("*") if path.is_dir()),
                    reverse=True,
                ):
                    directory.rmdir()
            except OSError as exc:
                raise BackendError(f"could not clear file cache: {exc}") from exc

    def close(self) -> None:
        """File storage does not keep open handles between operations."""

    def _path_for(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self._directory / digest[:2] / f"{digest}{_SUFFIX}"

    @staticmethod
    def _atomic_write(path: Path, data: bytes) -> None:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _decode_document(document: Any, *, expected_key: str) -> CacheEntry:
        if not isinstance(document, dict):
            raise CorruptedEntryError("cache document must be an object")
        if document.get("version") != _FORMAT_VERSION:
            raise CorruptedEntryError("unsupported cache file version")
        if document.get("key") != expected_key:
            raise CorruptedEntryError("cache key does not match file contents")

        payload_text = document["payload"]
        if not isinstance(payload_text, str):
            raise CorruptedEntryError("payload must be base64 text")

        try:
            payload = base64.b64decode(payload_text.encode("ascii"), validate=True)
            created_at = float(document["created_at"])
            raw_expires_at = document["expires_at"]
            expires_at = None if raw_expires_at is None else float(raw_expires_at)
        except (ValueError, TypeError, UnicodeEncodeError) as exc:
            raise CorruptedEntryError(f"invalid cache metadata: {exc}") from exc

        return CacheEntry(
            key=expected_key,
            payload=payload,
            created_at=created_at,
            expires_at=expires_at,
        )

    def _remove_empty_parent(self, directory: Path) -> None:
        if directory == self._directory:
            return
        try:
            directory.rmdir()
        except OSError:
            # The directory is not empty, was already removed, or cannot be changed.
            return
