"""SQLite snapshots and a single shared ingestion lease."""

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
CREATE TABLE IF NOT EXISTS quote_state (
  natural_key TEXT PRIMARY KEY,
  american TEXT,
  status TEXT,
  source_updated_at TEXT,
  last_quote_change_at TEXT,
  active INTEGER NOT NULL,
  body TEXT NOT NULL
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
CREATE TABLE IF NOT EXISTS nba_probe (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  probed_at TEXT,
  status TEXT,
  preseason_start TEXT,
  season TEXT,
  detail TEXT,
  games_json TEXT
);
CREATE TABLE IF NOT EXISTS credit_ledger (
  id INTEGER PRIMARY KEY,
  recorded_at TEXT NOT NULL,
  bucket TEXT NOT NULL,
  purpose TEXT NOT NULL,
  endpoint TEXT,
  credits_last INTEGER NOT NULL,
  credits_used INTEGER,
  credits_remaining INTEGER,
  season_phase TEXT
);
CREATE TABLE IF NOT EXISTS raw_payloads (
  id INTEGER PRIMARY KEY,
  recorded_at TEXT NOT NULL,
  endpoint TEXT NOT NULL,
  sport_key TEXT,
  event_id TEXT,
  season_phase TEXT,
  body TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS coverage_cells (
  id INTEGER PRIMARY KEY,
  recorded_at TEXT NOT NULL,
  sport_key TEXT,
  event_id TEXT,
  nba_game_id TEXT,
  season_phase TEXT NOT NULL,
  bookmaker TEXT NOT NULL,
  market_key TEXT NOT NULL,
  status TEXT NOT NULL,
  line_count INTEGER
);
CREATE TABLE IF NOT EXISTS observed_lines (
  id INTEGER PRIMARY KEY,
  recorded_at TEXT NOT NULL,
  event_id TEXT,
  nba_game_id TEXT,
  season_phase TEXT,
  bookmaker TEXT,
  market_key TEXT,
  side TEXT,
  line TEXT,
  american TEXT,
  source_updated_at TEXT,
  retrieved_at TEXT,
  derivation TEXT NOT NULL CHECK (derivation = 'OBSERVED')
);
CREATE TABLE IF NOT EXISTS game_state (
  nba_game_id TEXT PRIMARY KEY,
  period TEXT,
  clock TEXT,
  status TEXT,
  observed_at TEXT,
  source TEXT,
  season_phase TEXT
);
CREATE TABLE IF NOT EXISTS collection_plan (
  event_id TEXT NOT NULL,
  moment TEXT NOT NULL,
  nba_game_id TEXT,
  season_phase TEXT,
  status TEXT NOT NULL,
  PRIMARY KEY (event_id, moment)
);
CREATE TABLE IF NOT EXISTS collector_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS book_quotes (
  id INTEGER PRIMARY KEY,
  recorded_at TEXT NOT NULL,
  bookmaker TEXT NOT NULL,
  provider_event_id TEXT NOT NULL,
  nba_game_id TEXT,
  season_phase TEXT,
  period TEXT NOT NULL,
  market_family TEXT NOT NULL,
  side TEXT NOT NULL,
  line TEXT,
  american TEXT,
  decimal_odds TEXT,
  implied TEXT,
  fractional TEXT,
  status TEXT NOT NULL,
  event_status TEXT,
  source_url TEXT,
  source_updated_at TEXT,
  retrieved_at TEXT NOT NULL,
  start_utc TEXT,
  home_team TEXT,
  away_team TEXT,
  body TEXT NOT NULL
);
"""


def utc_stamp(moment: datetime) -> str:
    from datetime import timezone

    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            self._migrate(conn)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _migrate(self, conn: sqlite3.Connection) -> None:
        columns = {str(row["name"]) for row in conn.execute("PRAGMA table_info(book_quotes)")}
        additions = {
            "market_name": "TEXT",
            "participant": "TEXT",
            "market_id": "TEXT",
            "outcome_id": "TEXT",
            "wager_cutoff": "TEXT",
            "nba_start_utc": "TEXT",
            "observed_at": "TEXT",
            "last_seen_at": "TEXT",
        }
        for name, column_type in additions.items():
            if name not in columns:
                conn.execute(f"ALTER TABLE book_quotes ADD COLUMN {name} {column_type}")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS event_coverage (
              id INTEGER PRIMARY KEY,
              recorded_at TEXT NOT NULL,
              bookmaker TEXT NOT NULL,
              provider_event_id TEXT NOT NULL,
              source_url TEXT,
              groups_discovered TEXT NOT NULL,
              groups_fetched TEXT NOT NULL,
              markets_parsed INTEGER NOT NULL,
              unmapped_count INTEGER NOT NULL,
              failures TEXT,
              status TEXT NOT NULL,
              observed_at TEXT NOT NULL,
              body TEXT NOT NULL
            )
            """
        )

    def release(self, owner: str) -> None:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT owner FROM lease WHERE id = 1").fetchone()
            if row is not None and row["owner"] == owner:
                conn.execute(
                    "UPDATE lease SET expires_at = ? WHERE id = 1",
                    ("1970-01-01T00:00:00Z",),
                )
            conn.execute("COMMIT")

    def try_acquire(self, owner: str, now: datetime, ttl_seconds: int = 20) -> bool:
        now_s = utc_stamp(now)
        expires = utc_stamp(now + timedelta(seconds=ttl_seconds))
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT owner, expires_at FROM lease WHERE id = 1").fetchone()
            if row is not None and row["owner"] != owner and row["expires_at"] > now_s:
                conn.execute("COMMIT")
                return False
            conn.execute(
                """
                INSERT INTO lease (id, owner, expires_at) VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET owner = excluded.owner, expires_at = excluded.expires_at
                """,
                (owner, expires),
            )
            conn.execute("COMMIT")
        return True

    def lease_owner(self) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT owner FROM lease WHERE id = 1").fetchone()
        return None if row is None else str(row["owner"])

    def record_poll(self, retrieved_at: datetime, owner: str, ok: bool, mode: str, detail: str) -> int:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT COALESCE(MAX(poll_id), 0) + 1 AS n FROM polls").fetchone()
            poll_id = int(row["n"])
            conn.execute(
                "INSERT INTO polls (poll_id, retrieved_at, owner, ok, mode, detail) VALUES (?, ?, ?, ?, ?, ?)",
                (poll_id, utc_stamp(retrieved_at), owner, 1 if ok else 0, mode, detail),
            )
            conn.execute("COMMIT")
        return poll_id

    def successful_polls(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM polls WHERE ok = 1").fetchone()
        return int(row["n"])

    def last_success(self) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT retrieved_at FROM polls WHERE ok = 1 ORDER BY poll_id DESC LIMIT 1"
            ).fetchone()
        return None if row is None else str(row["retrieved_at"])

    def quote_state(self) -> dict[str, dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT natural_key, body FROM quote_state").fetchall()
        return {str(row["natural_key"]): json.loads(row["body"]) for row in rows}

    def save_snapshot(self, snapshot_id: str, retrieved_at: datetime, body: dict, states: dict[str, dict]) -> None:
        encoded = json.dumps(body, separators=(",", ":"), sort_keys=True)
        moment = utc_stamp(retrieved_at)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO snapshots (snapshot_id, retrieved_at, body) VALUES (?, ?, ?)",
                (snapshot_id, moment, encoded),
            )
            conn.execute(
                """
                INSERT INTO current_snapshot (id, snapshot_id) VALUES (1, ?)
                ON CONFLICT(id) DO UPDATE SET snapshot_id = excluded.snapshot_id
                """,
                (snapshot_id,),
            )
            for key, state in states.items():
                conn.execute(
                    """
                    INSERT INTO quote_state (
                      natural_key, american, status, source_updated_at, last_quote_change_at, active, body
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(natural_key) DO UPDATE SET
                      american = excluded.american,
                      status = excluded.status,
                      source_updated_at = excluded.source_updated_at,
                      last_quote_change_at = excluded.last_quote_change_at,
                      active = excluded.active,
                      body = excluded.body
                    """,
                    (
                        key,
                        None if state.get("american") is None else str(state.get("american")),
                        state.get("status"),
                        state.get("source_updated_at"),
                        state.get("last_quote_change_at"),
                        1 if state.get("active") else 0,
                        json.dumps(state, separators=(",", ":"), sort_keys=True),
                    ),
                )
            conn.execute("COMMIT")

    def current_body(self) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT snapshots.body AS body
                FROM current_snapshot
                JOIN snapshots ON snapshots.snapshot_id = current_snapshot.snapshot_id
                WHERE current_snapshot.id = 1
                """
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["body"])

    def history(self, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT snapshot_id, retrieved_at FROM snapshots ORDER BY retrieved_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{"snapshot_id": row["snapshot_id"], "retrieved_at": row["retrieved_at"]} for row in rows]

    def save_probe(
        self,
        probed_at: datetime,
        status: str,
        preseason_start: str | None,
        season: str,
        detail: str | None,
        games: list[dict],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO nba_probe (id, probed_at, status, preseason_start, season, detail, games_json)
                VALUES (1, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  probed_at = excluded.probed_at,
                  status = excluded.status,
                  preseason_start = excluded.preseason_start,
                  season = excluded.season,
                  detail = excluded.detail,
                  games_json = excluded.games_json
                """,
                (utc_stamp(probed_at), status, preseason_start, season, detail, json.dumps(games)),
            )

    def probe(self) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT probed_at, status, preseason_start, season, detail, games_json FROM nba_probe WHERE id = 1"
            ).fetchone()
        if row is None:
            return None
        payload = {key: row[key] for key in row.keys()}
        payload["games"] = json.loads(payload.pop("games_json") or "[]")
        return payload

    def meta_get(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM collector_meta WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row["value"])

    def meta_set(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO collector_meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def ledger(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT recorded_at, bucket, purpose, endpoint, credits_last, credits_used,
                       credits_remaining, season_phase
                FROM credit_ledger ORDER BY id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def add_credit(self, row: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO credit_ledger (
                  recorded_at, bucket, purpose, endpoint, credits_last, credits_used,
                  credits_remaining, season_phase
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("recorded_at"),
                    row.get("bucket"),
                    row.get("purpose"),
                    row.get("endpoint"),
                    int(row.get("credits_last") or 0),
                    row.get("credits_used"),
                    row.get("credits_remaining"),
                    row.get("season_phase"),
                ),
            )

    def save_raw(self, row: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO raw_payloads (recorded_at, endpoint, sport_key, event_id, season_phase, body)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    row["recorded_at"],
                    row["endpoint"],
                    row.get("sport_key"),
                    row.get("event_id"),
                    row.get("season_phase"),
                    json.dumps(row["body"]),
                ),
            )

    def raw_payloads(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT recorded_at, endpoint, sport_key, event_id, season_phase, body FROM raw_payloads ORDER BY id"
            ).fetchall()
        payloads = []
        for row in rows:
            item = dict(row)
            item["body"] = json.loads(item["body"])
            payloads.append(item)
        return payloads

    def add_coverage(self, row: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO coverage_cells (
                  recorded_at, sport_key, event_id, nba_game_id, season_phase, bookmaker,
                  market_key, status, line_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["recorded_at"],
                    row.get("sport_key"),
                    row.get("event_id"),
                    row.get("nba_game_id"),
                    row["season_phase"],
                    row["bookmaker"],
                    row["market_key"],
                    row["status"],
                    row.get("line_count"),
                ),
            )

    def coverage_cells(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT recorded_at, sport_key, event_id, nba_game_id, season_phase, bookmaker,
                       market_key, status, line_count
                FROM coverage_cells ORDER BY id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def add_observed_line(self, row: dict) -> None:
        if row.get("derivation") != "OBSERVED":
            raise ValueError("MODELED_NOT_A_QUOTE")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO observed_lines (
                  recorded_at, event_id, nba_game_id, season_phase, bookmaker, market_key,
                  side, line, american, source_updated_at, retrieved_at, derivation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["recorded_at"],
                    row.get("event_id"),
                    row.get("nba_game_id"),
                    row.get("season_phase"),
                    row.get("bookmaker"),
                    row.get("market_key"),
                    row.get("side"),
                    None if row.get("line") is None else str(row.get("line")),
                    None if row.get("american") is None else str(row.get("american")),
                    row.get("source_updated_at"),
                    row.get("retrieved_at"),
                    "OBSERVED",
                ),
            )

    def latest_book_quote(self, row: dict) -> dict | None:
        """Latest stored outcome for this market identity. Legacy rows have no market name."""
        market_name = "" if row.get("market_name") is None else str(row.get("market_name"))
        participant = "" if row.get("participant") is None else str(row.get("participant"))
        line = "" if row.get("line") is None else str(row.get("line"))
        with self._connect() as conn:
            found = conn.execute(
                """
                SELECT id, line, american, status, market_name FROM book_quotes
                WHERE bookmaker = ? AND provider_event_id = ? AND period = ? AND market_family = ? AND side = ?
                  AND COALESCE(market_name, '') = ? AND COALESCE(participant, '') = ? AND COALESCE(line, '') = ?
                ORDER BY id DESC LIMIT 1
                """,
                (
                    str(row["bookmaker"]),
                    str(row["provider_event_id"]),
                    str(row["period"]),
                    str(row["market_family"]),
                    str(row["side"]),
                    market_name,
                    participant,
                    line,
                ),
            ).fetchone()
            if found is None and participant == "" and market_name:
                found = conn.execute(
                    """
                    SELECT id, line, american, status, market_name FROM book_quotes
                    WHERE bookmaker = ? AND provider_event_id = ? AND period = ? AND market_family = ? AND side = ?
                      AND market_name IS NULL AND COALESCE(participant, '') = '' AND COALESCE(line, '') = ?
                    ORDER BY id DESC LIMIT 1
                    """,
                    (
                        str(row["bookmaker"]),
                        str(row["provider_event_id"]),
                        str(row["period"]),
                        str(row["market_family"]),
                        str(row["side"]),
                        line,
                    ),
                ).fetchone()
        return None if found is None else dict(found)

    def latest_event_quotes(self, bookmaker: str, event_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, period, market_family, market_name, participant, side, line, american, status
                FROM book_quotes
                WHERE id IN (
                  SELECT MAX(id) FROM book_quotes
                  WHERE bookmaker = ? AND provider_event_id = ?
                  GROUP BY period, market_family, COALESCE(market_name, ''), COALESCE(participant, ''), side, COALESCE(line, '')
                )
                """,
                (bookmaker, event_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_book_quote(self, row: dict) -> bool:
        """Append a quote when the price or status changed. An identical observation only updates last_seen_at."""
        previous = self.latest_book_quote(row)
        line = None if row.get("line") is None else str(row.get("line"))
        american = None if row.get("american") is None else str(row.get("american"))
        status = str(row["status"])
        seen = row.get("last_seen_at") or row.get("observed_at") or row["retrieved_at"]
        if previous is not None and previous.get("line") == line and previous.get("american") == american and previous.get("status") == status:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE book_quotes SET last_seen_at = ?, body = ? WHERE id = ?",
                    (
                        seen,
                        json.dumps(row.get("body") or {}, separators=(",", ":"), sort_keys=True),
                        previous["id"],
                    ),
                )
            return False
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO book_quotes (
                  recorded_at, bookmaker, provider_event_id, nba_game_id, season_phase, period,
                  market_family, market_name, participant, market_id, outcome_id, side, line,
                  american, decimal_odds, implied, fractional, status, event_status, source_url,
                  source_updated_at, retrieved_at, observed_at, last_seen_at, start_utc,
                  wager_cutoff, nba_start_utc, home_team, away_team, body
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["recorded_at"],
                    row["bookmaker"],
                    row["provider_event_id"],
                    row.get("nba_game_id"),
                    row.get("season_phase"),
                    row["period"],
                    row["market_family"],
                    row.get("market_name"),
                    row.get("participant"),
                    row.get("market_id"),
                    row.get("outcome_id"),
                    row["side"],
                    line,
                    american,
                    row.get("decimal_odds"),
                    row.get("implied"),
                    row.get("fractional"),
                    status,
                    row.get("event_status"),
                    row.get("source_url"),
                    row.get("source_updated_at"),
                    row["retrieved_at"],
                    row.get("observed_at") or row["retrieved_at"],
                    seen,
                    row.get("start_utc"),
                    row.get("wager_cutoff"),
                    row.get("nba_start_utc"),
                    row.get("home_team"),
                    row.get("away_team"),
                    json.dumps(row.get("body") or {}, separators=(",", ":"), sort_keys=True),
                ),
            )
        return True

    def save_event_coverage(self, row: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO event_coverage (
                  recorded_at, bookmaker, provider_event_id, source_url, groups_discovered,
                  groups_fetched, markets_parsed, unmapped_count, failures, status, observed_at, body
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["recorded_at"],
                    row["bookmaker"],
                    row["provider_event_id"],
                    row.get("source_url"),
                    json.dumps(row.get("groups_discovered") or []),
                    json.dumps(row.get("groups_fetched") or []),
                    int(row.get("markets_parsed") or 0),
                    int(row.get("unmapped_count") or 0),
                    json.dumps(row.get("failures") or []),
                    row["status"],
                    row["observed_at"],
                    json.dumps(row.get("body") or {}, separators=(",", ":"), sort_keys=True),
                ),
            )

    def book_quotes(self, bookmaker: str | None = None) -> list[dict]:
        with self._connect() as conn:
            if bookmaker is None:
                rows = conn.execute("SELECT * FROM book_quotes ORDER BY id").fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM book_quotes WHERE bookmaker = ? ORDER BY id",
                    (bookmaker,),
                ).fetchall()
        return [dict(row) for row in rows]

    def observed_lines(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT event_id, nba_game_id, season_phase, bookmaker, market_key, side, line,
                       american, source_updated_at, retrieved_at, derivation
                FROM observed_lines ORDER BY id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def save_plan(self, row: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO collection_plan (event_id, moment, nba_game_id, season_phase, status)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(event_id, moment) DO UPDATE SET
                  nba_game_id = excluded.nba_game_id,
                  season_phase = excluded.season_phase,
                  status = excluded.status
                """,
                (row["event_id"], row["moment"], row.get("nba_game_id"), row.get("season_phase"), row["status"]),
            )

    def plans(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT event_id, moment, nba_game_id, season_phase, status FROM collection_plan ORDER BY event_id, moment"
            ).fetchall()
        return [dict(row) for row in rows]

    def save_game_state(self, row: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO game_state (nba_game_id, period, clock, status, observed_at, source, season_phase)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(nba_game_id) DO UPDATE SET
                  period = excluded.period,
                  clock = excluded.clock,
                  status = excluded.status,
                  observed_at = excluded.observed_at,
                  source = excluded.source,
                  season_phase = excluded.season_phase
                """,
                (
                    row["nba_game_id"],
                    None if row.get("period") is None else str(row.get("period")),
                    None if row.get("clock") is None else str(row.get("clock")),
                    row.get("status"),
                    row.get("observed_at"),
                    row.get("source"),
                    row.get("season_phase"),
                ),
            )

    def game_states(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT nba_game_id, period, clock, status, observed_at, source, season_phase FROM game_state"
            ).fetchall()
        return [dict(row) for row in rows]
