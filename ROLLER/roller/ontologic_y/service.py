"""NBA board, descriptive windows, and an unavailable in-house model."""

from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from roller.ontologic_x.identity import fetch_nba_catalog
from roller.ontologic_y.capability import capability_matrix
from roller.ontologic_y.features import aggregate
from roller.ontologic_y.logs import fetch_logs
from roller.ontologic_y.model import assess_xib
from roller.ontologic_y.store import Store
from roller.ontologic_y.windows import descriptive_windows

REPO = Path(__file__).resolve().parents[3]
DEFAULT_DB = REPO / "research/ontologic_y/v1/ontologic_y.sqlite"
SCOREBOARD_SECONDS = 30
LOG_REFRESH = timedelta(minutes=30)


class Service:
    def __init__(self, store: Store, owner: str | None = None):
        self.store = store
        self.owner = owner or f"ontologic-y-{os.getpid()}"
        self._guard = threading.Lock()
        self.model = assess_xib()

    def refresh(self, now: datetime | None = None, *, logs: bool = False) -> dict:
        now = now or datetime.now(timezone.utc)
        if not self._guard.acquire(blocking=False):
            current = self.store.current()
            return current or self._empty("IN_PROCESS_BUSY", now)
        try:
            if not self.store.try_lease(self.owner, now):
                current = self.store.current()
                return current or self._empty("LEASE_HELD", now)
            try:
                failures = self.store.recent_failures(now)
                if failures >= 3:
                    self.store.record_poll(now, self.owner, False, "BACKOFF", "bounded")
                    current = self.store.current()
                    return current or self._empty("BACKOFF", now)
                catalog = fetch_nba_catalog(now)
                log_body = self.store.logs()
                if _logs_due(log_body, now, force=logs and log_body is None):
                    fetched = fetch_logs(now)
                    self.store.save_logs(now, fetched)
                    log_body = self.store.logs()
                body = self._snapshot(catalog, log_body, now)
                self.store.save_snapshot(body["snapshot_id"], now, body)
                self.store.record_poll(now, self.owner, catalog.get("status") == "OK", "NBA", catalog.get("status", ""))
                return body
            finally:
                self.store.release(self.owner)
        finally:
            self._guard.release()

    def board(self) -> dict:
        current = self.store.current()
        return current or self._empty("SOURCE_UNAVAILABLE", datetime.now(timezone.utc))

    def game(self, game_id: str) -> dict | None:
        current = self.board()
        for row in current.get("games") or []:
            if row.get("nba_game_id") == game_id or row.get("internal_game_id") == game_id:
                return row
        return None

    def _snapshot(self, catalog: dict, logs: dict | None, now: datetime) -> dict:
        previous = self.store.current() or {}
        rows = []
        changed = False
        history = (logs or {}).get("rows") or []
        for game in catalog.get("games") or []:
            start = _parse(game.get("start_utc"))
            if start is None:
                continue
            row = _game_row(game, history, now)
            prior = _find(previous.get("games") or [], row["nba_game_id"])
            if prior and (
                prior.get("home_score") != row["home_score"]
                or prior.get("period") != row["period"]
                or prior.get("clock") != row["clock"]
            ):
                changed = True
            rows.append(row)
        rows.sort(key=lambda item: (0 if item["status"] == "live" else 1, item.get("start_utc") or ""))
        return {
            "snapshot_id": "oy-" + uuid.uuid4().hex[:12],
            "retrieved_at": now.isoformat(),
            "live_execution": False,
            "product": "Ontologic Y",
            "source": "IN_HOUSE_MODEL",
            "vig_removal": "NOT_APPLICABLE",
            "model": self.model,
            "markets": capability_matrix(),
            "schedule_status": catalog.get("status"),
            "earliest_preseason_game_returned": catalog.get("preseason_start"),
            "schedule_completeness": "UNVERIFIED",
            "log_status": (logs or {}).get("status", "SOURCE_UNAVAILABLE"),
            "feature_snapshot_at": (logs or {}).get("retrieved_at"),
            "prediction_generated_at": None,
            "last_poll_at": now.isoformat(),
            "last_successful_retrieval_at": now.isoformat() if catalog.get("status") == "OK" else previous.get("last_successful_retrieval_at"),
            "source_updated_at": None,
            "source_time": "SOURCE_TIME_UNAVAILABLE",
            "last_state_change_at": now.isoformat() if changed else previous.get("last_state_change_at"),
            "effective_cadence_seconds": SCOREBOARD_SECONDS,
            "five_second_source": "NOT_SUSTAINED",
            "cadence_reason": "NBA stats endpoints are not a five-second feed. The client reads this snapshot every five seconds.",
            "games": rows,
        }

    def _empty(self, reason: str, now: datetime) -> dict:
        return {
            "snapshot_id": None,
            "retrieved_at": now.isoformat(),
            "live_execution": False,
            "product": "Ontologic Y",
            "model": self.model,
            "markets": capability_matrix(),
            "schedule_status": reason,
            "earliest_preseason_game_returned": None,
            "schedule_completeness": "UNVERIFIED",
            "games": [],
            "prediction_generated_at": None,
            "source_updated_at": None,
            "source_time": "SOURCE_TIME_UNAVAILABLE",
            "five_second_source": "NOT_SUSTAINED",
        }


