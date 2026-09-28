"""Austin → DRE live/historical position inference. No experiment phase modules."""

from __future__ import annotations

from typing import Any

from roller.austin.clock import format_clock, parse_utc
from roller.austin.errors import AustinError
from roller.austin.instances import load_trades
from roller.dre.models import AUSTIN_EV_DEFINITION, AUSTIN_EV_FORMULA
from roller.dre.pit import Stamped, clip_path, iso, to_utc


def _json_num(value: object) -> float | int | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    if number == int(number):
        return int(number)
    return float(number)


def get_trade(trade_id: str) -> dict[str, Any] | None:
    wanted = str(trade_id or "").strip()
    if not wanted:
        return None
    for row in load_trades():
        if str(row.get("trade_id")) == wanted:
            return row
    return None


def list_trades() -> list[dict[str, Any]]:
    return list(load_trades())


def last_observed_by_trade() -> dict[str, dict[str, Any]]:
    """Last artifact snapshot price per trade. HISTORICAL last observed, not live."""
    try:
        from roller.austin.store import load_snapshots
    except Exception:  # noqa: BLE001
        return {}
    try:
        snaps = load_snapshots()
    except AustinError:
        return {}
    if snaps is None or getattr(snaps, "empty", True):
        return {}
    if "trade_id" not in snaps.columns or "available_at" not in snaps.columns:
        return {}
    ordered = snaps.sort_values("available_at")
    if "current_price_cents" in ordered.columns:
        priced = ordered[ordered["current_price_cents"].fillna(0) > 0]
        if not priced.empty:
            ordered = priced
    last = ordered.groupby("trade_id", as_index=False).tail(1)
    price_col = "current_price_cents" if "current_price_cents" in last.columns else None
    out: dict[str, dict[str, Any]] = {}
    for rec in last.itertuples(index=False):
        tid = str(getattr(rec, "trade_id", "") or "")
        if not tid:
            continue
        price = None if price_col is None else _json_num(getattr(rec, price_col, None))
        stamp = parse_utc(getattr(rec, "available_at", None))
        out[tid] = {
            "last_observed_price_cents": None if price is None else int(round(float(price))),
            "last_observed_at": iso(stamp),
            "source": "austin_snapshots",
        }
    return out


def get_replay(trade_id: str) -> dict[str, Any]:
    from roller.austin.api import handle_replay

    payload = handle_replay(trade_id)
    path = []
    for row in payload.get("path") or []:
        if not isinstance(row, dict):
            continue
        stamp = to_utc(row.get("t"))
        path.append(
            {
                "t": iso(stamp) or row.get("t"),
                "t_sec": row.get("t_sec"),
                "price_cents": row.get("price_cents"),
                "home_score": row.get("home_score"),
                "away_score": row.get("away_score"),
                "label": row.get("label"),
                "source_timestamp": iso(stamp),
                "source": "austin_replay",
            }
        )
    return {
        "source": "AUSTIN",
        "status": payload.get("status") or "OBSERVED",
        "trade_id": payload.get("trade_id"),
        "ticker": payload.get("ticker"),
        "game_date": payload.get("game_date"),
        "quarter": payload.get("quarter"),
        "entry_price_cents": payload.get("entry_price_cents"),
        "settlement": payload.get("settlement"),
        "csv_t40": payload.get("csv_t40"),
        "candle_path_not_fill": True,
        "path": path,
        "marks": payload.get("marks") or {},
        "hedge_fill_status": payload.get("hedge_fill_status") or "FILL_UNAVAILABLE",
        "live_feed": "UNAVAILABLE",
        "data_mode": "HISTORICAL_QUERY",
    }


def replay_clipped(trade_id: str, as_of) -> dict[str, Any]:
    body = get_replay(trade_id)
    body["path"] = clip_path(as_of, list(body.get("path") or []), time_key="t")
    return body


