"""SQLite persistence layer (stdlib only — no native build step needed)."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.config import settings

_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS citizens (
    id                TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    name_hi           TEXT,
    gender            TEXT,
    age               INTEGER,
    aadhaar_last4     TEXT NOT NULL,
    mobile            TEXT NOT NULL,
    district          TEXT NOT NULL,
    block             TEXT,
    village           TEXT,
    land_bigha        REAL DEFAULT 0,
    occupation        TEXT,
    social_category   TEXT,
    family_members    INTEGER DEFAULT 1,
    income_monthly    INTEGER DEFAULT 0,
    language          TEXT DEFAULT 'hi'
);

CREATE TABLE IF NOT EXISTS applications (
    id              TEXT PRIMARY KEY,
    citizen_id      TEXT NOT NULL REFERENCES citizens(id) ON DELETE CASCADE,
    scheme_id       TEXT NOT NULL,
    status          TEXT NOT NULL,
    status_hi       TEXT,
    amount          INTEGER DEFAULT 0,
    reference       TEXT,
    last_updated    TEXT,
    created_at      TEXT
);

CREATE TABLE IF NOT EXISTS application_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id  TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    seq             INTEGER DEFAULT 0,
    date            TEXT,
    label           TEXT,
    label_hi        TEXT,
    status          TEXT
);

CREATE TABLE IF NOT EXISTS grievances (
    id              TEXT PRIMARY KEY,
    citizen_name    TEXT,
    contact         TEXT,
    category        TEXT NOT NULL,
    category_hi     TEXT,
    issue           TEXT,
    district        TEXT,
    block           TEXT,
    village         TEXT,
    duration_days   INTEGER DEFAULT 0,
    urgency         TEXT DEFAULT 'medium',
    sentiment       TEXT DEFAULT 'neutral',
    status          TEXT DEFAULT 'NEW',
    priority        TEXT DEFAULT 'P2',
    assigned_to     TEXT,
    summary         TEXT,
    summary_en      TEXT,
    transcript      TEXT,
    language        TEXT DEFAULT 'hi',
    channel         TEXT DEFAULT 'voice',
    created_at      TEXT,
    updated_at      TEXT
);

CREATE TABLE IF NOT EXISTS grievance_notes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    grievance_id    TEXT NOT NULL REFERENCES grievances(id) ON DELETE CASCADE,
    note            TEXT,
    author          TEXT DEFAULT 'DM Office',
    created_at      TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,
    created_at      TEXT,
    language        TEXT DEFAULT 'hi',
    state_json      TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS turns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    turn_index      INTEGER,
    role            TEXT,
    text            TEXT,
    intent          TEXT,
    language        TEXT,
    created_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_app_citizen ON applications(citizen_id);
CREATE INDEX IF NOT EXISTS idx_app_scheme ON applications(scheme_id);
CREATE INDEX IF NOT EXISTS idx_gr_cat ON grievances(category);
CREATE INDEX IF NOT EXISTS idx_gr_district ON grievances(district);
CREATE INDEX IF NOT EXISTS idx_gr_status ON grievances(status);
CREATE INDEX IF NOT EXISTS idx_turn_session ON turns(session_id);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    """Thread-safe SQLite wrapper. One connection guarded by a re-entrant lock."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else settings.db_file
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self.init_schema()

    def init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- low level -----------------------------------------------------------
    def execute(self, sql: str, params: tuple | dict = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def executemany(self, sql: str, seq: list[tuple]) -> None:
        with self._lock:
            self._conn.executemany(sql, seq)
            self._conn.commit()

    def query(self, sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._conn.execute(sql, params).fetchall())

    def query_one(self, sql: str, params: tuple | dict = ()) -> sqlite3.Row | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    # -- helpers -------------------------------------------------------------
    def insert(self, table: str, data: dict[str, Any]) -> None:
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        self.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", tuple(data.values()))

    def update(self, table: str, data: dict[str, Any], where: str, params: tuple) -> None:
        if not data:
            return
        assignments = ", ".join(f"{k} = ?" for k in data)
        self.execute(f"UPDATE {table} SET {assignments} WHERE {where}", (*data.values(), *params))

    def close(self) -> None:
        with self._lock:
            self._conn.close()


_db: Database | None = None
_db_lock = threading.Lock()


def get_db() -> Database:
    """Process-wide singleton database handle."""
    global _db
    if _db is None:
        with _db_lock:
            if _db is None:
                _db = Database()
    return _db


def reset_db(path: Path | str | None = None) -> Database:
    """Replace the singleton with a fresh handle (used by tests)."""
    global _db
    with _db_lock:
        if _db is not None:
            try:
                _db.close()
            except Exception:  # pragma: no cover - defensive
                pass
        _db = Database(path)
        return _db


@contextmanager
def session_scope() -> Iterator[sqlite3.Connection]:
    """Raw connection context for advanced use."""
    db = get_db()
    with db._lock:  # noqa: SLF001 - intentional internal use
        yield db._conn  # noqa: SLF001


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [row_to_dict(r) for r in rows]  # type: ignore[misc]


def json_loads(value: str | None, default: Any = None) -> Any:
    if not value:
        return default if default is not None else {}
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default if default is not None else {}