def _game_row(game: dict, history: list[dict], now: datetime) -> dict:
    home_history = [row for row in history if str(row.get("team_id")) == str(game.get("home_team_id"))]
    away_history = [row for row in history if str(row.get("team_id")) == str(game.get("away_team_id"))]
    home_windows = descriptive_windows(home_history, game.get("start_utc"), game.get("nba_game_id"))
    away_windows = descriptive_windows(away_history, game.get("start_utc"), game.get("nba_game_id"))
    return {
        "nba_game_id": game.get("nba_game_id"),
        "internal_game_id": game.get("internal_game_id"),
        "identity_status": game.get("identity_status") or "UNMATCHED",
        "away": game.get("away_tricode") or game.get("away"),
        "home": game.get("home_tricode") or game.get("home"),
        "away_name": game.get("away_full_name"),
        "home_name": game.get("home_full_name"),
        "away_team_id": game.get("away_team_id"),
        "home_team_id": game.get("home_team_id"),
        "start_utc": game.get("start_utc"),
        "status": game.get("status"),
        "season_type": game.get("season_type"),
        "period": None if game.get("status") == "upcoming" else game.get("period"),
        "clock": None if game.get("status") == "upcoming" else game.get("clock"),
        "away_score": None if game.get("status") == "upcoming" else game.get("away_score"),
        "home_score": None if game.get("status") == "upcoming" else game.get("home_score"),
        "score_role": "DISPLAY_ONLY",
        "basis": None,
        "model_status": "MODEL_INCOMPATIBLE",
        "moneyline": "MARKET_MODEL_UNAVAILABLE",
        "spread": "MARKET_MODEL_UNAVAILABLE",
        "total": "MARKET_MODEL_UNAVAILABLE",
        "quarters": "MARKET_MODEL_UNAVAILABLE",
        "home_windows": _public_windows(home_windows),
        "away_windows": _public_windows(away_windows),
        "home_features": _window_features(home_windows),
        "away_features": _window_features(away_windows),
        "prediction_generated_at": None,
        "feature_built_at": now.isoformat(),
    }


def _public_windows(body: dict) -> dict:
    windows = {}
    for season_type, window in (body.get("windows") or {}).items():
        windows[season_type] = {
            "label": window["label"],
            "count": window["count"],
            "requested": window["requested"],
            "game_ids": window["game_ids"],
            "dates": [row.get("start_utc") for row in window.get("games") or []],
            "long_gap": window["long_gap"],
            "cross_season": window["cross_season"],
            "model_input": False,
        }
    return {"label": "DESCRIPTIVE_ONLY", "windows": windows}


def _window_features(body: dict) -> dict:
    features = {}
    for season_type, window in (body.get("windows") or {}).items():
        features[season_type] = aggregate(window.get("games") or [])
    return features


def _logs_due(body: dict | None, now: datetime, force: bool) -> bool:
    if body is None or force:
        return True
    retrieved = _parse(body.get("retrieved_at"))
    if retrieved is None:
        return True
    wait = LOG_REFRESH if body.get("status") == "OK" else timedelta(minutes=5)
    return now - retrieved >= wait


def _find(rows: list[dict], game_id: str | None) -> dict | None:
    for row in rows:
        if row.get("nba_game_id") == game_id:
            return row
    return None


def _parse(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


_SERVICE: Service | None = None
_LOCK = threading.Lock()


def open_default() -> Service:
    global _SERVICE
    with _LOCK:
        if _SERVICE is None:
            _SERVICE = Service(Store(DEFAULT_DB))
        return _SERVICE
