"""SQLite snapshots and one ingestion lease for Ontologic Y."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS lease (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  owner TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS polls (
  poll_id INTEGER PRIMARY KEY,
  retrieved_at TEXT NOT NULL,
  owner TEXT NOT NULL,
  ok INTEGER NOT NULL,
  mode TEXT,
  detail TEXT
);
CREATE TABLE IF NOT EXISTS logs (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  retrieved_at TEXT,
  body TEXT
);
CREATE TABLE IF NOT EXISTS snapshots (
  snapshot_id TEXT PRIMARY KEY,
  retrieved_at TEXT NOT NULL,
  body TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS current_snapshot (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  snapshot_id TEXT NOT NULL
);
"""


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._db = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(SCHEMA)

    def close(self) -> None:
        self._db.close()

    def try_lease(self, owner: str, now: datetime, ttl: timedelta = timedelta(seconds=20)) -> bool:
        expires = (now + ttl).isoformat()
        self._db.execute("BEGIN IMMEDIATE")
        try:
            row = self._db.execute("SELECT owner, expires_at FROM lease WHERE id = 1").fetchone()
            if row and row["expires_at"] > now.isoformat() and row["owner"] != owner:
                self._db.execute("COMMIT")
                return False
            self._db.execute(
                "INSERT INTO lease(id, owner, expires_at) VALUES (1, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET owner = excluded.owner, expires_at = excluded.expires_at",
                (owner, expires),
            )
            self._db.execute("COMMIT")
            return True
        except Exception:
            self._db.execute("ROLLBACK")
            raise

    def release(self, owner: str) -> None:
        self._db.execute("DELETE FROM lease WHERE id = 1 AND owner = ?", (owner,))

    def record_poll(self, now: datetime, owner: str, ok: bool, mode: str, detail: str) -> None:
        self._db.execute(
            "INSERT INTO polls(retrieved_at, owner, ok, mode, detail) VALUES (?, ?, ?, ?, ?)",
            (now.isoformat(), owner, int(ok), mode, detail),
        )

    def save_logs(self, now: datetime, body: dict) -> None:
        payload = json.dumps(body, default=str)
        self._db.execute(
            "INSERT INTO logs(id, retrieved_at, body) VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET retrieved_at = excluded.retrieved_at, body = excluded.body",
            (now.isoformat(), payload),
        )

    def logs(self) -> dict | None:
        row = self._db.execute("SELECT retrieved_at, body FROM logs WHERE id = 1").fetchone()
        if row is None:
            return None
        body = json.loads(row["body"])
        body["retrieved_at"] = row["retrieved_at"]
        return body

    def save_snapshot(self, snapshot_id: str, now: datetime, body: dict) -> None:
        payload = json.dumps(body, default=str)
        self._db.execute("BEGIN IMMEDIATE")
        try:
            self._db.execute(
                "INSERT INTO snapshots(snapshot_id, retrieved_at, body) VALUES (?, ?, ?)",
                (snapshot_id, now.isoformat(), payload),
            )
            self._db.execute(
                "INSERT INTO current_snapshot(id, snapshot_id) VALUES (1, ?) "
                "ON CONFLICT(id) DO UPDATE SET snapshot_id = excluded.snapshot_id",
                (snapshot_id,),
            )
            self._db.execute("COMMIT")
        except Exception:
            self._db.execute("ROLLBACK")
            raise

    def current(self) -> dict | None:
        row = self._db.execute(
            "SELECT snapshots.body FROM current_snapshot JOIN snapshots USING (snapshot_id) WHERE current_snapshot.id = 1"
        ).fetchone()
        return None if row is None else json.loads(row["body"])

    def recent_failures(self, now: datetime, window: timedelta = timedelta(minutes=2)) -> int:
        cutoff = (now - window).isoformat()
        row = self._db.execute(
            "SELECT COUNT(*) AS n FROM polls WHERE ok = 0 AND retrieved_at >= ?",
            (cutoff,),
        ).fetchone()
        return int(row["n"])
