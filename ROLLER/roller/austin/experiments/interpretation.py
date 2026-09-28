"""Discovery interpretation audit. Reads existing artifacts. No query_match. No freeze."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from typing import Any

import numpy as np

from roller.austin.clock import parse_utc
from roller.austin.errors import AustinError
from roller.austin.experiments.cohorts import load_cohort
from roller.austin.experiments.ids import (
    BOOTSTRAP_B,
    BOOTSTRAP_SEED,
    DETERIORATION_X_CENTS,
    EXPERIMENT_A,
    EXPERIMENT_B,
    MEMBERS,
    N_A,
    N_B,
    SLICE_BY_EXPERIMENT,
    SUITE_ID,
    assert_experiment_id,
)
from roller.austin.experiments.outcomes_ncaab import baseline_hold_cents
from roller.austin.experiments.statistics import (
    _nums,
    calibration_rows,
    clustered_mean,
    clustered_mean_diff,
    clustered_ratio,
    summarize_pnl,
    warning_rows,
)
from roller.austin.paths import experiment_dir
from roller.austin.store import write_json


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes"}


def _float(value: object) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: object) -> int | None:
    num = _float(value)
    return None if num is None else int(round(num))


def load_discovery_queries(experiment_id: str) -> list[dict[str, Any]]:
    path = experiment_dir(experiment_id) / "discovery" / "state_queries.csv"
    if not path.is_file():
        raise AustinError("DATA_REQUIRED", f"{experiment_id} discovery state_queries.csv missing")
    rows = []
    with path.open(newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            rec["primary"] = _truthy(rec.get("primary"))
            rec["t40_already"] = _truthy(rec.get("t40_already"))
            rec["hit_40_after"] = _truthy(rec.get("hit_40_after"))
            rec["conditional_ev_cents"] = _float(rec.get("conditional_ev_cents"))
            rec["ci_lower_cents"] = _float(rec.get("ci_lower_cents"))
            rec["ci_upper_cents"] = _float(rec.get("ci_upper_cents"))
            rec["ev_at_entry"] = _float(rec.get("ev_at_entry"))
            rec["ev_now"] = _float(rec.get("ev_now"))
            rec["ev_change"] = _float(rec.get("ev_change"))
            rec["pnl_hold_after_t"] = _float(rec.get("pnl_hold_after_t"))
            rec["current_price_cents"] = _int(rec.get("current_price_cents"))
            rec["entry_price_cents"] = _int(rec.get("entry_price_cents"))
            rec["period"] = _int(rec.get("period"))
            rec["game_clock_remaining"] = _int(rec.get("game_clock_remaining"))
            rows.append(rec)
    return rows


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.median(values))


def coverage_audit(trades: list[dict[str, Any]], queries: list[dict[str, Any]]) -> dict[str, Any]:
    primary = [r for r in queries if r.get("primary")]
    valid = [
        r
        for r in primary
        if r.get("conditional_ev_cents") is not None and r.get("pnl_hold_after_t") is not None
    ]
    by_trade: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in primary:
        by_trade[row["trade_id"]].append(row)
    complete = partial = unavailable = 0
    valid_counts = []
    for trade in trades:
        rows = by_trade.get(trade["trade_id"], [])
        n_val = sum(1 for r in rows if r.get("availability_status") == "VALUE")
        n_miss = sum(1 for r in rows if r.get("availability_status") != "VALUE")
        valid_counts.append(n_val)
        if not rows or n_val == 0:
            unavailable += 1
        elif n_miss:
            partial += 1
        else:
            complete += 1
    pre80 = [r for r in primary if r.get("query_mode") == "PRE_80"]
    post80 = [r for r in primary if r.get("query_mode") == "POST_80"]
    wall_before_entry = 0
    deltas = []
    by_entry = {t["trade_id"]: t for t in trades}
    for row in pre80:
        trade = by_entry.get(row["trade_id"]) or {}
        entry = parse_utc(trade.get("entry_timestamp"))
        when = parse_utc(row.get("timestamp_utc"))
        if entry is not None and when is not None:
            deltas.append((when - entry).total_seconds())
            if when < entry:
                wall_before_entry += 1
    reason = Counter(str(r.get("reason") or "") for r in primary)
    knn = Counter(str(r.get("knn_status") or "") for r in primary)
    clocks = Counter((r.get("period"), r.get("game_clock_remaining")) for r in pre80)
    diagnosis = (
        "PRIMARY_GRID clock-eligible rows reconstructed as PRE_80 because PBP/bar "
        "timestamp < asked-six entry_timestamp. Warehouse price/score are present. "
        "KNN is not missing; NO_ENTRY_IN_FITTED_SPACE is the PRE_80 gate. "
        "This is clock-vs-wall alignment, not an absent parquet tree."
        if pre80
        else "No PRIMARY PRE_80 rows."
    )
    n = len(trades) or 1
    return {
        "n_trades": len(trades),
        "n_primary": len(primary),
        "n_valid_ordering_states": len(valid),
        "valid_states_per_trade": float(len(valid) / n),
        "path_complete": complete,
        "path_partial": partial,
        "path_unavailable": unavailable,
        "primary_query_mode": {"PRE_80": len(pre80), "POST_80": len(post80)},
        "primary_knn_status": dict(knn),
        "primary_reason": dict(reason),
        "primary_pre80_wall_before_entry": wall_before_entry,
        "primary_pre80_when_minus_entry_sec": {
            "n": len(deltas),
            "median": _median(deltas),
            "p25": None if not deltas else float(np.quantile(deltas, 0.25)),
            "p75": None if not deltas else float(np.quantile(deltas, 0.75)),
            "min": None if not deltas else float(min(deltas)),
            "max": None if not deltas else float(max(deltas)),
        },
        "primary_pre80_clocks": {f"P{p}_{r}": n for (p, r), n in clocks.most_common(12)},
        "valid_per_trade_min": None if not valid_counts else int(min(valid_counts)),
        "valid_per_trade_max": None if not valid_counts else int(max(valid_counts)),
        "diagnosis": diagnosis,
        "missing_warehouse_not_the_cause": True,
    }


def warning_denominators(trades: list[dict[str, Any]], queries: list[dict[str, Any]]) -> dict[str, Any]:
    rows = warning_rows(trades, queries)
    by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_class[str(row["class"])].append(row)

    def pack(name: str, values: list[float]) -> dict[str, Any]:
        return {
            "field": name,
            "n": len(values),
            "median": _median(values),
            "p25": None if not values else float(np.quantile(values, 0.25)),
            "p75": None if not values else float(np.quantile(values, 0.75)),
            "missing_not_zero": True,
        }

    available = by_class.get("WARNING_AVAILABLE") or []
    too_late = by_class.get("WARNING_TOO_LATE") or []
    first_neg = available + too_late
    return {
        "n_trades": len(rows),
        "n_WARNING_AVAILABLE": len(available),
        "n_WARNING_TOO_LATE": len(too_late),
        "n_NO_WARNING": len(by_class.get("NO_WARNING") or []),
        "n_PATH_UNAVAILABLE": len(by_class.get("PATH_UNAVAILABLE") or []),
        "median_warning_available": pack(
            "warning_to_settlement | WARNING_AVAILABLE",
            _nums([r.get("warning_to_settlement_game_clock_minutes") for r in available]),
        ),
        "median_warning_too_late": pack(
            "warning_to_settlement | WARNING_TOO_LATE",
            _nums([r.get("warning_to_settlement_game_clock_minutes") for r in too_late]),
        ),
        "median_first_negative_to_T40": pack(
            "warning_to_t40 | first negative EV",
            _nums([r.get("warning_to_t40_game_clock_minutes") for r in first_neg]),
        ),
        "median_first_negative_to_worst_price": pack(
            "warning_to_worst | first negative EV",
            _nums([r.get("warning_to_worst_price_game_clock_minutes") for r in first_neg]),
        ),
        "median_first_negative_to_settlement": pack(
            "warning_to_settlement | first negative EV (AVAILABLE + TOO_LATE)",
            _nums([r.get("warning_to_settlement_game_clock_minutes") for r in first_neg]),
        ),
        "label": (
            "Discovery report median_minutes is median_first_negative_to_settlement "
            "over AVAILABLE+TOO_LATE. It is not median_warning_available. "
            "If AVAILABLE=0 the reported median is a TOO_LATE-only figure."
        ),
    }


def ordering_audit(trades: list[dict[str, Any]], queries: list[dict[str, Any]]) -> dict[str, Any]:
    trade_hold = {t["trade_id"]: baseline_hold_cents(t) for t in trades}
    trade_game = {t["trade_id"]: t.get("internal_game_id") for t in trades}
    valid = []
    for row in queries:
        if not row.get("primary"):
            continue
        if row.get("conditional_ev_cents") is None or row.get("pnl_hold_after_t") is None:
            continue
        valid.append(
            {
                **row,
                "internal_game_id": row.get("internal_game_id") or trade_game.get(row["trade_id"]),
                "hold_after": row["pnl_hold_after_t"],
                "ev_negative": float(row["conditional_ev_cents"]) < 0,
                "deteriorated": row.get("ev_change") is not None
                and float(row["ev_change"]) <= -DETERIORATION_X_CENTS,
            }
        )
    ev_ci = clustered_mean_diff(
        valid,
        value_key="hold_after",
        positive_pred=lambda r: not r["ev_negative"],
        negative_pred=lambda r: r["ev_negative"],
    )
    det_rows = [r for r in valid if r.get("ev_change") is not None]
    det_ci = clustered_mean_diff(
        det_rows,
        value_key="hold_after",
        positive_pred=lambda r: not r["deteriorated"],
        negative_pred=lambda r: r["deteriorated"],
    )
    trade_rows = []
    by_trade: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in valid:
        by_trade[row["trade_id"]].append(row)
    for trade in trades:
        rows = by_trade.get(trade["trade_id"], [])
        first = rows[0] if rows else None
        first_neg = next((r for r in rows if r["ev_negative"]), None)
        hold = trade_hold.get(trade["trade_id"])
        trade_rows.append(
            {
                "trade_id": trade["trade_id"],
                "internal_game_id": trade.get("internal_game_id"),
                "settlement_hold": hold,
                "first_valid_ev": None if first is None else first["conditional_ev_cents"],
                "first_valid_hold_after": None if first is None else first["hold_after"],
                "first_valid_ev_negative": None if first is None else first["ev_negative"],
                "first_negative_hold_after": None if first_neg is None else first_neg["hold_after"],
                "ever_negative": first_neg is not None,
                "ever_deteriorated": any(r["deteriorated"] for r in rows),
            }
        )
    first_valid_ci = clustered_mean_diff(
        [r for r in trade_rows if r["first_valid_hold_after"] is not None and r["first_valid_ev_negative"] is not None],
        value_key="first_valid_hold_after",
        positive_pred=lambda r: not r["first_valid_ev_negative"],
        negative_pred=lambda r: r["first_valid_ev_negative"],
    )
    settle_ci = clustered_mean_diff(
        [r for r in trade_rows if r["settlement_hold"] is not None and r["ever_negative"] is not None],
        value_key="settlement_hold",
        positive_pred=lambda r: not r["ever_negative"],
        negative_pred=lambda r: r["ever_negative"],
    )
    first_neg_hold = [r["first_negative_hold_after"] for r in trade_rows if r["first_negative_hold_after"] is not None]
    return {
        "n_valid_states": len(valid),
        "n_trades_with_valid_state": sum(1 for r in trade_rows if r["first_valid_ev"] is not None),
        "state_ev_ordering": {
            **ev_ci,
            "claim": "mean hold_after | EV>=0  minus  mean hold_after | EV<0",
            "status": (
                "SUPPORTED"
                if ev_ci.get("excludes_zero") and (ev_ci.get("observed_delta") or 0) > 0
                else (
                    "MIXED"
                    if ev_ci.get("observed_delta") and ev_ci["observed_delta"] > 0
                    else ("INSUFFICIENT_SAMPLE" if ev_ci.get("observed_delta") is None else "NOT_SUPPORTED")
                )
            ),
        },
        "state_deterioration_ordering": {
            **det_ci,
            "claim": "mean hold_after | not deteriorated  minus  mean hold_after | EV-EV_entry<=-8",
            "status": (
                "SUPPORTED"
                if det_ci.get("excludes_zero") and (det_ci.get("observed_delta") or 0) > 0
                else (
                    "MIXED"
                    if det_ci.get("observed_delta") and det_ci["observed_delta"] > 0
                    else ("INSUFFICIENT_SAMPLE" if det_ci.get("observed_delta") is None else "NOT_SUPPORTED")
                )
            ),
        },
        "trade_first_valid_checkpoint": {
            **first_valid_ci,
            "claim": "one row per trade; first valid PRIMARY EV sign; value = hold_after at that checkpoint",
            "status": (
                "SUPPORTED"
                if first_valid_ci.get("excludes_zero") and (first_valid_ci.get("observed_delta") or 0) > 0
                else (
                    "MIXED"
                    if first_valid_ci.get("observed_delta") and first_valid_ci["observed_delta"] > 0
                    else ("INSUFFICIENT_SAMPLE" if first_valid_ci.get("observed_delta") is None else "NOT_SUPPORTED")
                )
            ),
        },
        "trade_ever_negative_vs_settlement_hold": {
            **settle_ci,
            "claim": "one row per trade; never-negative vs ever-negative; value = BASELINE_HOLD",
            "status": (
                "SUPPORTED"
                if settle_ci.get("excludes_zero") and (settle_ci.get("observed_delta") or 0) > 0
                else (
                    "MIXED"
                    if settle_ci.get("observed_delta") and settle_ci["observed_delta"] > 0
                    else ("INSUFFICIENT_SAMPLE" if settle_ci.get("observed_delta") is None else "NOT_SUPPORTED")
                )
            ),
        },
        "first_negative_subsequent_hold": summarize_pnl(first_neg_hold),
    }


def first_negative_audit(trades: list[dict[str, Any]], queries: list[dict[str, Any]]) -> dict[str, Any]:
    by_trade: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in queries:
        if row.get("primary"):
            by_trade[row["trade_id"]].append(row)
    out_rows = []
    for trade in trades:
        rows = by_trade.get(trade["trade_id"], [])
        valid = [r for r in rows if r.get("conditional_ev_cents") is not None]
        first = next((r for r in valid if float(r["conditional_ev_cents"]) < 0), None)
        if first is None:
            continue
        later = [r for r in rows if (r.get("timestamp_utc") or "") > (first.get("timestamp_utc") or "")]
        later_valid = [r for r in later if r.get("conditional_ev_cents") is not None]
        later_prices = [int(r["current_price_cents"]) for r in later if r.get("current_price_cents") is not None]
        price0 = first.get("current_price_cents")
        mfe = None if price0 is None or not later_prices else max(later_prices) - int(price0)
        mae = None if price0 is None or not later_prices else int(price0) - min(later_prices)
        max_px = None if not later_prices else max(later_prices)
        later_nonneg = [r for r in later_valid if float(r["conditional_ev_cents"]) >= 0]
        later_neg = [r for r in later_valid if float(r["conditional_ev_cents"]) < 0]
        if later_nonneg:
            klass = "TEMPORARY_DETERIORATION"
        elif later_valid and not later_nonneg:
            klass = "PERSISTENT_DETERIORATION"
        else:
            klass = "UNRESOLVED_NO_LATER_VALID_EV"
        t40_later = any(r.get("t40_already") or r.get("hit_40_after") for r in later) or bool(first.get("t40_already"))
        out_rows.append(
            {
                "trade_id": trade["trade_id"],
                "internal_game_id": trade.get("internal_game_id"),
                "won": bool(trade.get("won")),
                "class": klass,
                "price_at_first_negative": price0,
                "ev_at_first_negative": first.get("conditional_ev_cents"),
                "hold_after_first_negative": first.get("pnl_hold_after_t"),
                "settlement_hold": baseline_hold_cents(trade),
                "subsequent_mae_cents": mae,
                "subsequent_mfe_cents": mfe,
                "max_later_price": max_px,
                "recovered_to_60": False if max_px is None else max_px >= 60,
                "recovered_to_70": False if max_px is None else max_px >= 70,
                "recovered_to_80": False if max_px is None else max_px >= 80,
                "later_hit_t40": t40_later,
                "n_later_valid_ev": len(later_valid),
                "n_later_nonnegative_ev": len(later_nonneg),
                "n_later_negative_ev": len(later_neg),
            }
        )
    n = len(out_rows)
    winners = [r for r in out_rows if r["won"]]
    losers = [r for r in out_rows if not r["won"]]
    classes = Counter(r["class"] for r in out_rows)

    def rate(pred) -> dict[str, Any]:
        known = [r for r in out_rows if pred(r) is not None]
        yes = [r for r in known if pred(r)]
        return {"n": len(yes), "n_known": len(known), "share": None if not known else len(yes) / len(known)}

    return {
        "n_first_negative_trades": n,
        "n_eventually_win": len(winners),
        "n_eventually_lose": len(losers),
        "win_share": None if not n else len(winners) / n,
        "settlement_hold": summarize_pnl([float(r["settlement_hold"]) for r in out_rows if r["settlement_hold"] is not None]),
        "hold_after_first_negative": summarize_pnl(
            [float(r["hold_after_first_negative"]) for r in out_rows if r["hold_after_first_negative"] is not None]
        ),
        "subsequent_mae": summarize_pnl([float(r["subsequent_mae_cents"]) for r in out_rows if r["subsequent_mae_cents"] is not None]),
        "subsequent_mfe": summarize_pnl([float(r["subsequent_mfe_cents"]) for r in out_rows if r["subsequent_mfe_cents"] is not None]),
        "recovered_to_60": rate(lambda r: r["recovered_to_60"]),
        "recovered_to_70": rate(lambda r: r["recovered_to_70"]),
        "recovered_to_80": rate(lambda r: r["recovered_to_80"]),
        "later_hit_t40": rate(lambda r: r["later_hit_t40"]),
        "deterioration_class": {
            "TEMPORARY_DETERIORATION": classes.get("TEMPORARY_DETERIORATION", 0),
            "PERSISTENT_DETERIORATION": classes.get("PERSISTENT_DETERIORATION", 0),
            "UNRESOLVED_NO_LATER_VALID_EV": classes.get("UNRESOLVED_NO_LATER_VALID_EV", 0),
            "definition": (
                "TEMPORARY = later valid PRIMARY EV >= 0 exists. "
                "PERSISTENT = later valid PRIMARY EV exists and all stay < 0. "
                "UNRESOLVED = no later valid PRIMARY EV. Descriptive only. Not a policy."
            ),
        },
        "temporary_win_lose": {
            "n": classes.get("TEMPORARY_DETERIORATION", 0),
            "win": sum(1 for r in out_rows if r["class"] == "TEMPORARY_DETERIORATION" and r["won"]),
            "lose": sum(1 for r in out_rows if r["class"] == "TEMPORARY_DETERIORATION" and not r["won"]),
        },
        "persistent_win_lose": {
            "n": classes.get("PERSISTENT_DETERIORATION", 0),
            "win": sum(1 for r in out_rows if r["class"] == "PERSISTENT_DETERIORATION" and r["won"]),
            "lose": sum(1 for r in out_rows if r["class"] == "PERSISTENT_DETERIORATION" and not r["won"]),
        },
        "rows": out_rows,
    }


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    rx = np.argsort(np.argsort(np.asarray(xs, dtype=float)))
    ry = np.argsort(np.argsort(np.asarray(ys, dtype=float)))
    if np.std(rx) == 0 or np.std(ry) == 0:
        return None
    return float(np.corrcoef(rx, ry)[0, 1])


def _clustered_spearman(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get("internal_game_id") or row.get("trade_id"))].append(row)
    keys = sorted(groups)
    observed = _spearman(
        [float(r["ev"]) for r in rows],
        [float(r["hold_after"]) for r in rows],
    )
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    vals = []
    for _ in range(BOOTSTRAP_B):
        if not keys:
            break
        pick = rng.choice(len(keys), size=len(keys), replace=True)
        xs = []
        ys = []
        for idx in pick:
            for row in groups[keys[int(idx)]]:
                xs.append(float(row["ev"]))
                ys.append(float(row["hold_after"]))
        rho = _spearman(xs, ys)
        if rho is not None:
            vals.append(rho)
    return {
        "method": "clustered_bootstrap",
        "cluster": "internal_game_id",
        "seed": BOOTSTRAP_SEED,
        "B": BOOTSTRAP_B,
        "n_games": len(keys),
        "n_rows": len(rows),
        "observed": observed,
        "mean": None if not vals else float(np.mean(vals)),
        "ci": [None, None] if not vals else [float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))],
        "excludes_zero": bool(
            vals and (float(np.quantile(vals, 0.025)) > 0 or float(np.quantile(vals, 0.975)) < 0)
        ),
    }


def scoring_audit(trades: list[dict[str, Any]], queries: list[dict[str, Any]]) -> dict[str, Any]:
    """Continuous scoring. Not a single classification accuracy."""
    trade_by_id = {t["trade_id"]: t for t in trades}
    states = []
    for row in queries:
        if not row.get("primary"):
            continue
        ev = row.get("conditional_ev_cents")
        hold = row.get("pnl_hold_after_t")
        if ev is None or hold is None:
            continue
        err = float(ev) - float(hold)
        states.append(
            {
                "trade_id": row["trade_id"],
                "internal_game_id": row.get("internal_game_id") or (trade_by_id.get(row["trade_id"]) or {}).get("internal_game_id"),
                "ev": float(ev),
                "hold_after": float(hold),
                "abs_err": abs(err),
                "sq_err": err * err,
                "sign_hit_strict": 1.0 if (float(ev) > 0) == (float(hold) > 0) else 0.0,
                "zero_ev_or_hold": float(ev) == 0 or float(hold) == 0,
                "predict_bad": float(ev) < 0,
                "realized_bad": float(hold) < 0,
            }
        )
    mae = clustered_mean(states, value_key="abs_err")
    rmse_obs = None if not states else float(np.sqrt(np.mean([s["sq_err"] for s in states])))
    sign_rows = [s for s in states if not s["zero_ev_or_hold"]]
    sign = clustered_mean(sign_rows, value_key="sign_hit_strict")
    spearman = _clustered_spearman(states)
    state_prec = clustered_ratio(states, success_pred=lambda r: r["realized_bad"], denom_pred=lambda r: r["predict_bad"])
    state_rec = clustered_ratio(states, success_pred=lambda r: r["predict_bad"], denom_pred=lambda r: r["realized_bad"])
    state_spec = clustered_ratio(
        states,
        success_pred=lambda r: not r["predict_bad"],
        denom_pred=lambda r: not r["realized_bad"],
    )

    by_trade: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in states:
        by_trade[row["trade_id"]].append(row)
    trade_rows = []
    for trade in trades:
        rows = by_trade.get(trade["trade_id"], [])
        if not rows:
            continue
        flagged = any(r["predict_bad"] for r in rows)
        lost = not bool(trade.get("won"))
        trade_rows.append(
            {
                "trade_id": trade["trade_id"],
                "internal_game_id": trade.get("internal_game_id"),
                "flagged": flagged,
                "lost": lost,
                "won": not lost,
            }
        )
    n_scored = len(trade_rows)
    tp = sum(1 for r in trade_rows if r["flagged"] and r["lost"])
    fp = sum(1 for r in trade_rows if r["flagged"] and r["won"])
    fn = sum(1 for r in trade_rows if (not r["flagged"]) and r["lost"])
    tn = sum(1 for r in trade_rows if (not r["flagged"]) and r["won"])
    winners = sum(1 for r in trade_rows if r["won"])
    naive = None if not n_scored else winners / n_scored
    crude_acc = None if not n_scored else (tp + tn) / n_scored
    trade_prec = clustered_ratio(trade_rows, success_pred=lambda r: r["lost"], denom_pred=lambda r: r["flagged"])
    trade_rec = clustered_ratio(trade_rows, success_pred=lambda r: r["flagged"], denom_pred=lambda r: r["lost"])
    trade_spec = clustered_ratio(trade_rows, success_pred=lambda r: not r["flagged"], denom_pred=lambda r: r["won"])

    warns = warning_rows(trades, queries)
    warn_rows = []
    for w in warns:
        trade = trade_by_id.get(w["trade_id"]) or {}
        damaged = (not bool(trade.get("won"))) or bool(trade.get("t40"))
        warn_rows.append(
            {
                "trade_id": w["trade_id"],
                "internal_game_id": trade.get("internal_game_id"),
                "available": w["class"] == "WARNING_AVAILABLE",
                "too_late": w["class"] == "WARNING_TOO_LATE",
                "none": w["class"] == "NO_WARNING",
                "damaged": damaged,
                "lost": not bool(trade.get("won")),
            }
        )
    warn_prec = clustered_ratio(warn_rows, success_pred=lambda r: r["damaged"], denom_pred=lambda r: r["available"])
    warn_rec_loss = clustered_ratio(warn_rows, success_pred=lambda r: r["available"], denom_pred=lambda r: r["lost"])
    warn_rec_damage = clustered_ratio(warn_rows, success_pred=lambda r: r["available"], denom_pred=lambda r: r["damaged"])
    return {
        "not_a_single_accuracy": True,
        "label": (
            "Austin outputs a continuous conditional EV, not a binary winner/loser call. "
            "MAE/RMSE/sign/rank are the proper scores. "
            "The ever-EV<0 final-loss table is a crude classifier and is not Austin accuracy. "
            "A dumb always-win rule already equals the discovery win rate."
        ),
        "n_valid_states": len(states),
        "n_trades_scored": n_scored,
        "n_trades_unscored_missing_valid_state": len(trades) - n_scored,
        "mae_cents": mae,
        "rmse_cents": {"observed": rmse_obs, "n": len(states)},
        "sign_accuracy_ev_gt_0_vs_hold_gt_0": {
            **sign,
            "zeros_excluded": len(states) - len(sign_rows),
            "definition": "share of states with EV≠0 and hold≠0 where sign(EV)==sign(hold)",
        },
        "spearman_ev_vs_hold": spearman,
        "state_loss_detection": {
            "definition": "predict bad = EV<0; realized bad = subsequent hold < 0",
            "precision": state_prec,
            "recall": state_rec,
            "specificity": state_spec,
        },
        "crude_final_loss_classifier": {
            "definition": "flag = any valid PRIMARY EV<0; truth = eventual loss. NOT Austin accuracy.",
            "tp_losses_detected": tp,
            "fp_winners_flagged": fp,
            "fn_losses_missed": fn,
            "tn_winners_unflagged": tn,
            "n": n_scored,
            "precision": trade_prec,
            "recall": trade_rec,
            "specificity": trade_spec,
            "classification_accuracy": crude_acc,
            "naive_always_win_accuracy": naive,
            "accuracy_minus_naive": None if crude_acc is None or naive is None else crude_acc - naive,
        },
        "warning_before_damage": {
            "definition": "AVAILABLE warning = first negative EV while price>42 and T40 not already. damaged = eventual loss or T40.",
            "precision_available_for_damage": warn_prec,
            "recall_available_among_losses": warn_rec_loss,
            "recall_available_among_damaged": warn_rec_damage,
            "n_available": sum(1 for r in warn_rows if r["available"]),
            "n_too_late": sum(1 for r in warn_rows if r["too_late"]),
            "n_none": sum(1 for r in warn_rows if r["none"]),
            "n_lost": sum(1 for r in warn_rows if r["lost"]),
            "n_damaged": sum(1 for r in warn_rows if r["damaged"]),
        },
    }


def build_interpretation(experiment_id: str) -> dict[str, Any]:
    experiment_id = assert_experiment_id(experiment_id)
    trades = list(load_cohort(experiment_id, "DISCOVERY")["trades"])
    queries = load_discovery_queries(experiment_id)
    cal, cal_status = calibration_rows(queries)
    return {
        "suite_id": SUITE_ID,
        "experiment_id": experiment_id,
        "slice": SLICE_BY_EXPERIMENT[experiment_id],
        "n_lock": N_A if experiment_id == EXPERIMENT_A else N_B,
        "cohort": "DISCOVERY",
        "policy_status": "UNFROZEN",
        "confirmation_result": "NOT RUN",
        "bootstrap": {"cluster": "internal_game_id", "seed": BOOTSTRAP_SEED, "B": BOOTSTRAP_B},
        "coverage": coverage_audit(trades, queries),
        "warning": warning_denominators(trades, queries),
        "ordering": ordering_audit(trades, queries),
        "scoring": scoring_audit(trades, queries),
        "calibration": {"status": cal_status, "table": cal},
        "first_negative": first_negative_audit(trades, queries),
        "submits": False,
        "note": "Discovery interpretation only. No query_match. No POLICY_FREEZE. No confirmation.",
    }


def render_interpretation(payload: dict[str, Any]) -> str:
    cov = payload["coverage"]
    warn = payload["warning"]
    ord_ = payload["ordering"]
    fn = {k: v for k, v in payload["first_negative"].items() if k != "rows"}
    ev = ord_["state_ev_ordering"]
    det = ord_["state_deterioration_ordering"]
    sc = payload["scoring"]
    crude = sc["crude_final_loss_classifier"]
    lines = [
        f"# DISCOVERY INTERPRETATION AUDIT · {payload['experiment_id']}",
        "",
        f"slice={payload['slice']} locked N={payload['n_lock']} cohort=DISCOVERY",
        "POLICY STATUS = UNFROZEN",
        "CONFIRMATION = NOT RUN",
        "No feature / PCA / K / EV / policy / schedule / cohort change.",
        "",
        "## 1. Coverage",
        "",
        f"trades={cov['n_trades']} primary={cov['n_primary']} valid_states={cov['n_valid_ordering_states']} per_trade={cov['valid_states_per_trade']:.2f}",
        f"complete/partial/unavailable={cov['path_complete']}/{cov['path_partial']}/{cov['path_unavailable']}",
        f"PRIMARY PRE_80={cov['primary_query_mode']['PRE_80']} POST_80={cov['primary_query_mode']['POST_80']}",
        f"PRE_80 wall_before_entry={cov['primary_pre80_wall_before_entry']} when-entry median_sec={cov['primary_pre80_when_minus_entry_sec']['median']}",
        f"reasons={cov['primary_reason']}",
        cov["diagnosis"],
        "",
        "## 2. Warning denominators",
        "",
        warn["label"],
        f"AVAILABLE={warn['n_WARNING_AVAILABLE']} TOO_LATE={warn['n_WARNING_TOO_LATE']} NONE={warn['n_NO_WARNING']} PATH_UNAVAILABLE={warn['n_PATH_UNAVAILABLE']}",
        f"median_warning_available n={warn['median_warning_available']['n']} median={warn['median_warning_available']['median']}",
        f"median_warning_too_late n={warn['median_warning_too_late']['n']} median={warn['median_warning_too_late']['median']}",
        f"median_first_negative_to_T40 n={warn['median_first_negative_to_T40']['n']} median={warn['median_first_negative_to_T40']['median']}",
        f"median_first_negative_to_worst_price n={warn['median_first_negative_to_worst_price']['n']} median={warn['median_first_negative_to_worst_price']['median']}",
        f"median_first_negative_to_settlement n={warn['median_first_negative_to_settlement']['n']} median={warn['median_first_negative_to_settlement']['median']}",
        "Missing is not converted to zero.",
        "",
        "## 3–4. Game-clustered ordering",
        "",
        f"EV ordering observed Δ={ev.get('observed_delta')} CI={ev.get('ci')} excludes_zero={ev.get('excludes_zero')} status={ev.get('status')}",
        f"  n_pos={ev.get('n_positive')} n_neg={ev.get('n_negative')} n_games={ev.get('n_games')}",
        f"deterioration ordering observed Δ={det.get('observed_delta')} CI={det.get('ci')} excludes_zero={det.get('excludes_zero')} status={det.get('status')}",
        f"  n_pos={det.get('n_positive')} n_neg={det.get('n_negative')} n_games={det.get('n_games')}",
        f"trade first-valid checkpoint {ord_['trade_first_valid_checkpoint'].get('status')} Δ={ord_['trade_first_valid_checkpoint'].get('observed_delta')} CI={ord_['trade_first_valid_checkpoint'].get('ci')}",
        f"trade ever-negative vs settlement hold {ord_['trade_ever_negative_vs_settlement_hold'].get('status')} Δ={ord_['trade_ever_negative_vs_settlement_hold'].get('observed_delta')} CI={ord_['trade_ever_negative_vs_settlement_hold'].get('ci')}",
        "",
        "## 5. Scoring — not a single accuracy",
        "",
        sc["label"],
        f"n_valid_states={sc['n_valid_states']} n_trades_scored={sc['n_trades_scored']} missing_valid_state={sc['n_trades_unscored_missing_valid_state']}",
        f"MAE ¢ observed={sc['mae_cents'].get('observed')} CI={sc['mae_cents'].get('ci')} n_games={sc['mae_cents'].get('n_games')}",
        f"RMSE ¢ observed={sc['rmse_cents'].get('observed')}",
        f"sign accuracy (EV>0 vs hold>0, zeros excluded) observed={sc['sign_accuracy_ev_gt_0_vs_hold_gt_0'].get('observed')} CI={sc['sign_accuracy_ev_gt_0_vs_hold_gt_0'].get('ci')} zeros_excluded={sc['sign_accuracy_ev_gt_0_vs_hold_gt_0'].get('zeros_excluded')}",
        f"Spearman EV vs hold observed={sc['spearman_ev_vs_hold'].get('observed')} CI={sc['spearman_ev_vs_hold'].get('ci')} excludes_zero={sc['spearman_ev_vs_hold'].get('excludes_zero')}",
        f"state loss-detection precision={sc['state_loss_detection']['precision'].get('observed')} recall={sc['state_loss_detection']['recall'].get('observed')} specificity={sc['state_loss_detection']['specificity'].get('observed')}",
        f"crude ever-EV<0 final-loss classifier (NOT Austin accuracy): TP={crude['tp_losses_detected']} FP={crude['fp_winners_flagged']} FN={crude['fn_losses_missed']} TN={crude['tn_winners_unflagged']}",
        f"  precision={crude['precision'].get('observed')} CI={crude['precision'].get('ci')} recall={crude['recall'].get('observed')} specificity={crude['specificity'].get('observed')}",
        f"  classification_accuracy={crude['classification_accuracy']} naive_always_win={crude['naive_always_win_accuracy']} minus_naive={crude['accuracy_minus_naive']}",
        f"warning-before-damage precision={sc['warning_before_damage']['precision_available_for_damage'].get('observed')} recall_among_losses={sc['warning_before_damage']['recall_available_among_losses'].get('observed')}",
        "",
        "## 6. Calibration",
        "",
        f"status={payload['calibration']['status']}",
        str(payload["calibration"]["table"]),
        "",
        "## 7–8. First-negative trades (descriptive, not a policy)",
        "",
        str(fn),
        "",
        "TEMPORARY vs PERSISTENT is a description of later Austin EV sign. It is not a freeze candidate.",
        "",
        "CONFIRMATION NOT RUN. POLICY UNFROZEN. No winner.",
    ]
    return "\n".join(lines) + "\n"


def persist_interpretation(experiment_id: str, payload: dict[str, Any], text: str) -> None:
    root = experiment_dir(experiment_id)
    folder = root / "discovery"
    folder.mkdir(parents=True, exist_ok=True)
    slim = dict(payload)
    first = dict(slim.get("first_negative") or {})
    rows = first.pop("rows", [])
    slim["first_negative"] = first
    write_json(folder / "interpretation.json", slim)
    write_json(root / "interpretation.json", slim)
    if rows:
        path = folder / "first_negative_trades.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        with (root / "first_negative_trades.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    (folder / "INTERPRETATION.md").write_text(text, encoding="utf-8")
    (root / "INTERPRETATION.md").write_text(text, encoding="utf-8")


def stage_interpret(experiment_id: str) -> dict[str, Any]:
    experiment_id = assert_experiment_id(experiment_id)
    if (experiment_dir(experiment_id) / "POLICY_FREEZE.json").is_file():
        raise AustinError("LOCK_MISMATCH", "experiment-local POLICY_FREEZE.json is forbidden")
    if (experiment_dir(experiment_id) / "confirmation" / "statistics.json").is_file():
        raise AustinError("LOCK_MISMATCH", "interpretation refuses to run after confirmation artifacts")
    payload = build_interpretation(experiment_id)
    text = render_interpretation(payload)
    persist_interpretation(experiment_id, payload, text)
    print(text, flush=True)
    return {"experiment_id": experiment_id, "policy_status": "UNFROZEN", "confirmation_result": "NOT RUN"}


def render_suite_interpretation(payloads: dict[str, dict[str, Any]]) -> str:
    a = payloads[EXPERIMENT_A]
    b = payloads[EXPERIMENT_B]
    lines = [
        "# DISCOVERY INTERPRETATION AUDIT · SUITE",
        "",
        f"Suite `{SUITE_ID}`. POLICY STATUS = UNFROZEN. CONFIRMATION A = NOT RUN. CONFIRMATION B = NOT RUN.",
        "No freeze. No policy selection. No confirmation spend.",
        "",
        "## Answers",
        "",
        "### 1. Why H2_1 has 117 valid states and 0 complete paths",
        "",
        b["coverage"]["diagnosis"],
        f"A: valid={a['coverage']['n_valid_ordering_states']} per_trade={a['coverage']['valid_states_per_trade']:.2f} complete={a['coverage']['path_complete']} PRE_80_primary={a['coverage']['primary_query_mode']['PRE_80']}",
        f"B: valid={b['coverage']['n_valid_ordering_states']} per_trade={b['coverage']['valid_states_per_trade']:.2f} complete={b['coverage']['path_complete']} PRE_80_primary={b['coverage']['primary_query_mode']['PRE_80']}",
        "H2_1 starts later, so fewer PRIMARY clocks remain, and a much larger share of those clocks have PBP wall time still before asked-six entry. That is alignment, not a missing warehouse.",
        "",
        "### 2. Warning median when AVAILABLE=0",
        "",
        b["warning"]["label"],
        f"B median_warning_available n={b['warning']['median_warning_available']['n']} median={b['warning']['median_warning_available']['median']}",
        f"B median_warning_too_late n={b['warning']['median_warning_too_late']['n']} median={b['warning']['median_warning_too_late']['median']}",
        f"B median_first_negative_to_settlement n={b['warning']['median_first_negative_to_settlement']['n']} median={b['warning']['median_first_negative_to_settlement']['median']}",
        "",
        "### 3–4. Clustered ordering",
        "",
        f"A EV {a['ordering']['state_ev_ordering']['status']} Δ={a['ordering']['state_ev_ordering']['observed_delta']} CI={a['ordering']['state_ev_ordering']['ci']}",
        f"A deterioration {a['ordering']['state_deterioration_ordering']['status']} Δ={a['ordering']['state_deterioration_ordering']['observed_delta']} CI={a['ordering']['state_deterioration_ordering']['ci']}",
        f"B EV {b['ordering']['state_ev_ordering']['status']} Δ={b['ordering']['state_ev_ordering']['observed_delta']} CI={b['ordering']['state_ev_ordering']['ci']}",
        f"B deterioration {b['ordering']['state_deterioration_ordering']['status']} Δ={b['ordering']['state_deterioration_ordering']['observed_delta']} CI={b['ordering']['state_deterioration_ordering']['ci']}",
        "",
        "### 5. Scoring — not one Austin accuracy",
        "",
        a["scoring"]["label"],
        f"A MAE={a['scoring']['mae_cents'].get('observed')} CI={a['scoring']['mae_cents'].get('ci')} RMSE={a['scoring']['rmse_cents'].get('observed')} sign={a['scoring']['sign_accuracy_ev_gt_0_vs_hold_gt_0'].get('observed')} Spearman={a['scoring']['spearman_ev_vs_hold'].get('observed')}",
        f"A crude ever-EV<0 acc={a['scoring']['crude_final_loss_classifier']['classification_accuracy']} naive_always_win={a['scoring']['crude_final_loss_classifier']['naive_always_win_accuracy']} minus_naive={a['scoring']['crude_final_loss_classifier']['accuracy_minus_naive']} prec={a['scoring']['crude_final_loss_classifier']['precision'].get('observed')} rec={a['scoring']['crude_final_loss_classifier']['recall'].get('observed')}",
        f"B MAE={b['scoring']['mae_cents'].get('observed')} CI={b['scoring']['mae_cents'].get('ci')} RMSE={b['scoring']['rmse_cents'].get('observed')} sign={b['scoring']['sign_accuracy_ev_gt_0_vs_hold_gt_0'].get('observed')} Spearman={b['scoring']['spearman_ev_vs_hold'].get('observed')}",
        f"B crude ever-EV<0 acc={b['scoring']['crude_final_loss_classifier']['classification_accuracy']} naive_always_win={b['scoring']['crude_final_loss_classifier']['naive_always_win_accuracy']} minus_naive={b['scoring']['crude_final_loss_classifier']['accuracy_minus_naive']} prec={b['scoring']['crude_final_loss_classifier']['precision'].get('observed')} rec={b['scoring']['crude_final_loss_classifier']['recall'].get('observed')}",
        f"A warning-before-damage recall_losses={a['scoring']['warning_before_damage']['recall_available_among_losses'].get('observed')} B={b['scoring']['warning_before_damage']['recall_available_among_losses'].get('observed')}",
        "",
        "### 6. H2_1 calibration",
        "",
        f"status={b['calibration']['status']}",
        str(b["calibration"]["table"]),
        "",
        "### 6–7. First-negative persistence (descriptive)",
        "",
        f"A first-neg n={a['first_negative']['n_first_negative_trades']} win={a['first_negative']['n_eventually_win']} lose={a['first_negative']['n_eventually_lose']} classes={a['first_negative']['deterioration_class']}",
        f"B first-neg n={b['first_negative']['n_first_negative_trades']} win={b['first_negative']['n_eventually_win']} lose={b['first_negative']['n_eventually_lose']} classes={b['first_negative']['deterioration_class']}",
        "",
        "Austin can mark a worse state. It does not yet separate transient from terminal deterioration well enough for an exit rule.",
        "",
        "DISCOVERY INTERPRETATION COMPLETE",
        "POLICY STATUS = UNFROZEN",
        "CONFIRMATION A = NOT RUN",
        "CONFIRMATION B = NOT RUN",
        "NEXT REQUIRED ACTION = HUMAN SELECTS EXACTLY ONE PRE-REGISTERED POLICY OR NONE",
    ]
    return "\n".join(lines) + "\n"


def interpret_suite() -> dict[str, Any]:
    payloads = {eid: build_interpretation(eid) for eid in MEMBERS}
    for eid, payload in payloads.items():
        persist_interpretation(eid, payload, render_interpretation(payload))
    text = render_suite_interpretation(payloads)
    from roller.austin.paths import experiments_root

    (experiments_root() / "INTERPRETATION_AUDIT.md").write_text(text, encoding="utf-8")
    print(text, flush=True)
    return {"suite_id": SUITE_ID, "policy_status": "UNFROZEN", "confirmation_result": "NOT RUN"}
