"""SQLite-backed persistent cache."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from threading import RLock

from ..entry import CacheEntry
from ..exceptions import BackendError

_SCHEMA = """
CREATE TABLE IF NOT EXISTS retra_entries (
    key TEXT PRIMARY KEY,
    payload BLOB NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL
)
"""


class SQLiteBackend:
    """Persist cache entries in a local SQLite database."""

    def __init__(
        self,
        path: str | os.PathLike[str],
        *,
        timeout: float = 5.0,
        enable_wal: bool = True,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        self._path = Path(path).expanduser()
        self._lock = RLock()
        self._closed = False

        try:
            if str(self._path) != ":memory:":
                self._path = self._path.resolve()
                self._path.parent.mkdir(parents=True, exist_ok=True)

            self._connection = sqlite3.connect(
                str(self._path),
                timeout=timeout,
                check_same_thread=False,
            )
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute(f"PRAGMA busy_timeout = {int(timeout * 1000)}")
            if enable_wal and str(self._path) != ":memory:":
                self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute(_SCHEMA)
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_retra_expires_at "
                "ON retra_entries(expires_at)"
            )
            self._connection.commit()
        except (OSError, sqlite3.Error) as exc:
            raise BackendError(f"could not initialize SQLite backend: {exc}") from exc

    @property
    def path(self) -> Path:
        return self._path

    def get(self, key: str) -> CacheEntry | None:
        with self._lock:
            self._ensure_open()
            try:
                row = self._connection.execute(
                    "SELECT payload, created_at, expires_at "
                    "FROM retra_entries WHERE key = ?",
                    (key,),
                ).fetchone()
            except sqlite3.Error as exc:
                raise BackendError(f"could not read SQLite cache entry: {exc}") from exc

        if row is None:
            return None

        payload, created_at, expires_at = row
        return CacheEntry(
            key=key,
            payload=bytes(payload),
            created_at=float(created_at),
            expires_at=None if expires_at is None else float(expires_at),
        )

    def set(self, entry: CacheEntry) -> None:
        with self._lock:
            self._ensure_open()
            try:
                self._connection.execute(
                    """
                    INSERT INTO retra_entries (key, payload, created_at, expires_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        payload = excluded.payload,
                        created_at = excluded.created_at,
                        expires_at = excluded.expires_at
                    """,
                    (
                        entry.key,
                        sqlite3.Binary(entry.payload),
                        entry.created_at,
                        entry.expires_at,
                    ),
                )
                self._connection.commit()
            except sqlite3.Error as exc:
                self._connection.rollback()
                raise BackendError(f"could not write SQLite cache entry: {exc}") from exc

    def delete(self, key: str) -> bool:
        with self._lock:
            self._ensure_open()
            try:
                cursor = self._connection.execute(
                    "DELETE FROM retra_entries WHERE key = ?",
                    (key,),
                )
                self._connection.commit()
                return cursor.rowcount > 0
            except sqlite3.Error as exc:
                self._connection.rollback()
                raise BackendError(f"could not delete SQLite cache entry: {exc}") from exc

    def clear(self) -> None:
        with self._lock:
            self._ensure_open()
            try:
                self._connection.execute("DELETE FROM retra_entries")
                self._connection.commit()
            except sqlite3.Error as exc:
                self._connection.rollback()
                raise BackendError(f"could not clear SQLite cache: {exc}") from exc

    def delete_expired(self, now: float) -> int:
        """Delete expired entries and return the number of removed rows."""

        with self._lock:
            self._ensure_open()
            try:
                cursor = self._connection.execute(
                    "DELETE FROM retra_entries "
                    "WHERE expires_at IS NOT NULL AND expires_at <= ?",
                    (float(now),),
                )
                self._connection.commit()
                return max(cursor.rowcount, 0)
            except sqlite3.Error as exc:
                self._connection.rollback()
                raise BackendError(f"could not delete expired SQLite entries: {exc}") from exc

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            try:
                self._connection.close()
            except sqlite3.Error as exc:
                raise BackendError(f"could not close SQLite backend: {exc}") from exc
            finally:
                self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise BackendError("SQLite backend is closed")
