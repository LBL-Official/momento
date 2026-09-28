"""Trade-level economics and game-clustered bootstrap. Checkpoints are not bets."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from roller.austin.experiments.ids import BOOTSTRAP_B, BOOTSTRAP_SEED
from roller.austin.paths import experiment_dir
from roller.austin.store import write_json
from roller.state.clock import elapsed_game_seconds


def _nums(values: list[Any]) -> list[float]:
    out = []
    for value in values:
        if value is None or value == "":
            continue
        try:
            out.append(float(value))
        except (TypeError, ValueError):
            continue
    return out


def summarize_pnl(pnls: list[float]) -> dict[str, Any]:
    if not pnls:
        return {
            "n": 0,
            "mean": None,
            "median": None,
            "ev_cents": None,
            "std": None,
            "p10": None,
            "p25": None,
            "p75": None,
            "p90": None,
            "min": None,
            "max": None,
            "total": None,
        }
    arr = np.asarray(pnls, dtype=float)
    return {
        "n": int(len(arr)),
        "mean": float(arr.mean()),
        "median": float(np.median(arr)),
        "ev_cents": float(arr.mean()),
        "std": float(arr.std(ddof=1)) if len(arr) > 1 else 0.0,
        "p10": float(np.quantile(arr, 0.10)),
        "p25": float(np.quantile(arr, 0.25)),
        "p75": float(np.quantile(arr, 0.75)),
        "p90": float(np.quantile(arr, 0.90)),
        "min": float(arr.min()),
        "max": float(arr.max()),
        "total": float(arr.sum()),
    }


def max_drawdown(pnls: list[float]) -> float | None:
    if not pnls:
        return None
    equity = np.cumsum(np.asarray(pnls, dtype=float))
    peak = np.maximum.accumulate(equity)
    dd = equity - peak
    return float(dd.min())


def clustered_delta_ci(
    rows: list[dict[str, Any]],
    *,
    baseline_key: str,
    policy_key: str,
    cluster_key: str = "internal_game_id",
    seed: int = BOOTSTRAP_SEED,
    draws: int = BOOTSTRAP_B,
) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(cluster_key) or row.get("trade_id"))].append(row)
    keys = sorted(groups)
    rng = np.random.default_rng(seed)
    deltas = []
    for _ in range(int(draws)):
        pick = rng.choice(len(keys), size=len(keys), replace=True)
        base = []
        pol = []
        for idx in pick:
            for row in groups[keys[int(idx)]]:
                if row.get(baseline_key) is None or row.get(policy_key) is None:
                    continue
                base.append(float(row[baseline_key]))
                pol.append(float(row[policy_key]))
        if not base:
            continue
        deltas.append(float(np.mean(pol) - np.mean(base)))
    if not deltas:
        return {"method": "clustered_bootstrap", "cluster": "internal_game_id", "seed": seed, "B": draws, "ci": [None, None]}
    return {
        "method": "clustered_bootstrap",
        "cluster": "internal_game_id",
        "seed": seed,
        "B": draws,
        "mean_delta": float(np.mean(deltas)),
        "ci": [float(np.quantile(deltas, 0.025)), float(np.quantile(deltas, 0.975))],
        "n_games": len(keys),
        "n_trades": len(rows),
        "n_state_observations": None,
    }


def clustered_mean_diff(
    rows: list[dict[str, Any]],
    *,
    value_key: str,
    positive_pred,
    negative_pred,
    cluster_key: str = "internal_game_id",
    seed: int = BOOTSTRAP_SEED,
    draws: int = BOOTSTRAP_B,
) -> dict[str, Any]:
    """Game-clustered CI for mean(value|positive) − mean(value|negative)."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get(value_key) is None:
            continue
        groups[str(row.get(cluster_key) or row.get("trade_id"))].append(row)
    keys = sorted(groups)
    rng = np.random.default_rng(seed)
    deltas = []
    for _ in range(int(draws)):
        if not keys:
            break
        pick = rng.choice(len(keys), size=len(keys), replace=True)
        pos = []
        neg = []
        for idx in pick:
            for row in groups[keys[int(idx)]]:
                val = float(row[value_key])
                if positive_pred(row):
                    pos.append(val)
                elif negative_pred(row):
                    neg.append(val)
        if not pos or not neg:
            continue
        deltas.append(float(np.mean(pos) - np.mean(neg)))
    n_pos = sum(1 for row in rows if row.get(value_key) is not None and positive_pred(row))
    n_neg = sum(1 for row in rows if row.get(value_key) is not None and negative_pred(row))
    payload = {
        "method": "clustered_bootstrap",
        "cluster": "internal_game_id",
        "seed": seed,
        "B": draws,
        "contrast": "mean(positive) - mean(negative)",
        "n_games": len(keys),
        "n_rows": len(rows),
        "n_positive": n_pos,
        "n_negative": n_neg,
        "observed_delta": None,
        "mean_delta": None,
        "ci": [None, None],
        "excludes_zero": False,
    }
    pos_obs = [float(r[value_key]) for r in rows if r.get(value_key) is not None and positive_pred(r)]
    neg_obs = [float(r[value_key]) for r in rows if r.get(value_key) is not None and negative_pred(r)]
    if pos_obs and neg_obs:
        payload["observed_delta"] = float(np.mean(pos_obs) - np.mean(neg_obs))
    if not deltas:
        return payload
    lo, hi = float(np.quantile(deltas, 0.025)), float(np.quantile(deltas, 0.975))
    payload["mean_delta"] = float(np.mean(deltas))
    payload["ci"] = [lo, hi]
    payload["excludes_zero"] = lo > 0 or hi < 0
    return payload


