"""HTTP handlers for Austin. Mounted on the ROLLER research API. No submit."""

from __future__ import annotations

from typing import Any

from roller.austin.config import DEFAULT
from roller.austin.errors import AustinError
from roller.austin.fort_worth import persist_contract, policy_payload
from roller.austin.games import catalog_payload, get_game
from roller.austin.instances import load_trades
from roller.austin.integrity import example_fixtures
from roller.austin.paths import (
    audit_path,
    calibration_path,
    hedge_path,
    integrity_audit_path,
    sizing_path,
    summary_path,
    walkforward_path,
)
from roller.austin.query import form_fields, query_from_body, query_match
from roller.austin.reconstruct import build_historical_query_state, list_moments
from roller.austin.replay import replay_trade
from roller.austin.bars_join import load_paths
from roller.austin.pbp_join import load_pbp
from roller.austin.store import (
    artifacts_present,
    load_json,
    load_pca_model,
    load_snapshots,
)


def _calibration() -> dict[str, Any]:
    sizing = load_json(sizing_path(), required=False) or {}
    extra = load_json(calibration_path(), required=False) or {}
    cal = extra or sizing.get("calibration") or {}
    return cal


def handle_health() -> dict[str, Any]:
    return {
        "ok": True,
        "product": "Austin",
        "live_execution": False,
        "submits": False,
        "live_feed": DEFAULT.live_feed,
        "data_mode": DEFAULT.data_mode,
        "model_universe": DEFAULT.dataset_version,
        "query_universe": "nba_warehouse_games",
        "artifacts": artifacts_present(),
        "note": "Conditional EV query desk. Candle path != fill. Execution disabled.",
    }


def handle_dataset() -> dict[str, Any]:
    summary = load_json(summary_path())
    return {
        "status": "OBSERVED",
        "sport": "NBA",
        "market": "CHOOSIN TEXAS",
        "period": "2Q + 3Q",
        "data_mode": DEFAULT.data_mode,
        "live_feed": DEFAULT.live_feed,
        "live_execution": False,
        "model_universe": DEFAULT.dataset_version,
        "query_universe": "nba_warehouse_games",
        "coverage": summary.get("coverage"),
        "model_version": summary.get("model_version"),
        "dataset_version": summary.get("dataset_version"),
        "built_at": summary.get("built_at"),
        "note": summary.get("note"),
    }


def handle_pca() -> dict[str, Any]:
    summary = load_json(summary_path())
    return {
        "status": "OBSERVED",
        "pca": summary.get("pca"),
        "points": summary.get("pca_points"),
        "note": "Color is DISPLAY / DIAGNOSTIC, not a signal.",
    }


def handle_validation() -> dict[str, Any]:
    return {"status": "OBSERVED", **load_json(walkforward_path())}


def handle_hedge() -> dict[str, Any]:
    return {"status": "OBSERVED", **load_json(hedge_path())}


def handle_sizing() -> dict[str, Any]:
    return {"status": "OBSERVED", **load_json(sizing_path())}


def handle_calibration() -> dict[str, Any]:
    sizing = load_json(sizing_path())
    return {
        "status": "OBSERVED",
        "calibration": sizing.get("calibration"),
        "bands": sizing.get("bands"),
        "bankroll": sizing.get("bankroll"),
        "note": "Entry-allocation research on the 604 walk-forward. POST-80 band is ENTRY_SIZING_REFERENCE.",
    }


def handle_audit() -> dict[str, Any]:
    payload = load_json(audit_path())
    integrity = load_json(integrity_audit_path(), required=False) or {}
    return {"status": "OBSERVED", **payload, "integrity": integrity}


def handle_lab() -> dict[str, Any]:
    summary = load_json(summary_path())
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


def _run_query(raw, *, persist: bool = True, k: int | None = None) -> dict[str, Any]:
    snaps = load_snapshots()
    model = load_pca_model()
    result = query_match(raw, snapshots=snaps, model=model, calibration=_calibration(), k=k)
    if persist and result.get("match"):
        persist_contract(result)
    return {"status": result.get("status") or "OBSERVED", **result}


