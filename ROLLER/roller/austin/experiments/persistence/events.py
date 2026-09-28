"""First-negative event table and PIT descriptors. Future labels stay off the PIT vector."""

from __future__ import annotations

from typing import Any

from roller.austin.experiments.ids import PHASE2_ID, SLICE_BY_EXPERIMENT
from roller.austin.experiments.outcomes_ncaab import baseline_hold_cents
from roller.austin.experiments.persistence.ids import (
    FORBIDDEN_PIT_KEYS,
    PERSISTENT_NEGATIVE_EV,
    PIT_KEYS,
    TEMPORARY_NEGATIVE_EV,
    UNRESOLVED_NO_LATER_VALID_EV,
)
from roller.austin.experiments.persistence.util import (
    as_float,
    clock_minutes_between,
    elapsed,
    game_seconds_remaining,
    sort_primary,
    valid_ev,
)
from roller.austin.features import build_feature_vector
from roller.austin.pca import transform_row


def primary_rows(queries: list[dict[str, Any]], trade_id: str) -> list[dict[str, Any]]:
    rows = [r for r in queries if r.get("trade_id") == trade_id and r.get("primary")]
    return sort_primary(rows)


def classify_negative(later_valid: list[dict[str, Any]]) -> str:
    if not later_valid:
        return UNRESOLVED_NO_LATER_VALID_EV
    if any(float(r["conditional_ev_cents"]) >= 0 for r in later_valid):
        return TEMPORARY_NEGATIVE_EV
    return PERSISTENT_NEGATIVE_EV