def clustered_mean(
    rows: list[dict[str, Any]],
    *,
    value_key: str,
    cluster_key: str = "internal_game_id",
    seed: int = BOOTSTRAP_SEED,
    draws: int = BOOTSTRAP_B,
) -> dict[str, Any]:
    groups: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row.get(value_key) is None:
            continue
        groups[str(row.get(cluster_key) or row.get("trade_id"))].append(float(row[value_key]))
    keys = sorted(groups)
    observed = [v for vals in groups.values() for v in vals]
    payload = {
        "method": "clustered_bootstrap",
        "cluster": "internal_game_id",
        "seed": seed,
        "B": draws,
        "n_games": len(keys),
        "n_rows": len(observed),
        "observed": None if not observed else float(np.mean(observed)),
        "mean": None,
        "ci": [None, None],
    }
    if not keys:
        return payload
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(int(draws)):
        pick = rng.choice(len(keys), size=len(keys), replace=True)
        vals = [v for idx in pick for v in groups[keys[int(idx)]]]
        if vals:
            means.append(float(np.mean(vals)))
    if means:
        payload["mean"] = float(np.mean(means))
        payload["ci"] = [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]
    return payload


def clustered_ratio(
    rows: list[dict[str, Any]],
    *,
    success_pred,
    denom_pred,
    cluster_key: str = "internal_game_id",
    seed: int = BOOTSTRAP_SEED,
    draws: int = BOOTSTRAP_B,
) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(cluster_key) or row.get("trade_id"))].append(row)
    keys = sorted(groups)
    succ = sum(1 for r in rows if denom_pred(r) and success_pred(r))
    den = sum(1 for r in rows if denom_pred(r))
    payload = {
        "method": "clustered_bootstrap",
        "cluster": "internal_game_id",
        "seed": seed,
        "B": draws,
        "n_games": len(keys),
        "n_success": succ,
        "n_denom": den,
        "observed": None if not den else succ / den,
        "mean": None,
        "ci": [None, None],
    }
    if not keys:
        return payload
    rng = np.random.default_rng(seed)
    rates = []
    for _ in range(int(draws)):
        pick = rng.choice(len(keys), size=len(keys), replace=True)
        s = d = 0
        for idx in pick:
            for row in groups[keys[int(idx)]]:
                if denom_pred(row):
                    d += 1
                    if success_pred(row):
                        s += 1
        if d:
            rates.append(s / d)
    if rates:
        payload["mean"] = float(np.mean(rates))
        payload["ci"] = [float(np.quantile(rates, 0.025)), float(np.quantile(rates, 0.975))]
    return payload


def _elapsed(period: Any, remaining: Any) -> int | None:
    return elapsed_game_seconds(period, remaining, sport="NCAAB")


def _minutes_between(start: dict[str, Any] | None, end: dict[str, Any] | None) -> float | None:
    if start is None or end is None:
        return None
    a = _elapsed(start.get("period"), start.get("game_clock_remaining"))
    b = _elapsed(end.get("period"), end.get("game_clock_remaining"))
    if a is None or b is None:
        return None
    return max(0.0, (b - a) / 60.0)


