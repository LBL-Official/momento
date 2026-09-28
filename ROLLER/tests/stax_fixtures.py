"""Shared STAX test sources. No warehouse scan."""

from __future__ import annotations

from typing import Any


def source(
    *,
    name: str = "FIRST80 Q3",
    sports: tuple[str, ...] = ("basketball",),
    leagues: tuple[str, ...] = ("NBA",),
    seasons: tuple[str, ...] = ("2025-26",),
    date_from: str | None = "2025-10-10",
    date_to: str | None = "2026-06-13",
    question_hash: str = "qh-a",
    games: list[str] | None = None,
    n: int | None = None,
) -> dict[str, Any]:
    universe = {
        "sports": list(sports),
        "leagues": list(leagues),
        "seasons": list(seasons),
        "markets": ["kalshi"],
        "market_data": ["candles"],
        "date_from": date_from,
        "date_to": date_to,
    }
    question = {
        "universe": universe,
        "entry_conditions": [],
        "path_conditions": [],
        "terminal": "BOTH",
    }
    return {
        "name": name,
        "id": f"save-{name}",
        "save_id": f"save-{name}",
        "question": question,
        "draft": {"universe": universe},
        "hashes": {"question_hash": question_hash},
        "universe": universe,
    }


def envelope(
    *,
    games: list[str],
    dataset_version: str = "ds-1",
    question_hash: str = "qh-a",
    status: str = "COMPLETE",
) -> dict[str, Any]:
    trades = [{"internal_game_id": g, "ticker": f"T-{g}"} for g in games]
    return {
        "research_object_id": None,
        "execution_status": status,
        "summary": {"population_n": len(trades)},
        "population": {"count": len(trades), "trades": trades, "rows": trades[:2], "rows_truncated": True},
        "hashes": {"question_hash": question_hash},
        "dataset_version": dataset_version,
        "compile": {"question": source()["question"]},
        "measurements": [
            {"name": "path_rate", "value": 0.5},
            {"name": "terminal_rate", "value": 0.4},
        ],
        "analysis": {"observed_path_ev": {"value": 0.02}},
    }


def fake_execute(dataset: str = "ds-1", games: dict[str, list[str]] | None = None, fail: set[str] | None = None):
    games = games or {}
    fail = fail or set()
    calls: list[dict[str, Any]] = []

    def execute_question(payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(payload)
        question = payload.get("question") or {}
        uni = (question.get("universe") or payload.get("draft", {}).get("universe") or {})
        qh = (payload.get("question") or {}).get("terminal", "BOTH")
        name = None
        # identify by date or league for failure injection
        key = str(uni.get("leagues") or uni.get("date_from") or "x")
        if any(x in fail for x in (key, str(uni.get("date_from")), "fail")):
            return envelope(games=[], dataset_version=dataset, status="DATA_REQUIRED")
        g = games.get(str(uni.get("date_from")), ["G1", "G2"])
        env = envelope(games=g, dataset_version=dataset)
        env["compile"] = {"question": {"universe": uni}}
        env["hashes"] = {"question_hash": f"qh-{qh}"}
        return env

    execute_question.calls = calls  # type: ignore[attr-defined]
    return execute_question
