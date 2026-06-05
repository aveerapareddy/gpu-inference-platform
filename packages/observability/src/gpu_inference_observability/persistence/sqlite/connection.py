"""SQLite connection management."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from gpu_inference_observability.persistence.sqlite.schema import CREATE_STATEMENTS, SCHEMA_VERSION


class SqliteConnection:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    def _migrate(self) -> None:
        for statement in CREATE_STATEMENTS:
            self._conn.execute(statement)
        row = self._conn.execute(
            "SELECT version FROM schema_migrations WHERE version = ?",
            (SCHEMA_VERSION,),
        ).fetchone()
        if row is None:
            self._conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
            )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
