"""SQLite object store with per-thread read connections."""

from __future__ import annotations

import os
import sqlite3
import struct
import threading
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from ..exceptions import CorruptedEntryError, StoreError
from ..internal.clock import WallClock
from ..keys import canonical_bytes
from ..persistence import checksum
from ..protocols import Serializer
from ..records import CacheRecord
from ..serializers import PickleSerializer

_SCHEMA = """
CREATE TABLE IF NOT EXISTS retra_entries (
    digest BLOB NOT NULL,
    canonical_key BLOB NOT NULL,
    payload BLOB NOT NULL,
    payload_checksum BLOB NOT NULL,
    created_ns INTEGER NOT NULL,
    deadline_ns INTEGER NOT NULL,
    namespace_generation INTEGER NOT NULL,
    function_generation INTEGER NOT NULL,
    dependency_versions BLOB NOT NULL,
    PRIMARY KEY (digest, canonical_key)
)
"""
_DEPENDENCY = struct.Struct(">q")


def _digest(canonical_key: bytes) -> bytes:
    import hashlib

    return hashlib.blake2b(canonical_key, digest_size=16).digest()


def _encode_dependencies(values: tuple[int, ...]) -> bytes:
    return b"".join(_DEPENDENCY.pack(value) for value in values)


def _decode_dependencies(data: bytes) -> tuple[int, ...]:
    if len(data) % _DEPENDENCY.size:
        raise CorruptedEntryError("invalid dependency metadata length")
    return tuple(
        _DEPENDENCY.unpack_from(data, offset)[0] for offset in range(0, len(data), _DEPENDENCY.size)
    )


def _entry_checksum(
    canonical_key: bytes,
    payload: bytes,
    created_ns: int,
    deadline_ns: int,
    namespace_generation: int,
    function_generation: int,
    dependencies: bytes,
) -> bytes:
    metadata = struct.pack(
        ">qqqqI",
        created_ns,
        deadline_ns,
        namespace_generation,
        function_generation,
        len(dependencies),
    )
    return checksum(canonical_key + metadata + dependencies + payload)