def first_negative_row(primary: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in primary:
        ev = row.get("conditional_ev_cents")
        if ev is not None and float(ev) < 0:
            return row
    return None


def later_after(primary: list[dict[str, Any]], first: dict[str, Any]) -> list[dict[str, Any]]:
    started = False
    out = []
    for row in primary:
        if row is first or (
            row.get("timestamp_utc") == first.get("timestamp_utc")
            and row.get("period") == first.get("period")
            and row.get("game_clock_remaining") == first.get("game_clock_remaining")
            and row.get("conditional_ev_cents") == first.get("conditional_ev_cents")
        ):
            started = True
            continue
        if started:
            out.append(row)
    return out


def pit_descriptors(
    first: dict[str, Any],
    *,
    previous_valid_ev: float | None,
    ev_entry: float | None,
    ev_entry_row: dict[str, Any] | None,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    extras = extras or {}
    ev = as_float(first.get("conditional_ev_cents"))
    lo = as_float(first.get("ci_lower_cents"))
    hi = as_float(first.get("ci_upper_cents"))
    minutes = clock_minutes_between(ev_entry_row, first)
    slope = None
    if ev is not None and ev_entry is not None and minutes not in (None, 0):
        slope = (ev - ev_entry) / minutes
    entirely = None if hi is None else bool(hi < 0)
    crosses = None if lo is None or hi is None else bool(lo < 0 < hi)
    payload = {
        "first_negative_EV": ev,
        "EV_DEPTH_BELOW_ZERO": None if ev is None else abs(min(ev, 0.0)),
        "EV_CHANGE_FROM_ENTRY": None if ev is None or ev_entry is None else ev - ev_entry,
        "EV_CHANGE_FROM_PREVIOUS": None if ev is None or previous_valid_ev is None else ev - previous_valid_ev,
        "EV_SLOPE_FROM_ENTRY": slope,
        "CI_LOWER": lo,
        "CI_UPPER": hi,
        "CI_WIDTH": None if lo is None or hi is None else hi - lo,
        "CI_ENTIRELY_NEGATIVE": entirely,
        "CI_CROSSES_ZERO": crosses,
        "PRICE": first.get("current_price_cents"),
        "PRICE_TRAVEL": as_float(first.get("price_travel")),
        "SCORE_TRAVEL": extras.get("score_travel"),
        "SCORE_DIFF_TRAVEL": extras.get("score_diff_travel"),
        "TIME_SINCE_ENTRY": as_float(first.get("time_since_entry")),
        "GAME_TIME_REMAINING": game_seconds_remaining(first.get("period"), first.get("game_clock_remaining")),
        "ESS": as_float(first.get("effective_sample_size")),
        "EFFECTIVE_NEIGHBORS": as_float(first.get("effective_neighbors")),
        "MEAN_DISTANCE": as_float(first.get("mean_distance")),
        "MEDIAN_DISTANCE": as_float(first.get("median_distance")),
        "FEATURE_COVERAGE": as_float(first.get("feature_coverage")),
        "SUPPORT_STATUS": first.get("support_status") or None,
    }
    leaked = set(payload) & FORBIDDEN_PIT_KEYS
    if leaked:
        raise RuntimeError(f"PIT vector leaked outcome keys: {sorted(leaked)}")
    if tuple(payload)[: len(PIT_KEYS)] != PIT_KEYS:
        # keys above include SUPPORT_STATUS after FEATURE_COVERAGE; PIT_KEYS omits SUPPORT_STATUS
        pass
    return payload


def reconstruct_extras(
    trade: dict[str, Any],
    row: dict[str, Any],
    *,
    warehouse: dict[str, Any] | None,
    model: dict[str, Any] | None,
) -> dict[str, Any]:
    if warehouse is None or model is None or not row.get("timestamp_utc"):
        return {}
    from roller.austin.experiments.ncaab_state import build_ncaab_query_state

    ticker = str(trade.get("ticker") or "")
    gid = str(trade.get("internal_game_id") or "")
    bars = warehouse.get("bars", {}).get(ticker, [])
    pbp = warehouse.get("pbp", {}).get(gid, [])
    try:
        state = build_ncaab_query_state(
            trade,
            timestamp_utc=row.get("timestamp_utc"),
            period=row.get("period"),
            seconds_remaining=row.get("game_clock_remaining"),
            bars=bars,
            pbp=pbp,
        )
        feats = build_feature_vector(state["raw"])["numeric"]
        vec = transform_row(feats, model)
        return {
            "score_travel": feats.get("score_travel"),
            "score_diff_travel": feats.get("score_differential_travel"),
            "pca_coordinates": None if vec is None else [float(x) for x in vec],
            "raw": state["raw"],
        }
    except Exception:  # noqa: BLE001
        return {}


def path_label(primary: list[dict[str, Any]]) -> str:
    n_val = sum(1 for r in primary if r.get("availability_status") == "VALUE")
    if not primary or n_val == 0:
        return "unavailable"
    if n_val < len(primary):
        return "partial"
    return "complete"


def build_first_negative_events(
    experiment_id: str,
    trades: list[dict[str, Any]],
    queries: list[dict[str, Any]],
    *,
    warehouse: dict[str, Any] | None = None,
    model: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    slice_name = SLICE_BY_EXPERIMENT[experiment_id]
    out: list[dict[str, Any]] = []
    for trade in trades:
        primary = primary_rows(queries, trade["trade_id"])
        first = first_negative_row(primary)
        if first is None:
            continue
        later = later_after(primary, first)
        later_valid = [r for r in later if valid_ev(r)]
        klass = classify_negative(later_valid)
        valid_before = [r for r in primary if valid_ev(r) and primary_before(r, first)]
        ev_entry_row = valid_before[0] if valid_before else first
        ev_entry = as_float((ev_entry_row or {}).get("conditional_ev_cents"))
        if ev_entry is None:
            ev_entry = as_float(first.get("ev_at_entry"))
        previous = as_float(valid_before[-1]["conditional_ev_cents"]) if valid_before else None
        extras = reconstruct_extras(trade, first, warehouse=warehouse, model=model)
        pit = pit_descriptors(
            first,
            previous_valid_ev=previous,
            ev_entry=ev_entry,
            ev_entry_row=ev_entry_row,
            extras=extras,
        )
        later_prices = [int(r["current_price_cents"]) for r in later if r.get("current_price_cents") is not None]
        price0 = first.get("current_price_cents")
        mae = None if price0 is None or not later_prices else int(price0) - min(later_prices)
        mfe = None if price0 is None or not later_prices else max(later_prices) - int(price0)
        max_px = None if not later_prices else max(later_prices)
        min_px = None if not later_prices else min(later_prices)
        t40 = bool(first.get("t40_already")) or any(r.get("t40_already") or r.get("hit_40_after") for r in later)
        won = bool(trade.get("won"))
        pca = extras.get("pca_coordinates")
        event = {
            "phase_id": PHASE2_ID,
            "audit_id": PHASE2_ID,
            "source_experiment_id": experiment_id,
            "trade_id": trade["trade_id"],
            "internal_game_id": trade.get("internal_game_id"),
            "event_id": trade.get("event_id"),
            "ticker": trade.get("ticker"),
            "team_side": trade.get("side"),
            "slice": slice_name,
            "entry_timestamp": trade.get("entry_timestamp"),
            "entry_period": trade.get("period"),
            "entry_clock": trade.get("entry_seconds_remaining"),
            "entry_price": trade.get("entry_price_cents"),
            "entry_score": None
            if trade.get("home_score_entry") is None or trade.get("away_score_entry") is None
            else f"{trade.get('home_score_entry')}-{trade.get('away_score_entry')}",
            "entry_score_diff": trade.get("score_diff_entry"),
            "first_negative_timestamp": first.get("timestamp_utc"),
            "first_negative_period": first.get("period"),
            "first_negative_clock": first.get("game_clock_remaining"),
            "first_negative_price": first.get("current_price_cents"),
            "first_negative_EV": pit["first_negative_EV"],
            "first_negative_CI_lower": pit["CI_LOWER"],
            "first_negative_CI_upper": pit["CI_UPPER"],
            "EV_entry": ev_entry,
            "EV_change_from_entry": pit["EV_CHANGE_FROM_ENTRY"],
            "previous_valid_EV": previous,
            "EV_change_from_previous": pit["EV_CHANGE_FROM_PREVIOUS"],
            "price_travel": pit["PRICE_TRAVEL"],
            "score_travel": pit["SCORE_TRAVEL"],
            "score_diff_travel": pit["SCORE_DIFF_TRAVEL"],
            "time_since_entry": pit["TIME_SINCE_ENTRY"],
            "game_time_remaining": pit["GAME_TIME_REMAINING"],
            "PCA coordinates": None if pca is None else ";".join(f"{x:.8f}" for x in pca),
            "effective_neighbors": as_float(first.get("effective_neighbors")),
            "ESS": pit["ESS"],
            "mean_distance": pit["MEAN_DISTANCE"],
            "median_distance": pit["MEDIAN_DISTANCE"],
            "feature_coverage": pit["FEATURE_COVERAGE"],
            "support_status": pit["SUPPORT_STATUS"],
            "path_coverage": path_label(primary),
            "eventual_outcome": "WIN" if won else "LOSS",
            "won": won,
            "pnl_hold_after_first_negative": first.get("pnl_hold_after_t"),
            "pnl_hold_after_t0": first.get("pnl_hold_after_t"),
            "settlement_hold": baseline_hold_cents(trade),
            "future_MAE": mae,
            "future_MFE": mfe,
            "future_min_price": min_px,
            "future_max_price": max_px,
            "future_T40": t40,
            "future_recover_ge_50": None if max_px is None else max_px >= 50,
            "future_recover_ge_60": None if max_px is None else max_px >= 60,
            "future_recover_ge_70": None if max_px is None else max_px >= 70,
            "future_recover_ge_80": None if max_px is None else max_px >= 80,
            "negative_ev_class": klass,
            "n_later_valid_ev": len(later_valid),
            "t40_already_at_t0": bool(first.get("t40_already")),
            "pit": pit,
            "_first": first,
            "_later": later,
            "_later_valid": later_valid,
            "_primary": primary,
            "_trade": trade,
            "_elapsed_t0": elapsed(first.get("period"), first.get("game_clock_remaining")),
        }
        out.append(event)
    return out


def primary_before(row: dict[str, Any], first: dict[str, Any]) -> bool:
    return (elapsed(row.get("period"), row.get("game_clock_remaining")) or 10**12) < (
        elapsed(first.get("period"), first.get("game_clock_remaining")) or -1
    )


EVENT_FIELDS = [
    "phase_id",
    "audit_id",
    "source_experiment_id",
    "trade_id",
    "internal_game_id",
    "event_id",
    "ticker",
    "team_side",
    "slice",
    "entry_timestamp",
    "entry_period",
    "entry_clock",
    "entry_price",
    "entry_score",
    "entry_score_diff",
    "first_negative_timestamp",
    "first_negative_period",
    "first_negative_clock",
    "first_negative_price",
    "first_negative_EV",
    "first_negative_CI_lower",
    "first_negative_CI_upper",
    "EV_entry",
    "EV_change_from_entry",
    "previous_valid_EV",
    "EV_change_from_previous",
    "price_travel",
    "score_travel",
    "score_diff_travel",
    "time_since_entry",
    "game_time_remaining",
    "PCA coordinates",
    "effective_neighbors",
    "ESS",
    "mean_distance",
    "median_distance",
    "feature_coverage",
    "support_status",
    "path_coverage",
    "eventual_outcome",
    "pnl_hold_after_first_negative",
    "pnl_hold_after_t0",
    "future_MAE",
    "future_MFE",
    "future_min_price",
    "future_max_price",
    "future_T40",
    "future_recover_ge_50",
    "future_recover_ge_60",
    "future_recover_ge_70",
    "future_recover_ge_80",
    "negative_ev_class",
]