def query_at(trade: dict[str, Any], as_of) -> dict[str, Any]:
    """Historical Austin query. persist=False so DRE does not write Austin artifacts."""
    from roller.austin.api import _run_query
    from roller.austin.query import form_fields
    from roller.austin.reconstruct import build_historical_query_state

    when = to_utc(as_of)
    if when is None:
        raise AustinError("QUERY_REJECTED", "as_of required for Austin historical query")
    game_id = str(trade.get("ticker") or trade.get("game_id") or "").strip()
    side = str(trade.get("entry_side") or "").strip().lower()
    if side not in {"home", "away"}:
        raise AustinError("QUERY_REJECTED", f"trade side must be home|away, got {side!r}")
    recon = build_historical_query_state(
        game_id=game_id,
        side=side,
        timestamp_utc=iso(when),
    )
    result = _run_query(recon["raw"], persist=False)
    result["reconstructed"] = {k: v for k, v in recon.items() if k != "raw"}
    result["form"] = form_fields(recon["raw"])
    query_ts = to_utc(recon["raw"].availability_timestamp) or when
    result["source"] = "AUSTIN"
    result["live_feed"] = result.get("live_feed") or "UNAVAILABLE"
    result["data_mode"] = result.get("data_mode") or "HISTORICAL_QUERY"
    result["inference_timestamp"] = iso(query_ts)
    result["source_timestamp"] = iso(query_ts)
    result["source_model_id"] = result.get("model_version")
    result["source_model_version"] = result.get("model_version")
    result["conditional_ev_definition"] = AUSTIN_EV_DEFINITION
    result["conditional_ev_formula"] = result.get("ev_formula") or AUSTIN_EV_FORMULA
    result["stamp"] = Stamped(
        field="austin_query",
        value=result.get("status"),
        source="austin",
        source_timestamp=query_ts,
        pit_kind="QUERY",
    )
    return result