def warning_rows(trades: list[dict[str, Any]], queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_trade: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in queries:
        by_trade[row["trade_id"]].append(row)
    out = []
    for trade in trades:
        rows = [r for r in by_trade.get(trade["trade_id"], []) if r.get("primary")]
        first_neg = next((r for r in rows if r.get("conditional_ev_cents") is not None and float(r["conditional_ev_cents"]) < 0), None)
        first_ci = next(
            (
                r
                for r in rows
                if r.get("conditional_ev_cents") is not None
                and float(r["conditional_ev_cents"]) < 0
                and r.get("ci_upper_cents") is not None
                and float(r["ci_upper_cents"]) < 0
            ),
            None,
        )
        later = []
        if first_neg is not None:
            later = [r for r in rows if (r.get("timestamp_utc") or "") >= (first_neg.get("timestamp_utc") or "")]
        prices = [int(r["current_price_cents"]) for r in later if r.get("current_price_cents") is not None]
        worst = None if not prices else min(prices)
        worst_row = None
        if worst is not None:
            worst_row = next((r for r in later if r.get("current_price_cents") is not None and int(r["current_price_cents"]) == worst), None)
        t40_row = next((r for r in later if r.get("t40_already") or r.get("hit_40_after")), None)
        settle_row = rows[-1] if rows else None
        price0 = None if first_neg is None else first_neg.get("current_price_cents")
        late = False
        if first_neg is not None and price0 is not None and float(price0) <= 42:
            late = True
        if first_neg is not None and first_neg.get("t40_already"):
            late = True
        if not rows:
            klass = "PATH_UNAVAILABLE"
        elif first_neg is None:
            klass = "NO_WARNING"
        elif late:
            klass = "WARNING_TOO_LATE"
        else:
            klass = "WARNING_AVAILABLE"
        adverse = None
        if price0 is not None and worst is not None:
            adverse = max(0, int(price0) - int(worst))
        settle_minutes = _minutes_between(first_neg, settle_row)
        if (
            first_neg is not None
            and first_neg is settle_row
            and first_neg.get("game_clock_remaining") is not None
        ):
            settle_minutes = float(first_neg["game_clock_remaining"]) / 60.0
        out.append(
            {
                "trade_id": trade["trade_id"],
                "won": trade.get("won"),
                "class": klass,
                "first_negative_ev_checkpoint": None if first_neg is None else first_neg.get("timestamp_utc"),
                "first_ci_confirmed_negative_checkpoint": None if first_ci is None else first_ci.get("timestamp_utc"),
                "price_at_first_negative_ev": price0,
                "clock_at_first_negative_ev": None if first_neg is None else first_neg.get("game_clock_remaining"),
                "period_at_first_negative_ev": None if first_neg is None else first_neg.get("period"),
                "warning_to_t40_game_clock_minutes": _minutes_between(first_neg, t40_row),
                "warning_to_worst_price_game_clock_minutes": _minutes_between(first_neg, worst_row),
                "warning_to_settlement_game_clock_minutes": settle_minutes,
                "adverse_price_movement_remaining": adverse,
                "worst_later_price": worst,
                "pnl_hold_after_first_negative": None if first_neg is None else first_neg.get("pnl_hold_after_t"),
                "warning_unavailable_not_zero": klass in {"NO_WARNING", "PATH_UNAVAILABLE"},
            }
        )
    return out


def signal_rows(queries: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [
        r
        for r in queries
        if r.get("primary") and r.get("conditional_ev_cents") is not None and r.get("pnl_hold_after_t") is not None
    ]
    neg = [r for r in valid if float(r["conditional_ev_cents"]) < 0]
    pos = [r for r in valid if float(r["conditional_ev_cents"]) >= 0]
    det = [r for r in valid if r.get("ev_change") is not None]
    det_down = [r for r in det if float(r["ev_change"]) <= -8]
    det_flat = [r for r in det if float(r["ev_change"]) > -8]
    first_neg_hold = []
    by_trade = defaultdict(list)
    for row in valid:
        by_trade[row["trade_id"]].append(row)
    for rows in by_trade.values():
        first = next((r for r in rows if float(r["conditional_ev_cents"]) < 0), None)
        if first is not None:
            first_neg_hold.append(float(first["pnl_hold_after_t"]))
    return {
        "n_valid_states": len(valid),
        "negative_ev": {"n": len(neg), "mean_hold": None if not neg else float(np.mean([float(r["pnl_hold_after_t"]) for r in neg]))},
        "nonnegative_ev": {"n": len(pos), "mean_hold": None if not pos else float(np.mean([float(r["pnl_hold_after_t"]) for r in pos]))},
        "deterioration_le_minus_8": {
            "n": len(det_down),
            "mean_hold": None if not det_down else float(np.mean([float(r["pnl_hold_after_t"]) for r in det_down])),
        },
        "deterioration_gt_minus_8": {
            "n": len(det_flat),
            "mean_hold": None if not det_flat else float(np.mean([float(r["pnl_hold_after_t"]) for r in det_flat])),
        },
        "first_negative_ev_subsequent_hold": summarize_pnl(first_neg_hold),
        "ordering_status": (
            "SUPPORTED"
            if neg and pos and (np.mean([float(r["pnl_hold_after_t"]) for r in neg]) < np.mean([float(r["pnl_hold_after_t"]) for r in pos]))
            else ("INSUFFICIENT_SAMPLE" if not neg or not pos else "NOT_SUPPORTED")
        ),
    }


def equity_rows(trades: list[dict[str, Any]], policy_ledger: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(trades, key=lambda t: str(t.get("entry_timestamp") or ""))
    hold_cum = 0.0
    policy_cum: dict[str, float] = defaultdict(float)
    out = []
    by_trade_policy = {(r["trade_id"], r["policy_id"]): r for r in policy_ledger}
    for trade in ordered:
        hold = next((r for r in policy_ledger if r["trade_id"] == trade["trade_id"] and r.get("baseline_hold_pnl") is not None), None)
        if hold is None:
            continue
        hold_cum += float(hold["baseline_hold_pnl"])
        row = {
            "trade_id": trade["trade_id"],
            "entry_timestamp": trade.get("entry_timestamp"),
            "baseline_hold_equity": hold_cum,
        }
        for policy_id in sorted({r["policy_id"] for r in policy_ledger}):
            item = by_trade_policy.get((trade["trade_id"], policy_id))
            if item is None or item.get("hypothetical_pnl_b") is None:
                continue
            policy_cum[policy_id] += float(item["hypothetical_pnl_b"])
            row[f"{policy_id}_scenario_b_equity"] = policy_cum[policy_id]
        out.append(row)
    return out


def calibration_rows(queries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    valid = [
        r
        for r in queries
        if r.get("primary") and r.get("conditional_ev_cents") is not None and r.get("pnl_hold_after_t") is not None
    ]
    bands = [(-1e9, -10), (-10, 0), (0, 5), (5, 10), (10, 1e9)]
    labels = ["< -10¢", "-10 to 0¢", "0 to +5¢", "+5 to +10¢", "> +10¢"]
    table = []
    for (lo, hi), label in zip(bands, labels):
        subset = [r for r in valid if lo <= float(r["conditional_ev_cents"]) < hi]
        realized = _nums([r["pnl_hold_after_t"] for r in subset])
        pred = _nums([r["conditional_ev_cents"] for r in subset])
        table.append(
            {
                "band": label,
                "n": len(subset),
                "mean_predicted_ev": None if not pred else float(np.mean(pred)),
                "mean_realized_hold": None if not realized else float(np.mean(realized)),
                "median_realized_hold": None if not realized else float(np.median(realized)),
            }
        )
    means = [row["mean_realized_hold"] for row in table if row["n"] >= 5 and row["mean_realized_hold"] is not None]
    status = "INSUFFICIENT_SAMPLE"
    if len(means) >= 3 and means[0] < means[-1]:
        status = "SEPARATED"
    return table, status


def path_coverage(trades: list[dict[str, Any]], queries: list[dict[str, Any]]) -> dict[str, Any]:
    by_trade = defaultdict(list)
    for row in queries:
        by_trade[row["trade_id"]].append(row)
    complete = partial = unavailable = 0
    for trade in trades:
        rows = by_trade.get(trade["trade_id"], [])
        primary = [r for r in rows if r.get("primary")]
        if not primary:
            unavailable += 1
        elif any(r.get("availability_status") == "VALUE" for r in primary):
            if any(r.get("availability_status") != "VALUE" for r in primary):
                partial += 1
            else:
                complete += 1
        else:
            unavailable += 1
    return {
        "N_trades": len(trades),
        "N_path_complete": complete,
        "N_path_partial": partial,
        "N_path_unavailable": unavailable,
        "N_primary_grid_rows": sum(1 for r in queries if r.get("primary")),
        "N_valid_Austin_rows": sum(1 for r in queries if r.get("availability_status") == "VALUE"),
        "N_knn_observations": 48752,
        "N_games": len({t.get("internal_game_id") for t in trades}),
        "N_state_observations": len(queries),
    }


def hedge_resolution(queries: list[dict[str, Any]]) -> dict[str, Any]:
    diags = [r for r in queries if r.get("role") == "DIAGNOSTIC_EVENT"]
    by_trade = defaultdict(dict)
    for row in diags:
        by_trade[row["trade_id"]][int(row.get("diagnostic_print") or 0)] = row
    n42 = n41 = same = without = 0
    for marks in by_trade.values():
        if 42 in marks:
            n42 += 1
        if 41 in marks:
            n41 += 1
        if 42 in marks and 41 in marks:
            if marks[42].get("timestamp_utc") == marks[41].get("timestamp_utc"):
                same += 1
            elif marks[42].get("timestamp_utc") != marks[41].get("timestamp_utc"):
                without += 1
        elif 42 in marks and 41 not in marks:
            without += 1
    return {
        "TRIGGER_RESOLUTION": "1m_close",
        "n_first_le_42": n42,
        "n_first_le_41": n41,
        "n_42_without_41": without,
        "n_same_bar_42_and_41": same,
        "role": "DIAGNOSTIC_EVENTS",
    }


def build_statistics(
    *,
    experiment_id: str,
    cohort: str,
    trades: list[dict[str, Any]],
    queries: list[dict[str, Any]],
    policy_ledger: list[dict[str, Any]],
    interventions: list[dict[str, Any]],
) -> dict[str, Any]:
    hold = [float(r["baseline_hold_pnl"]) for r in policy_ledger if r.get("baseline_hold_pnl") is not None]
    # one row per trade per policy — collapse to first policy for baseline
    seen = set()
    hold_unique = []
    hyp_by_policy: dict[str, list[float]] = defaultdict(list)
    delta_rows = []
    for row in policy_ledger:
        tid = row["trade_id"]
        if tid not in seen:
            seen.add(tid)
            if row.get("baseline_hold_pnl") is not None:
                hold_unique.append(float(row["baseline_hold_pnl"]))
        if row.get("hypothetical_pnl_b") is not None:
            hyp_by_policy[row["policy_id"]].append(float(row["hypothetical_pnl_b"]))
        delta_rows.append(row)
    coverage = path_coverage(trades, queries)
    cal, cal_status = calibration_rows(queries)
    warnings = warning_rows(trades, queries)
    warn_vals = _nums([w["warning_to_settlement_game_clock_minutes"] for w in warnings if w["class"] in {"WARNING_AVAILABLE", "WARNING_TOO_LATE"}])
    warn_losers = _nums(
        [w["warning_to_settlement_game_clock_minutes"] for w in warnings if w["class"] == "WARNING_AVAILABLE" and not w.get("won")]
    )
    signal = signal_rows(queries)
    policies = {}
    for policy_id, pnls in hyp_by_policy.items():
        subset = [r for r in policy_ledger if r["policy_id"] == policy_id]
        ordered = sorted(subset, key=lambda r: str(r.get("entry_timestamp") or ""))
        hyp_ordered = [float(r["hypothetical_pnl_b"]) for r in ordered if r.get("hypothetical_pnl_b") is not None]
        hold_ordered = [float(r["baseline_hold_pnl"]) for r in ordered if r.get("baseline_hold_pnl") is not None]
        ci = clustered_delta_ci(subset, baseline_key="baseline_hold_pnl", policy_key="hypothetical_pnl_b")
        ci["n_state_observations"] = coverage["N_state_observations"]
        inter = [i for i in interventions if i["policy_id"] == policy_id]
        hyp_sum = summarize_pnl(pnls)
        policies[policy_id] = {
            "baseline_hold": summarize_pnl(hold_unique),
            "policy_hypothetical_b": hyp_sum,
            "delta_mean": None if not hold_unique or not pnls else float(np.mean(pnls) - np.mean(hold_unique)),
            "max_dd_baseline": max_drawdown(hold_ordered),
            "max_dd_policy": max_drawdown(hyp_ordered),
            "p10_policy": hyp_sum.get("p10"),
            "worst_trade": hyp_sum.get("min"),
            "delta_ci": ci,
            "intervention_rate": None if not subset else sum(1 for r in subset if r["intervention"] == "INTERVENE") / len(subset),
            "intervention_count": sum(1 for r in subset if r["intervention"] == "INTERVENE"),
            "winners_abandoned": sum(1 for i in inter if i.get("winner_abandoned")),
            "losses_avoided": sum(1 for i in inter if i.get("loss_avoided")),
            "cents_sacrificed": float(np.nansum([i.get("cents_sacrificed") or 0 for i in inter])),
            "cents_saved": float(np.nansum([i.get("cents_saved") or 0 for i in inter])),
            "median_warning_minutes": None if not warn_vals else float(np.median(warn_vals)),
            "low_support_states": sum(1 for r in queries if r.get("support_status") == "LOW_HISTORICAL_SUPPORT"),
        }
    payload = {
        "experiment_id": experiment_id,
        "cohort": cohort,
        "N_games": coverage["N_games"],
        "N_trades": coverage["N_trades"],
        "N_state_observations": coverage["N_state_observations"],
        "coverage": coverage,
        "baseline_hold": summarize_pnl(hold_unique),
        "calibration": {"status": cal_status, "table": cal},
        "signal": signal,
        "hedge_resolution": hedge_resolution(queries),
        "warning": {
            "n": len(warnings),
            "available": sum(1 for w in warnings if w["class"] == "WARNING_AVAILABLE"),
            "too_late": sum(1 for w in warnings if w["class"] == "WARNING_TOO_LATE"),
            "no_warning": sum(1 for w in warnings if w["class"] == "NO_WARNING"),
            "path_unavailable": sum(1 for w in warnings if w["class"] == "PATH_UNAVAILABLE"),
            "median_minutes": None if not warn_vals else float(np.median(warn_vals)),
            "p25": None if not warn_vals else float(np.quantile(warn_vals, 0.25)),
            "p75": None if not warn_vals else float(np.quantile(warn_vals, 0.75)),
            "median_minutes_losers": None if not warn_losers else float(np.median(warn_losers)),
            "mean_adverse_remaining": None
            if not _nums([w.get("adverse_price_movement_remaining") for w in warnings])
            else float(np.mean(_nums([w.get("adverse_price_movement_remaining") for w in warnings]))),
        },
        "policies": policies,
        "policy_status": "UNFROZEN" if cohort == "DISCOVERY" else "FROZEN",
        "confirmation_result": "NOT RUN" if cohort == "DISCOVERY" else "OBSERVED",
        "equity": equity_rows(trades, policy_ledger),
        "fee_model": "UNAVAILABLE",
        "page3_n280_queried": False,
        "execution": "DISABLED",
        "live_feed": "UNAVAILABLE",
        "submits": False,
    }
    return payload


def persist_statistics(experiment_id: str, cohort: str, payload: dict[str, Any], warnings: list[dict[str, Any]]) -> None:
    root = experiment_dir(experiment_id) / cohort.lower()
    write_json(root / "statistics.json", payload)
    write_json(root / "path_coverage.json", payload["coverage"])
    if cohort == "DISCOVERY":
        write_json(experiment_dir(experiment_id) / "path_coverage.json", payload["coverage"])
        write_json(experiment_dir(experiment_id) / "statistics.json", payload)
    warn_path = root / "warning_time.csv"
    warn_path.parent.mkdir(parents=True, exist_ok=True)
    if warnings:
        with warn_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(warnings[0].keys()))
            writer.writeheader()
            writer.writerows(warnings)
    write_json(root / "calibration.json", payload["calibration"])
    cal_fields = ["band", "n", "mean_predicted_ev", "mean_realized_hold", "median_realized_hold"]
    with (root / "calibration.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=cal_fields)
        writer.writeheader()
        writer.writerows(payload["calibration"]["table"])
    parent = experiment_dir(experiment_id)
    if cohort == "DISCOVERY":
        if warnings:
            with (parent / "warning_time.csv").open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(warnings[0].keys()))
                writer.writeheader()
                writer.writerows(warnings)
        write_json(parent / "calibration.json", payload["calibration"])
        with (parent / "calibration.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=cal_fields)
            writer.writeheader()
            writer.writerows(payload["calibration"]["table"])
        equity = payload.get("equity") or []
        if equity:
            with (root / "equity_curves.csv").open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(equity[0].keys()))
                writer.writeheader()
                writer.writerows(equity)
            with (parent / "equity_curves.csv").open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(equity[0].keys()))
                writer.writeheader()
                writer.writerows(equity)
    if cohort == "CONFIRMATION":
        write_json(parent / "confirmation_statistics.json", payload)
        write_json(parent / "confirmation_path_coverage.json", payload["coverage"])
        with (parent / "confirmation_calibration.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=cal_fields)
            writer.writeheader()
            writer.writerows(payload["calibration"]["table"])