def handle_query(body: dict[str, Any]) -> dict[str, Any]:
    raw = query_from_body(body)
    return _run_query(raw, k=body.get("k"))


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
    result = _run_query(recon["raw"], persist=True)
    result["reconstructed"] = {k: v for k, v in recon.items() if k != "raw"}
    result["form"] = form_fields(recon["raw"])
    return result


def handle_games() -> dict[str, Any]:
    return catalog_payload()


def handle_game_moments(game_id: str, side: str = "home") -> dict[str, Any]:
    get_game(game_id)
    return list_moments(game_id, side=side)


def handle_replay(trade_id: str) -> dict[str, Any]:
    trades = load_trades()
    trade = next((row for row in trades if row["trade_id"] == trade_id), None)
    if trade is None:
        raise AustinError("DATA_REQUIRED", f"unknown trade_id {trade_id}")
    paths = load_paths([trade])
    gid = paths["internal_game_id"].get(trade["ticker"])
    pbp = load_pbp({gid} if gid else set())
    opp = paths["opponent_ticker"].get(trade["ticker"])
    payload = replay_trade(
        trade,
        favorite_bars=paths["favorite"].get(trade["ticker"], []),
        opponent_bars=paths["favorite"].get(opp, []) if opp else [],
        pbp_events=pbp.get(gid, []) if gid else [],
    )
    return {"status": "OBSERVED", **payload}


def handle_fort_worth() -> dict[str, Any]:
    from roller.austin.paths import contract_path

    contract = load_json(contract_path(), required=False)
    return {
        "status": "OBSERVED",
        "live_execution": False,
        "submits": False,
        "policy": policy_payload(),
        "last_contract": contract or None,
        "note": "Austin does not call Fort Worth. Fort Worth does not submit.",
    }


def handle_example_query() -> dict[str, Any]:
    snaps = load_snapshots()
    fixtures = example_fixtures(snaps)
    post = fixtures.get("post80_42") or fixtures.get("entry")
    if post:
        return {
            "status": "OBSERVED",
            "default": "post80_42" if fixtures.get("post80_42") else "entry",
            **post,
            "fixtures": fixtures,
            "submits": False,
            "live_feed": DEFAULT.live_feed,
            "note": post.get("note") or "Historical fixture. Not live.",
        }
    trades = load_trades()
    if not trades:
        raise AustinError("DATA_REQUIRED", "no trades")
    trade = trades[0]
    return {
        "status": "OBSERVED",
        "trade_id": trade["trade_id"],
        "side": trade["entry_side"],
        "query_mode": "POST_80",
        "entry_price_cents": trade["entry_price_cents"],
        "current_price_cents": 42,
        "home_score_entry": trade.get("home_score_entry"),
        "away_score_entry": trade.get("away_score_entry"),
        "home_score_current": trade.get("home_score_entry"),
        "away_score_current": trade.get("away_score_entry"),
        "entry_quarter": trade.get("quarter"),
        "current_quarter": trade.get("quarter"),
        "entry_seconds_remaining": trade.get("entry_seconds_remaining"),
        "current_seconds_remaining": trade.get("entry_seconds_remaining"),
        "note": "Fallback 80→42 form. Prefer reconstructed fixtures after build.",
        "fixtures": {"entry": None, "post80_42": None},
    }


def handle_integrity() -> dict[str, Any]:
    return {"status": "OBSERVED", **(load_json(integrity_audit_path(), required=False) or {})}


def handle_experiments() -> dict[str, Any]:
    from roller.austin.experiments.artifacts import handle_experiments as _handle

    return _handle()


def handle_experiment(experiment_id: str) -> dict[str, Any]:
    from roller.austin.experiments.artifacts import handle_experiment as _handle

    return _handle(experiment_id)
