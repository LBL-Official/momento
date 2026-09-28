"""Background NBA refresh. The page reads the stored snapshot."""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from roller.ontologic_y.service import SCOREBOARD_SECONDS, Service, open_default

_STARTED = False
_GUARD = threading.Lock()


def ensure_started() -> Service:
    global _STARTED
    service = open_default()
    with _GUARD:
        if _STARTED:
            return service
        _STARTED = True

    def loop() -> None:
        logs_due = True
        while True:
            try:
                service.refresh(datetime.now(timezone.utc), logs=logs_due)
            except Exception:
                pass
            logs_due = False
            threading.Event().wait(SCOREBOARD_SECONDS)

    threading.Thread(target=loop, name="ontologic-y", daemon=True).start()
    return service


def get_service() -> Service:
    return ensure_started()


def handle_health() -> dict:
    board = get_service().board()
    keys = (
        "snapshot_id",
        "retrieved_at",
        "live_execution",
        "schedule_status",
        "log_status",
        "last_poll_at",
        "last_successful_retrieval_at",
        "source_updated_at",
        "source_time",
        "last_state_change_at",
        "feature_snapshot_at",
        "prediction_generated_at",
        "effective_cadence_seconds",
        "five_second_source",
        "cadence_reason",
        "earliest_preseason_game_returned",
        "schedule_completeness",
    )
    body = {key: board.get(key) for key in keys}
    body["model_status"] = (board.get("model") or {}).get("model_status")
    body["live_execution"] = False
    return body


def handle_board(date: str | None = None, view: str | None = None, support: str | None = None) -> dict:
    board = dict(get_service().board())
    games = list(board.get("games") or [])
    if date:
        games = [game for game in games if str(game.get("start_utc") or "").startswith(date)]
    if view in {"live", "upcoming", "completed"}:
        games = [game for game in games if game.get("status") == view]
    if support == "supported":
        games = [game for game in games if game.get("model_status") == "SUPPORTED"]
    elif support == "unavailable":
        games = [game for game in games if game.get("model_status") != "SUPPORTED"]
    board["games"] = games
    board["live_execution"] = False
    return board


def handle_game(game_id: str) -> dict:
    service = get_service()
    game = service.game(game_id)
    if game is None:
        return {"status": "SOURCE_UNAVAILABLE", "game": None, "live_execution": False}
    return {
        "status": "OK",
        "live_execution": False,
        "game": game,
        "model": service.model,
        "markets": service.board().get("markets"),
        "prediction_generated_at": None,
    }