class SQLiteStore:
    """Persistent store optimized for concurrent reads and serialized writes."""

    __slots__ = (
        "_closed",
        "_max_items",
        "_path",
        "_read_local",
        "_serializer",
        "_timeout",
        "_uri",
        "_write_connection",
        "_write_lock",
        "clock",
    )
    persistent = True

    def __init__(
        self,
        path: str | os.PathLike[str],
        *,
        serializer: Serializer | None = None,
        timeout: float = 5.0,
        max_items: int | None = None,
        enable_wal: bool = True,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if max_items is not None and max_items <= 0:
            raise ValueError("max_items must be greater than zero")
        self.clock = WallClock()
        self._serializer = serializer or PickleSerializer()
        self._timeout = timeout
        self._max_items = max_items
        self._read_local = threading.local()
        self._write_lock = threading.RLock()
        self._closed = False

        if str(path) == ":memory:":
            self._path = Path(":memory:")
            self._uri = f"file:retra-{id(self)}?mode=memory&cache=shared"
        else:
            self._path = Path(path).expanduser().resolve()
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._uri = str(self._path)

        try:
            self._write_connection = self._connect()
            self._configure(self._write_connection, enable_wal=enable_wal)
            self._write_connection.execute(_SCHEMA)
            self._write_connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_retra_deadline ON retra_entries(deadline_ns)"
            )
            self._write_connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_retra_created ON retra_entries(created_ns)"
            )
            self._write_connection.commit()
        except sqlite3.Error as exc:
            raise StoreError(f"could not initialize SQLite store: {exc}") from exc

    @property
    def path(self) -> Path:
        return self._path

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(
            self._uri,
            timeout=self._timeout,
            check_same_thread=False,
            uri=self._uri.startswith("file:"),
            cached_statements=256,
        )

    def _configure(self, connection: sqlite3.Connection, *, enable_wal: bool) -> None:
        connection.execute(f"PRAGMA busy_timeout = {int(self._timeout * 1000)}")
        connection.execute("PRAGMA synchronous = NORMAL")
        if enable_wal and self._path != Path(":memory:"):
            connection.execute("PRAGMA journal_mode = WAL")

    def _read_connection(self) -> sqlite3.Connection:
        self._ensure_open()
        connection = getattr(self._read_local, "connection", None)
        if connection is None:
            connection = self._connect()
            self._configure(connection, enable_wal=False)
            self._read_local.connection = connection
        return connection

    def get_record(self, key: object) -> CacheRecord[Any] | None:
        canonical_key = canonical_bytes(key)
        digest = _digest(canonical_key)
        now_ns = self.clock.now_ns()
        try:
            row = (
                self._read_connection()
                .execute(
                    """
                SELECT payload, payload_checksum, created_ns, deadline_ns,
                       namespace_generation, function_generation, dependency_versions
                FROM retra_entries
                WHERE digest = ? AND canonical_key = ?
                  AND (deadline_ns = 0 OR deadline_ns > ?)
                """,
                    (digest, canonical_key, now_ns),
                )
                .fetchone()
            )
        except sqlite3.Error as exc:
            raise StoreError(f"could not read SQLite cache entry: {exc}") from exc
        if row is None:
            return None
        (
            payload,
            stored_checksum,
            created_ns,
            deadline_ns,
            namespace_generation,
            function_generation,
            dependencies,
        ) = row
        payload_bytes = bytes(payload)
        dependency_bytes = bytes(dependencies)
        expected = _entry_checksum(
            canonical_key,
            payload_bytes,
            int(created_ns),
            int(deadline_ns),
            int(namespace_generation),
            int(function_generation),
            dependency_bytes,
        )
        if bytes(stored_checksum) != expected:
            raise CorruptedEntryError("SQLite cache entry checksum mismatch")
        value = self._serializer.loads(payload_bytes)
        return CacheRecord(
            value=value,
            created_ns=int(created_ns),
            deadline_ns=int(deadline_ns),
            namespace_generation=int(namespace_generation),
            function_generation=int(function_generation),
            dependency_versions=_decode_dependencies(dependency_bytes),
        )

    def get_metadata(self, key: object) -> CacheRecord[None] | None:
        canonical_key = canonical_bytes(key)
        digest = _digest(canonical_key)
        now_ns = self.clock.now_ns()
        try:
            row = (
                self._read_connection()
                .execute(
                    """
                SELECT created_ns, deadline_ns, namespace_generation,
                       function_generation, dependency_versions
                FROM retra_entries
                WHERE digest = ? AND canonical_key = ?
                  AND (deadline_ns = 0 OR deadline_ns > ?)
                """,
                    (digest, canonical_key, now_ns),
                )
                .fetchone()
            )
        except sqlite3.Error as exc:
            raise StoreError(f"could not read SQLite cache metadata: {exc}") from exc
        if row is None:
            return None
        created_ns, deadline_ns, namespace_generation, function_generation, dependencies = row
        return CacheRecord(
            value=None,
            created_ns=int(created_ns),
            deadline_ns=int(deadline_ns),
            namespace_generation=int(namespace_generation),
            function_generation=int(function_generation),
            dependency_versions=_decode_dependencies(bytes(dependencies)),
        )

    def set_record(self, key: object, record: CacheRecord[Any]) -> int:
        self.set_many({key: record})
        return 0

    def set_many(self, records: Mapping[object, CacheRecord[Any]]) -> int:
        rows: list[tuple[object, ...]] = []
        for key, record in records.items():
            canonical_key = canonical_bytes(key)
            payload = self._serializer.dumps(record.value)
            dependencies = _encode_dependencies(record.dependency_versions)
            rows.append(
                (
                    _digest(canonical_key),
                    canonical_key,
                    payload,
                    _entry_checksum(
                        canonical_key,
                        payload,
                        record.created_ns,
                        record.deadline_ns,
                        record.namespace_generation,
                        record.function_generation,
                        dependencies,
                    ),
                    record.created_ns,
                    record.deadline_ns,
                    record.namespace_generation,
                    record.function_generation,
                    dependencies,
                )
            )
        with self._write_lock:
            self._ensure_open()
            try:
                self._write_connection.executemany(
                    """
                    INSERT INTO retra_entries (
                        digest, canonical_key, payload, payload_checksum, created_ns,
                        deadline_ns, namespace_generation, function_generation,
                        dependency_versions
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(digest, canonical_key) DO UPDATE SET
                        payload = excluded.payload,
                        payload_checksum = excluded.payload_checksum,
                        created_ns = excluded.created_ns,
                        deadline_ns = excluded.deadline_ns,
                        namespace_generation = excluded.namespace_generation,
                        function_generation = excluded.function_generation,
                        dependency_versions = excluded.dependency_versions
                    """,
                    rows,
                )
                if self._max_items is not None:
                    self._write_connection.execute(
                        """
                        DELETE FROM retra_entries
                        WHERE rowid IN (
                            SELECT rowid FROM retra_entries
                            ORDER BY created_ns ASC
                            LIMIT MAX((SELECT COUNT(*) FROM retra_entries) - ?, 0)
                        )
                        """,
                        (self._max_items,),
                    )
                self._write_connection.commit()
            except sqlite3.Error as exc:
                self._write_connection.rollback()
                raise StoreError(f"could not write SQLite cache entries: {exc}") from exc
        return 0

    def delete(self, key: object) -> bool:
        canonical_key = canonical_bytes(key)
        with self._write_lock:
            self._ensure_open()
            try:
                cursor = self._write_connection.execute(
                    "DELETE FROM retra_entries WHERE digest = ? AND canonical_key = ?",
                    (_digest(canonical_key), canonical_key),
                )
                self._write_connection.commit()
                return cursor.rowcount > 0
            except sqlite3.Error as exc:
                self._write_connection.rollback()
                raise StoreError(f"could not delete SQLite cache entry: {exc}") from exc

    def delete_many(self, keys: Iterable[object]) -> int:
        pairs = [(_digest(encoded), encoded) for key in keys if (encoded := canonical_bytes(key))]
        with self._write_lock:
            self._ensure_open()
            try:
                before = self._write_connection.total_changes
                self._write_connection.executemany(
                    "DELETE FROM retra_entries WHERE digest = ? AND canonical_key = ?", pairs
                )
                self._write_connection.commit()
                return self._write_connection.total_changes - before
            except sqlite3.Error as exc:
                self._write_connection.rollback()
                raise StoreError(f"could not delete SQLite cache entries: {exc}") from exc

    def contains_key(self, key: object) -> bool:
        canonical_key = canonical_bytes(key)
        now_ns = self.clock.now_ns()
        try:
            row = (
                self._read_connection()
                .execute(
                    """
                SELECT 1 FROM retra_entries
                WHERE digest = ? AND canonical_key = ?
                  AND (deadline_ns = 0 OR deadline_ns > ?)
                LIMIT 1
                """,
                    (_digest(canonical_key), canonical_key, now_ns),
                )
                .fetchone()
            )
        except sqlite3.Error as exc:
            raise StoreError(f"could not inspect SQLite cache entry: {exc}") from exc
        return row is not None

    def get_many(self, keys: Iterable[object]) -> dict[object, CacheRecord[Any]]:
        found: dict[object, CacheRecord[Any]] = {}
        for key in keys:
            record = self.get_record(key)
            if record is not None:
                found[key] = record
        return found

    def clear(self) -> None:
        with self._write_lock:
            self._ensure_open()
            try:
                self._write_connection.execute("DELETE FROM retra_entries")
                self._write_connection.commit()
            except sqlite3.Error as exc:
                self._write_connection.rollback()
                raise StoreError(f"could not clear SQLite store: {exc}") from exc

    def prune(self) -> int:
        now_ns = self.clock.now_ns()
        with self._write_lock:
            self._ensure_open()
            try:
                cursor = self._write_connection.execute(
                    "DELETE FROM retra_entries WHERE deadline_ns != 0 AND deadline_ns <= ?",
                    (now_ns,),
                )
                removed = max(cursor.rowcount, 0)
                self._write_connection.commit()
                return removed
            except sqlite3.Error as exc:
                self._write_connection.rollback()
                raise StoreError(f"could not prune SQLite store: {exc}") from exc

    def close(self) -> None:
        with self._write_lock:
            if self._closed:
                return
            connection = getattr(self._read_local, "connection", None)
            if connection is not None and connection is not self._write_connection:
                connection.close()
            self._write_connection.close()
            self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise StoreError("SQLite store is closed")