def normalize_live_state(query: dict[str, Any] | None, replay_point: dict[str, Any] | None) -> dict[str, Any]:
    if not query:
        return {
            "source": "AUSTIN",
            "availability": "UNAVAILABLE",
            "live_feed": "UNAVAILABLE",
            "data_mode": "HISTORICAL_QUERY",
            "detail": "No current Austin inference",
        }
    cond = query.get("conditional_ev") if isinstance(query.get("conditional_ev"), dict) else {}
    support = query.get("support") if isinstance(query.get("support"), dict) else {}
    change = query.get("state_change") if isinstance(query.get("state_change"), dict) else {}
    derived = query.get("derived") if isinstance(query.get("derived"), dict) else {}
    proximity = query.get("proximity") if isinstance(query.get("proximity"), list) else []
    ranked = sorted(
        [row for row in proximity if isinstance(row, dict) and row.get("abs_delta") is not None],
        key=lambda row: float(row.get("abs_delta") or 0),
        reverse=True,
    )[:5]
    features = query.get("features") if isinstance(query.get("features"), dict) else {}
    point = replay_point or {}
    period = query.get("reconstructed", {})
    raw_form = {}
    recon = query.get("reconstructed") if isinstance(query.get("reconstructed"), dict) else {}
    # reconstructed omits raw; clock/score come from query form if present
    form = query.get("form") if isinstance(query.get("form"), dict) else {}
    if not form:
        form = recon
    home = point.get("home_score")
    away = point.get("away_score")
    lead = None
    if home is not None and away is not None:
        try:
            lead = int(home) - int(away)
        except (TypeError, ValueError):
            lead = None
    return {
        "source": "AUSTIN",
        "availability": "OBSERVED" if query.get("status") in {"OBSERVED", "QUERY_PARTIAL"} else str(query.get("status") or "UNAVAILABLE"),
        "live_feed": "UNAVAILABLE",
        "data_mode": query.get("data_mode") or "HISTORICAL_QUERY",
        "live_execution": False,
        "submits": False,
        "inference_timestamp": query.get("inference_timestamp"),
        "source_timestamp": query.get("source_timestamp"),
        "query_mode": query.get("query_mode"),
        "query_source": query.get("query_source"),
        "game_clock": format_clock(form.get("current_seconds_remaining")),
        "period": form.get("current_quarter"),
        "score": None if home is None or away is None else f"{home}-{away}",
        "home_score": home if home is not None else form.get("home_score_current"),
        "away_score": away if away is not None else form.get("away_score_current"),
        "lead": lead,
        "market_price_cents": point.get("price_cents") or form.get("current_price_cents"),
        "price_from_entry_cents": derived.get("price_travel"),
        "current_feature_vector": {
            "top": ranked,
            "coverage": features.get("feature_coverage") or query.get("feature_coverage"),
            "missing": features.get("missing_features") or query.get("missing_features") or [],
        },
        "deterioration_state": {"value": None, "availability": "UNAVAILABLE"},
        "temporary_distress_evidence": {"value": None, "availability": "UNAVAILABLE"},
        "persistent_distress_evidence": {"value": None, "availability": "UNAVAILABLE"},
        "recovery_evidence": {"value": None, "availability": "UNAVAILABLE"},
        "loss_hazard": {"value": None, "availability": "UNAVAILABLE"},
        "trajectory": {"value": None, "availability": "UNAVAILABLE"},
        "conditional_ev": {
            "label": "AUSTIN CONDITIONAL",
            "estimand": "AUSTIN_CONDITIONAL_EV",
            "definition": AUSTIN_EV_DEFINITION,
            "formula": query.get("conditional_ev_formula") or AUSTIN_EV_FORMULA,
            "label_source": cond.get("label") or "CONDITIONAL EV FROM CURRENT STATE",
            "conditional_ev_cents": cond.get("conditional_ev_cents"),
            "ci_level": cond.get("ci_level"),
            "ci_lower_cents": cond.get("ci_lower_cents"),
            "ci_upper_cents": cond.get("ci_upper_cents"),
            "method": cond.get("method"),
            "note": "Historical nearest-state estimate. Not Choosin Texas population EV.",
        },
        "state_change": {
            "label": "AUSTIN STATE CHANGE",
            "estimand": "AUSTIN_CONDITIONAL_EV_CHANGE",
            "ev_at_entry": change.get("ev_at_entry"),
            "ev_now": change.get("ev_now"),
            "ev_change": change.get("ev_change"),
            "note": change.get("note") or "Research comparison only. Not an exit instruction. Not a CT EV delta.",
        },
        "model_support": support,
        "model_uncertainty": {
            "ci_lower_cents": cond.get("ci_lower_cents"),
            "ci_upper_cents": cond.get("ci_upper_cents"),
            "ci_level": cond.get("ci_level"),
            "method": cond.get("method"),
        },
        "source_model_id": query.get("model_version"),
        "source_model_version": query.get("model_version"),
        "dataset_version": query.get("dataset_version"),
        "feature_schema_version": query.get("feature_schema_version"),
        "pca_version": query.get("pca_version"),
        "knn_status": query.get("knn_status"),
        "query_status": query.get("status"),
        "reason": query.get("reason"),
        "details": {
            "features": features,
            "pca_vector": query.get("pca_vector"),
            "distribution": query.get("distribution"),
            "sizing": query.get("sizing"),
            "availability": query.get("availability"),
            "knn_config": query.get("knn_config"),
        },
        "note": "Historical query. Live feed UNAVAILABLE. Candle path ≠ fill.",
    }


def list_row(trade: dict[str, Any], observed: dict[str, Any] | None) -> dict[str, Any]:
    last = observed or {}
    home = trade.get("home_team") or ""
    away = trade.get("away_team") or ""
    return {
        "position_id": trade.get("trade_id"),
        "trade_id": trade.get("trade_id"),
        "ticker": trade.get("ticker"),
        "sport": trade.get("sport") or "NBA",
        "game": f"{away} @ {home}".strip(" @"),
        "home_team": trade.get("home_team"),
        "away_team": trade.get("away_team"),
        "team": trade.get("team"),
        "side": trade.get("entry_side"),
        "position_label": f"{trade.get('team') or ''} YES".strip(),
        "entry_price_cents": trade.get("entry_price_cents"),
        "entry_timestamp": trade.get("entry_timestamp"),
        "last_observed_price_cents": last.get("last_observed_price_cents"),
        "last_observed_at": last.get("last_observed_at"),
        "slice": trade.get("slice"),
        "quarter": trade.get("quarter"),
        "game_date": trade.get("game_date"),
        "dataset_split": trade.get("dataset_split"),
        "mode": "HISTORICAL",
        "live_feed": "UNAVAILABLE",
        "position_status": "HISTORICAL",
    }
