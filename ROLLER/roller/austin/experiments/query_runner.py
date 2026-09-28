"""Frozen Austin queries on NCAAB PRIMARY_GRID. Model is never refit."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from roller.austin.config import DEFAULT
from roller.austin.experiments.ids import (
    CLOCK_SPORT,
    EV_DEFINITION,
    FILL_STATUS,
    LIVE_FEED,
    LOW_SUPPORT_MEDIAN_DISTANCE,
    PAGE3_N,
    assert_experiment_id,
)
from roller.austin.experiments.ncaab_state import build_ncaab_query_state
from roller.austin.experiments.outcomes_ncaab import outcomes_for_trade
from roller.austin.experiments.policies import assign_ev_entry
from roller.austin.experiments.schedule import build_observation_grid
from roller.austin.experiments.warehouse_cache import load_trade_warehouse
from roller.austin.outcomes import HOLD_EV_DEFINITION
from roller.austin.paths import experiment_dir, sizing_path
from roller.austin.query import query_match
from roller.austin.store import load_json, load_pca_model, load_snapshots

STATE_FIELDS = (
    "experiment_id",
    "cohort",
    "trade_id",
    "internal_game_id",
    "ticker",
    "period",
    "game_clock_remaining",
    "timestamp_utc",
    "role",
    "primary",
    "skip_reason",
    "query_mode",
    "query_source",
    "entry_source",
    "entry_price_cents",
    "current_price_cents",
    "price_travel",
    "time_since_entry",
    "home_score",
    "away_score",
    "knn_status",
    "reason",
    "conditional_ev_cents",
    "ci_lower_cents",
    "ci_upper_cents",
    "ci_method",
    "k",
    "effective_neighbors",
    "effective_sample_size",
    "median_distance",
    "mean_distance",
    "feature_coverage",
    "support_status",
    "availability_status",
    "pnl_hold_after_t",
    "pnl_8040_after_t",
    "pnl_8040_after_t_status",
    "t40_already",
    "hit_40_after",
    "ev_at_entry",
    "ev_now",
    "ev_change",
    "submits",
    "live_feed",
    "page3_n280_queried",
)


def _support_status(median_distance: float | None, knn_status: str | None) -> str:
    if knn_status != "OBSERVED" or median_distance is None:
        return "UNAVAILABLE"
    if float(median_distance) > LOW_SUPPORT_MEDIAN_DISTANCE:
        return "LOW_HISTORICAL_SUPPORT"
    return "OBSERVED"


GRID_FIELDS = (
    "experiment_id",
    "cohort",
    "trade_id",
    "internal_game_id",
    "ticker",
    "period",
    "game_clock_remaining",
    "timestamp_utc",
    "role",
    "skip_reason",
    "primary",
    "on_grid",
    "diagnostic_print",
    "entry_equals_grid",
    "current_price_cents",
    "home_score",
    "away_score",
    "entry_source",
    "entry_price_cents",
)


def _write_grid_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(GRID_FIELDS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name) for name in GRID_FIELDS})


def run_grids(experiment_id: str, trades: list[dict[str, Any]], *, cohort: str = "DISCOVERY") -> list[dict[str, Any]]:
    experiment_id = assert_experiment_id(experiment_id)
    warehouse = load_trade_warehouse(trades)
    out: list[dict[str, Any]] = []
    for idx, trade in enumerate(trades, start=1):
        if idx == 1 or idx % 25 == 0 or idx == len(trades):
            print(f"grid {experiment_id} {cohort} {idx}/{len(trades)}", flush=True)
        if str(trade.get("slice")) == "H2_2":
            from roller.austin.errors import AustinError

            raise AustinError("LOCK_MISMATCH", "H2_2 reached grid runner")
        ticker = str(trade.get("ticker") or "")
        gid = str(trade.get("internal_game_id") or "")
        grid = build_observation_grid(
            trade,
            bars=warehouse["bars"].get(ticker, []),
            pbp=warehouse["pbp"].get(gid, []),
        )
        for obs in grid:
            out.append(
                {
                    **obs,
                    "experiment_id": experiment_id,
                    "cohort": cohort,
                    "entry_source": trade.get("entry_source"),
                    "entry_price_cents": trade.get("entry_price_cents"),
                }
            )
    return out


def persist_grids(experiment_id: str, cohort: str, rows: list[dict[str, Any]]) -> Path:
    root = experiment_dir(experiment_id) / cohort.lower()
    path = root / "observation_grid.csv"
    _write_grid_csv(path, rows)
    if cohort == "DISCOVERY":
        _write_grid_csv(experiment_dir(experiment_id) / "observation_grid.csv", rows)
    return path


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(STATE_FIELDS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name) for name in STATE_FIELDS})


def run_queries(
    experiment_id: str,
    trades: list[dict[str, Any]],
    *,
    cohort: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    experiment_id = assert_experiment_id(experiment_id)
    snaps = load_snapshots()
    if len(snaps) != 48752:
        from roller.austin.errors import AustinError

        raise AustinError("LOCK_MISMATCH", f"snapshot n={len(snaps)} != 48752")
    model = load_pca_model()
    calibration = (load_json(sizing_path(), required=False) or {}).get("calibration") or {}
    out: list[dict[str, Any]] = []
    selected = trades if limit is None else trades[: int(limit)]
    warehouse = load_trade_warehouse(selected)
    for idx, trade in enumerate(selected, start=1):
        if idx == 1 or idx % 10 == 0 or idx == len(selected):
            print(f"query {experiment_id} {cohort} {idx}/{len(selected)}", flush=True)
        if str(trade.get("slice")) == "H2_2":
            from roller.austin.errors import AustinError

            raise AustinError("LOCK_MISMATCH", "H2_2 reached query_runner")
        ticker = str(trade.get("ticker") or "")
        gid = str(trade.get("internal_game_id") or "")
        bars = warehouse["bars"].get(ticker, [])
        pbp = warehouse["pbp"].get(gid, [])
        grid = build_observation_grid(trade, bars=bars, pbp=pbp)
        outcomes_cache: dict[str, dict[str, Any]] = {}
        for obs in grid:
            if obs.get("skip_reason") and obs.get("role") != "DIAGNOSTIC_EVENT":
                out.append(
                    {
                        **obs,
                        "experiment_id": experiment_id,
                        "cohort": cohort,
                        "query_mode": "PRE_80" if obs.get("skip_reason") == "PRE_ENTRY" else None,
                        "query_source": "HISTORICAL_RECONSTRUCT",
                        "entry_source": trade.get("entry_source"),
                        "entry_price_cents": trade.get("entry_price_cents"),
                        "availability_status": "UNAVAILABLE",
                        "submits": False,
                        "live_feed": LIVE_FEED,
                        "page3_n280_queried": False,
                    }
                )
                continue
            if not obs.get("timestamp_utc"):
                continue
            try:
                built = build_ncaab_query_state(
                    trade,
                    timestamp_utc=obs["timestamp_utc"],
                    query_mode="POST_80" if obs.get("skip_reason") != "PRE_ENTRY" else "PRE_80",
                    bars=bars,
                    pbp=pbp,
                )
            except Exception as exc:  # noqa: BLE001 — persist UNAVAILABLE, do not drop the trade
                out.append(
                    {
                        **obs,
                        "experiment_id": experiment_id,
                        "cohort": cohort,
                        "knn_status": "UNAVAILABLE",
                        "reason": str(exc),
                        "availability_status": "UNAVAILABLE",
                        "submits": False,
                        "live_feed": LIVE_FEED,
                        "page3_n280_queried": False,
                    }
                )
                continue
            raw = built["raw"]
            result = query_match(raw, snapshots=snaps, model=model, calibration=calibration, include_entry_change=False)
            ev = (result.get("conditional_ev") or {}) if result.get("conditional_ev") else {}
            support = result.get("support") or {}
            ci_low = ev.get("ci_lower_cents")
            ci_up = ev.get("ci_upper_cents")
            when = built["when"]
            key = when.isoformat()
            if key not in outcomes_cache:
                outcomes_cache[key] = outcomes_for_trade(trade, snapshot_ts=when, bars=built.get("bars") or [])
            oc = outcomes_cache[key]
            knn_status = result.get("knn_status") or result.get("status")
            ev_cents = ev.get("conditional_ev_cents")
            availability = "VALUE" if ev_cents is not None and knn_status == "OBSERVED" else (
                "NOT_APPLICABLE" if raw.query_mode == "PRE_80" else "UNAVAILABLE"
            )
            travel = None
            if raw.entry_price_cents is not None and raw.current_price_cents is not None:
                travel = int(raw.current_price_cents) - int(raw.entry_price_cents)
            out.append(
                {
                    **obs,
                    "experiment_id": experiment_id,
                    "cohort": cohort,
                    "query_mode": raw.query_mode,
                    "query_source": raw.query_source,
                    "entry_source": raw.entry_source,
                    "entry_price_cents": raw.entry_price_cents,
                    "current_price_cents": raw.current_price_cents,
                    "price_travel": travel,
                    "time_since_entry": raw.time_since_entry_sec,
                    "home_score": raw.home_score_current,
                    "away_score": raw.away_score_current,
                    "knn_status": knn_status,
                    "reason": result.get("reason"),
                    "conditional_ev_cents": ev_cents,
                    "ci_lower_cents": ci_low,
                    "ci_upper_cents": ci_up,
                    "ci_method": ev.get("method") or "95% CI — weighted bootstrap",
                    "k": support.get("k") or DEFAULT.k_default,
                    "effective_neighbors": support.get("effective_neighbors"),
                    "effective_sample_size": support.get("effective_sample_size"),
                    "median_distance": support.get("median_distance"),
                    "mean_distance": support.get("mean_distance"),
                    "feature_coverage": support.get("feature_coverage") or result.get("feature_coverage"),
                    "support_status": _support_status(support.get("median_distance"), knn_status),
                    "availability_status": availability,
                    "pnl_hold_after_t": oc.get("pnl_hold_after_t"),
                    "pnl_8040_after_t": oc.get("pnl_8040_after_t"),
                    "pnl_8040_after_t_status": oc.get("pnl_8040_after_t_status"),
                    "t40_already": oc.get("t40_already"),
                    "hit_40_after": oc.get("hit_40_after"),
                    "submits": False,
                    "live_feed": LIVE_FEED,
                    "page3_n280_queried": False,
                    "clock_sport": CLOCK_SPORT,
                    "ev_definition": HOLD_EV_DEFINITION,
                    "fill_status": FILL_STATUS,
                    "page3_n": PAGE3_N,
                }
            )
    return assign_ev_entry(out)


def persist_trajectories(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = (
        "trade_id",
        "internal_game_id",
        "checkpoint_timestamp",
        "period",
        "game_clock_remaining",
        "role",
        "primary",
        "current_price_cents",
        "conditional_ev_cents",
        "ev_at_entry",
        "ev_now",
        "ev_change",
        "pnl_hold_after_t",
        "availability_status",
    )
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "trade_id": row.get("trade_id"),
                    "internal_game_id": row.get("internal_game_id"),
                    "checkpoint_timestamp": row.get("timestamp_utc"),
                    "period": row.get("period"),
                    "game_clock_remaining": row.get("game_clock_remaining"),
                    "role": row.get("role"),
                    "primary": row.get("primary"),
                    "current_price_cents": row.get("current_price_cents"),
                    "conditional_ev_cents": row.get("conditional_ev_cents"),
                    "ev_at_entry": row.get("ev_at_entry"),
                    "ev_now": row.get("ev_now"),
                    "ev_change": row.get("ev_change"),
                    "pnl_hold_after_t": row.get("pnl_hold_after_t"),
                    "availability_status": row.get("availability_status"),
                }
            )


def persist_queries(experiment_id: str, cohort: str, rows: list[dict[str, Any]]) -> Path:
    root = experiment_dir(experiment_id) / cohort.lower()
    path = root / "state_queries.csv"
    _write_csv(path, rows)
    persist_trajectories(root / "trade_trajectories.csv", rows)
    parent = experiment_dir(experiment_id)
    if cohort == "DISCOVERY":
        _write_csv(parent / "state_queries.csv", rows)
        persist_trajectories(parent / "trade_trajectories.csv", rows)
    if cohort == "CONFIRMATION":
        _write_csv(parent / "confirmation_state_queries.csv", rows)
        persist_trajectories(parent / "confirmation_trade_trajectories.csv", rows)
    return path
