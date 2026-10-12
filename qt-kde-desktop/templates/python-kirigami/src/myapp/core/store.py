"""The app's database: SQLite in the data dir.

One connection, owned by the worker thread (sqlite3 objects must stay on the thread that
created them). WAL lets readers in other processes (a CLI, a backup) work during writes.
Schema changes are numbered migrations tracked with PRAGMA user_version.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

MIGRATIONS = (
    """
    CREATE TABLE recent_folder (
        path TEXT PRIMARY KEY,
        opened_at REAL NOT NULL
    )
    """,
    # Append new migrations; never edit a released one.
)
RECENT_LIMIT = 10


class Store:
    def __init__(self, path: Path) -> None:
        self._db = sqlite3.connect(path)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def _migrate(self) -> None:
        (current,) = self._db.execute("PRAGMA user_version").fetchone()
        for number, script in enumerate(MIGRATIONS[current:], start=current + 1):
            with self._db:
                self._db.executescript(script)
                self._db.execute(f"PRAGMA user_version = {number}")

    def remember_folder(self, path: str) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO recent_folder(path, opened_at) VALUES (?, ?)"
                " ON CONFLICT(path) DO UPDATE SET opened_at = excluded.opened_at",
                (path, time.time()),
            )
            self._db.execute(
                "DELETE FROM recent_folder WHERE path NOT IN"
                " (SELECT path FROM recent_folder ORDER BY opened_at DESC LIMIT ?)",
                (RECENT_LIMIT,),
            )

    def recent_folders(self) -> list[str]:
        rows = self._db.execute("SELECT path FROM recent_folder ORDER BY opened_at DESC")
        return [path for (path,) in rows]

    def close(self) -> None:
        self._db.close()
