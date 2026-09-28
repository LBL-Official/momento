"""HTTP handlers for the 78/67 Austin desk. No submit."""

from __future__ import annotations

from typing import Any

from roller.austin.errors import AustinError
from roller.austin.games import catalog_payload, get_game
from roller.austin_first78.config import CFG, EV_DEFINITION
from roller.austin_first78.paths import (
    audit_path,
    hedge_path,
    integrity_audit_path,
    sizing_path,
    summary_path,
    walkforward_path,
)
from roller.austin_first78.query import form_fields, query_from_body, query_match
from roller.austin_first78.reconstruct import build_historical_query_state, list_moments, replay_trade
from roller.austin_first78.store import artifacts_present, load_json, load_pca_model, load_snapshots, load_trades_frame


def handle_health() -> dict[str, Any]:
    return {
        "ok": artifacts_present(),
        "product": "Austin",
        "rule": "FIRST78_67",
        "live_execution": False,
        "submits": False,
        "live_feed": "UNAVAILABLE",
        "data_mode": CFG.data_mode,
        "model_universe": CFG.dataset_version,
        "model_version": CFG.model_version,
        "artifacts": artifacts_present(),
        "note": "78/67 conditional EV query desk. Candle path is not a fill.",
    }


def handle_dataset() -> dict[str, Any]:
    summary = load_json(summary_path())
    return {
        "status": "OBSERVED",
        "sport": "NBA",
        "market": "CHOOSIN TEXAS",
        "period": "2Q + 3Q",
        "rule": "FIRST78_67",
        "data_mode": CFG.data_mode,
        "live_feed": "UNAVAILABLE",
        "live_execution": False,
        "model_universe": CFG.dataset_version,
        "model_version": CFG.model_version,
        "coverage": summary.get("coverage"),
        "dataset_version": summary.get("dataset_version"),
        "built_at": summary.get("built_at"),
        "note": summary.get("note"),
    }


def handle_pca() -> dict[str, Any]:
    summary = load_json(summary_path())
    return {"status": "OBSERVED", "pca": summary.get("pca"), "points": summary.get("pca_points"), "note": "Color is diagnostic."}


def handle_validation() -> dict[str, Any]:
    return {"status": "OBSERVED", **(load_json(walkforward_path()) or {})}


def handle_hedge() -> dict[str, Any]:
    return {"status": "OBSERVED", **(load_json(hedge_path()) or {})}


def handle_sizing() -> dict[str, Any]:
    return {"status": "OBSERVED", **(load_json(sizing_path()) or {})}


def handle_calibration() -> dict[str, Any]:
    sizing = load_json(sizing_path()) or {}
    return {
        "status": "OBSERVED",
        "calibration": sizing.get("calibration"),
        "bands": sizing.get("bands"),
        "bankroll": sizing.get("bankroll"),
        "note": "3/4/5% of $20,000 at a 78¢ entry. ENTRY_SIZING_REFERENCE. No BUY/SKIP.",
    }


def handle_audit() -> dict[str, Any]:
    return {
        "status": "OBSERVED",
        **(load_json(audit_path()) or {}),
        "integrity": load_json(integrity_audit_path(), required=False) or {},
    }


def handle_lab() -> dict[str, Any]:
    summary = load_json(summary_path()) or {}
    return {
        "status": "OBSERVED",
        "correlations": summary.get("correlations"),
        "buckets": summary.get("buckets"),
        "interactions": summary.get("interactions"),
        "ablation": summary.get("ablation"),
        "model_compare": summary.get("model_compare"),
        "fees": summary.get("fees"),
        "note": "CORRELATION ≠ CAUSATION",
    }


def handle_example_query() -> dict[str, Any]:
    trades = load_trades_frame()
    if trades.empty:
        raise AustinError("DATA_REQUIRED", "no trades")
    trade = trades.iloc[0]
    return {
        "status": "OBSERVED",
        "trade_id": trade["trade_id"],
        "side": trade["entry_side"],
        "query_mode": "POST_78",
        "entry_price_cents": int(trade["entry_price_cents"]),
        "current_price_cents": int(trade["entry_price_cents"]),
        "entry_quarter": int(trade["quarter"]) if trade["quarter"] == trade["quarter"] else None,
        "current_quarter": int(trade["quarter"]) if trade["quarter"] == trade["quarter"] else None,
        "note": "Entry fixture for the 78/67 fit. Not live.",
        "fixtures": {},
        "submits": False,
        "live_feed": "UNAVAILABLE",
    }


def handle_games() -> dict[str, Any]:
    payload = catalog_payload()
    tickers = set(load_trades_frame()["ticker"].astype(str))
    games = []
    n_in = 0
    for row in payload.get("games") or []:
        flagged = str(row.get("home_ticker") or "") in tickers or str(row.get("away_ticker") or "") in tickers
        item = dict(row)
        item["in_austin_78"] = flagged
        if flagged:
            n_in += 1
        games.append(item)
    payload["games"] = games
    payload["model_universe"] = CFG.dataset_version
    payload["model_version"] = CFG.model_version
    payload["model_n"] = int(load_json(summary_path()).get("coverage", {}).get("n_trades") or 0)
    payload["n_in_austin_78"] = n_in
    payload["rule"] = "FIRST78_67"
    payload["note"] = "Training N is the observed NBA 2Q/3Q 78¢-cross count. Query games are warehouse NBA games."
    return payload


def handle_game_moments(game_id: str, side: str = "home") -> dict[str, Any]:
    get_game(game_id)
    return list_moments(game_id, side=side)


def _run_query(raw, *, k: int | None = None) -> dict[str, Any]:
    sizing = load_json(sizing_path(), required=False) or {}
    result = query_match(
        raw,
        snapshots=load_snapshots(),
        model=load_pca_model(),
        calibration=sizing.get("calibration") or {},
        k=k,
    )
    return {"status": result.get("status") or "OBSERVED", **result}


def handle_query(body: dict[str, Any]) -> dict[str, Any]:
    return _run_query(query_from_body(body), k=body.get("k"))


def handle_query_historical(body: dict[str, Any]) -> dict[str, Any]:
    game_id = str(body.get("internal_game_id") or body.get("game_id") or body.get("ticker") or "").strip()
    if not game_id:
        raise AustinError("QUERY_REJECTED", "missing internal_game_id|game_id|ticker")
    recon = build_historical_query_state(
        game_id=game_id,
        side=str(body.get("side") or "home"),
        timestamp_utc=body.get("timestamp_utc"),
        quarter=body.get("quarter") if body.get("quarter") is not None else body.get("current_quarter"),
        seconds_remaining=body.get("seconds_remaining")
        if body.get("seconds_remaining") is not None
        else body.get("current_seconds_remaining"),
        query_mode=body.get("query_mode"),
    )
    result = _run_query(recon["raw"])
    result["entry_source"] = recon.get("entry_source") or result.get("entry_source")
    result["reconstructed"] = {k: v for k, v in recon.items() if k != "raw"}
    result["form"] = form_fields(recon["raw"])
    result["ev_definition"] = EV_DEFINITION
    return result


def handle_replay(trade_id: str) -> dict[str, Any]:
    frame = load_trades_frame()
    hit = frame[frame["trade_id"].astype(str) == str(trade_id)]
    if hit.empty:
        raise AustinError("DATA_REQUIRED", f"unknown trade_id {trade_id}")
    return {"status": "OBSERVED", **replay_trade(hit.iloc[0].to_dict())}
