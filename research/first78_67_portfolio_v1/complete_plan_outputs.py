#!/usr/bin/env python3
"""Fill plan outputs that the first ledger run left unnamed.

Does not change trades.csv. Does not retune 78/67.
"""

from __future__ import annotations

import csv
import json
import math
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

EXP = Path(__file__).resolve().parent
SRC = EXP / "src"
sys.path.insert(0, str(SRC))

from first78.extract import _index_candles, _quality, _read_bars  # noqa: E402
from first78.portfolio import replay  # noqa: E402
from first78.stats import block_bootstrap_equity  # noqa: E402

RUN = EXP / "runs" / "first78_67_20260926T074540Z"
REPO = EXP.parents[1]
NBA_ROOT = REPO / "Backtesting Suite/Data/NBA/2025-2026/warehouse/normalized/nba"
NCAAB_ROOT = REPO / "Backtesting Suite/Data/NCAAB/2025-2026/warehouse/normalized/ncaab"
HOLDOUT = "2026-02-01"


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def candidates_from_trades(trades: list[dict]) -> list[dict]:
    rows = []
    for trade in trades:
        rows.append(
            {
                "game_id": trade["game_id"],
                "contract_id": trade["contract_id"],
                "sport": trade["sport"],
                "signal_ts": int(trade["entry_ts"]),
                "exit_ts": int(trade["exit_ts"]),
                "cash_ts": int(trade["cash_ts"]),
                "exit_reason": trade["exit_reason"],
                "local_day": trade["signal_pacific"][:10],
            }
        )
    return rows


def quantile(values: list[float], frac: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(frac * (len(ordered) - 1)))))
    return ordered[index]


def day_cluster_means(trades: list[dict], draws: int, seed: int) -> dict:
    by_day: dict[str, list[float]] = defaultdict(list)
    for trade in trades:
        by_day[trade["signal_pacific"][:10]].append(int(trade["net_pnl_cents"]) / int(trade["contracts"]))
    days = sorted(by_day)
    observed = [v for day in days for v in by_day[day]]
    obs_mean = sum(observed) / len(observed) if observed else None
    rng = random.Random(seed)
    boots = []
    for _ in range(draws):
        picked = [days[rng.randrange(len(days))] for _ in days]
        sample = [v for day in picked for v in by_day[day]]
        boots.append(sum(sample) / len(sample))
    below = sum(1 for v in boots if v <= 0)
    return {
        "estimand": "mean net cents per contract",
        "cluster": "local signal day",
        "draws": draws,
        "seed": seed,
        "n_days": len(days),
        "n_trades": len(trades),
        "observed_mean": obs_mean,
        "ci90": [quantile(boots, 0.05), quantile(boots, 0.95)],
        "ci95": [quantile(boots, 0.025), quantile(boots, 0.975)],
        "one_sided_p_mean_le_0": (1 + below) / (draws + 1),
        "note": "Day-cluster interval for this historical mean. Not a timing null and not a live-edge probability.",
    }


def holm(pvalues: list[tuple[str, float]]) -> list[dict]:
    ordered = sorted(pvalues, key=lambda item: item[1])
    m = len(ordered)
    adj = []
    running = 0.0
    for i, (name, p) in enumerate(ordered):
        running = max(running, min(1.0, (m - i) * p))
        adj.append({"endpoint": name, "raw_p": p, "holm_p": running})
    return adj


def load_paths(trades: list[dict]) -> dict[str, list[tuple[int, int]]]:
    indexes = {"NBA": _index_candles(NBA_ROOT), "NCAAB": _index_candles(NCAAB_ROOT)}
    out = {}
    for trade in trades:
        path = indexes[trade["sport"]].get(trade["contract_id"])
        if path is None:
            out[trade["trade_id"]] = []
            continue
        bars = _read_bars(path)
        had = False
        kept = []
        entry = int(trade["entry_ts"])
        end = int(trade["exit_ts"])
        for bar in bars:
            if not _quality(bar["bid"], bar["ask"], bar["vol"], had):
                continue
            had = True
            if bar["ts"] < entry or bar["ts"] > end or bar["bid"] is None:
                continue
            kept.append((bar["ts"], bar["bid"] // 100))
        out[trade["trade_id"]] = kept
    return out


def within_game(trades: list[dict], paths: dict[str, list[tuple[int, int]]]) -> None:
    def dist_bin(cents: int) -> str:
        gap = cents - 67
        if gap < 5:
            return "0_to_5pp"
        if gap < 15:
            return "5_to_15pp"
        return "15pp_or_more"

    def time_bin(raw: str) -> str:
        if raw in ("", None):
            return "UNKNOWN"
        try:
            rem = float(raw)
        except ValueError:
            return "UNKNOWN"
        return "under_5min" if rem < 300 else "5min_or_more"

    rows = []
    for trade in trades:
        series = paths.get(trade["trade_id"]) or []
        entry_px = int(trade["observed_entry_close_cents"])
        minutes = None
        if series:
            minutes = (series[-1][0] - series[0][0]) / 60
        rows.append(
            {
                "trade_id": trade["trade_id"],
                "sport": trade["sport"],
                "signal_day": trade["signal_pacific"][:10],
                "distance_bin": dist_bin(entry_px),
                "time_bin": time_bin(trade.get("period_remaining_s") or ""),
                "exit_reason": trade["exit_reason"],
                "stopped": trade["exit_reason"] == "STOP",
                "minutes_to_exit": None if minutes is None else round(minutes, 3),
                "split": "FIT" if trade["signal_pacific"][:10] < HOLDOUT else "LATER_SEGMENT",
            }
        )
    fit = [r for r in rows if r["split"] == "FIT"]
    later = [r for r in rows if r["split"] == "LATER_SEGMENT"]
    rates: dict[tuple[str, str, str], list] = defaultdict(list)
    for row in fit:
        rates[(row["sport"], row["distance_bin"], row["time_bin"])].append(row["stopped"])

    def predict(row: dict) -> tuple[float | None, str]:
        cell = rates.get((row["sport"], row["distance_bin"], row["time_bin"]))
        if not cell or len(cell) < 20:
            return None, "INSUFFICIENT_SAMPLE"
        return sum(1 for flag in cell if flag) / len(cell), "EMPIRICAL_CELL"

    preds = []
    scored = []
    for row in rows:
        p_stop, status = predict(row)
        preds.append({**row, "p_stop_from_fit_cell": p_stop, "prediction_status": status})
        if row["split"] == "LATER_SEGMENT" and p_stop is not None:
            y = 1.0 if row["stopped"] else 0.0
            scored.append((p_stop - y) ** 2)
    brier = None if not scored else sum(scored) / len(scored)
    absorption = []
    for sport in ("NBA", "NCAAB", "COMBINED"):
        group = rows if sport == "COMBINED" else [r for r in rows if r["sport"] == sport]
        n = len(group)
        stops = sum(1 for r in group if r["exit_reason"] == "STOP")
        wins = sum(1 for r in group if r["exit_reason"] == "WIN_SETTLEMENT")
        losses = sum(1 for r in group if r["exit_reason"] == "LOSS_SETTLEMENT")
        absorption.append(
            {
                "sport": sport,
                "n": n,
                "p_stop": None if n == 0 else stops / n,
                "p_win_settlement": None if n == 0 else wins / n,
                "p_loss_settlement": None if n == 0 else losses / n,
                "label": "DEVELOPMENT_ONLY_FULL_SAMPLE",
            }
        )
    times = []
    for reason in ("STOP", "WIN_SETTLEMENT", "LOSS_SETTLEMENT"):
        vals = [r["minutes_to_exit"] for r in rows if r["exit_reason"] == reason and r["minutes_to_exit"] is not None]
        times.append(
            {
                "exit_reason": reason,
                "n": len(vals),
                "median_minutes": None if not vals else quantile(vals, 0.5),
                "resolution": "minute bar, not an exact execution time",
            }
        )
    (RUN / "06_markov_chains" / "within_game_state_definitions.json").write_text(
        json.dumps(
            {
                "status": "DEVELOPMENT_ONLY",
                "deployment_validation": "INCOMPLETE",
                "distance_bins_prespecified": ["0_to_5pp above 67", "5_to_15pp", "15pp_or_more"],
                "time_bins_prespecified": ["under_5min remaining", "5min_or_more", "UNKNOWN"],
                "holdout_cut_local_date": HOLDOUT,
                "note": "Cell rates are fit on the earlier segment and scored on the later segment of the same examined season. This is not an untouched prospective test. Predictions do not filter entries or change size.",
                "later_segment_brier_stop": brier,
                "later_segment_scored_n": len(scored),
                "fit_n": len(fit),
                "later_n": len(later),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    write_csv(RUN / "06_markov_chains" / "within_game_predictions.csv", preds)
    write_csv(RUN / "06_markov_chains" / "absorption_probabilities.csv", absorption)
    write_csv(RUN / "06_markov_chains" / "time_to_exit.csv", times)
    write_csv(
        RUN / "06_markov_chains" / "model_validation.csv",
        [
            {
                "metric": "brier_stop",
                "value": brier,
                "n": len(scored),
                "label": "DEVELOPMENT_ONLY",
                "reason": None if scored else "INSUFFICIENT_LATER_SEGMENT",
            }
        ],
    )


def bid_mark_drawdown(trades: list[dict], events: list[dict], paths: dict[str, list[tuple[int, int]]]) -> dict:
    by_id = {t["trade_id"]: t for t in trades}
    open_ids: set[str] = set()
    cash = 2_000_000
    receivable = 0
    series = []
    missing = 0
    for event in events:
        kind = event["kind"]
        tid = event.get("trade_id") or ""
        if kind == "entry" and tid:
            open_ids.add(tid)
        if kind == "exit" and tid:
            open_ids.discard(tid)
        cash = int(event["cash_cents"])
        receivable = int(event["receivable_cents"])
        ts = int(event["ts"])
        mark = 0
        ok = True
        for open_id in open_ids:
            series_px = paths.get(open_id) or []
            bid = None
            for stamp, px in series_px:
                if stamp <= ts:
                    bid = px
                else:
                    break
            if bid is None:
                ok = False
                break
            mark += int(by_id[open_id]["contracts"]) * bid
        if not ok:
            missing += 1
            continue
        series.append(cash + receivable + mark)
    if not series:
        return {"status": "UNAVAILABLE", "reason": "NO_COMPLETE_MARKS", "missing_events": missing}
    peak = series[0]
    worst = 0.0
    trough = series[0]
    peak_v = series[0]
    for value in series:
        if value > peak:
            peak = value
        if peak > 0:
            dd = 1 - value / peak
            if dd > worst:
                worst = dd
                trough = value
                peak_v = peak
    return {
        "status": "BID_MARKED_GROSS_AT_EVENT_TIMES",
        "points": len(series),
        "events_missing_a_mark": missing,
        "max_drawdown_fraction": worst,
        "peak_equity_cents": peak_v,
        "trough_equity_cents": trough,
        "note": "Mark is the last bid close at or before the event. Not an intraminute path and not a liquidation fill.",
    }


def main() -> None:
    trades = read_csv(RUN / "01_trade_logs" / "trades.csv")
    events = read_csv(RUN / "02_portfolio_logs" / "events.csv")
    cands = candidates_from_trades(trades)

    reverse = replay(cands, reverse_priority=True)
    all_in = replay(cands, fee_inside_allocation=True)
    capacity = []
    for dollars in (10_000, 20_000, 40_000, 100_000):
        book = replay(cands, balance_cents=dollars * 100)
        capacity.append(
            {
                "starting_dollars": dollars,
                "admitted": len(book.trades),
                "net_pnl_cents": sum(t["net_pnl_cents"] for t in book.trades),
                "ending_equity_cents": book.ending_equity_cents,
                "max_open": book.max_open,
                "fill_fraction": "NOT_IDENTIFIED",
                "depth": "NOT_IDENTIFIED",
                "note": "Contract and cash replay only. Not evidence of available size.",
            }
        )
    write_csv(RUN / "05_profitability_dissection" / "capacity_curve.csv", capacity)
    write_csv(
        RUN / "05_profitability_dissection" / "ordering_and_all_in.csv",
        [
            {
                "name": "REVERSE_SAME_TIME_PRIORITY",
                "admitted": len(reverse.trades),
                "net_pnl_cents": sum(t["net_pnl_cents"] for t in reverse.trades),
                "max_open": reverse.max_open,
            },
            {
                "name": "ALL_IN_FEE_INSIDE_6PCT",
                "admitted": len(all_in.trades),
                "net_pnl_cents": sum(t["net_pnl_cents"] for t in all_in.trades),
                "max_open": all_in.max_open,
            },
        ],
    )

    intervals = {
        "combined": day_cluster_means(trades, 10000, 20260926),
        "NBA": day_cluster_means([t for t in trades if t["sport"] == "NBA"], 10000, 20260927),
        "NCAAB": day_cluster_means([t for t in trades if t["sport"] == "NCAAB"], 10000, 20260928),
    }
    holm_rows = holm(
        [
            ("combined_mean_net_per_contract", intervals["combined"]["one_sided_p_mean_le_0"]),
            ("NBA_mean_net_per_contract", intervals["NBA"]["one_sided_p_mean_le_0"]),
            ("NCAAB_mean_net_per_contract", intervals["NCAAB"]["one_sided_p_mean_le_0"]),
        ]
    )
    (RUN / "03_statistical_validation" / "day_cluster_intervals.json").write_text(
        json.dumps({"intervals": intervals, "holm_primary_family": holm_rows}, indent=2),
        encoding="utf-8",
    )
    (RUN / "03_statistical_validation" / "timing_null.json").write_text(
        json.dumps(
            {
                "status": "NOT_IDENTIFIABLE",
                "reason": "The 936-game book is conditioned on a later FIRST80. A matched pre-entry timing null that does not reuse that selection is not identified from these rows.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    per_contract = [int(t["net_pnl_cents"]) / int(t["contracts"]) for t in trades]
    mean_pc = sum(per_contract) / len(per_contract)
    total_contracts = sum(int(t["contracts"]) for t in trades)
    total_net = sum(int(t["net_pnl_cents"]) for t in trades)
    write_csv(
        RUN / "05_profitability_dissection" / "breakeven_execution_cost.csv",
        [
            {
                "metric": "extra_round_trip_cents_per_contract_that_zeros_mean_net",
                "unweighted_mean_net_cents_per_contract": mean_pc,
                "contract_weighted_net_cents_per_contract": total_net / total_contracts,
                "label": "TOLERANCE_NOT_A_CLAIM_THAT_REAL_COSTS_ARE_BELOW_THIS",
                "asymmetric_winner_loser_costs": "NOT_IDENTIFIED",
            }
        ],
    )

    cohorts: dict[str, list] = defaultdict(list)
    for trade in trades:
        cohorts[trade["cohort_id"]].append(trade)
    cohort_rows = []
    for key in sorted(cohorts, key=int):
        items = cohorts[key]
        cohort_rows.append(
            {
                "entry_cohort_id": key,
                "n": len(items),
                "complete": len(items) == 10,
                "net_pnl_cents": sum(int(t["net_pnl_cents"]) for t in items),
                "wins": sum(1 for t in items if int(t["net_pnl_cents"]) > 0),
                "losses": sum(1 for t in items if int(t["net_pnl_cents"]) < 0),
                "first_entry_pacific": min(t["signal_pacific"] for t in items),
                "last_exit_pacific": max(t["exit_pacific"] for t in items),
                "note": "Cohort is ten admitted entries. It does not control the sizing epoch.",
            }
        )
    write_csv(RUN / "02_portfolio_logs" / "entry_cohorts.csv", cohort_rows)
    write_csv(
        RUN / "02_portfolio_logs" / "equity_curve.csv",
        [
            {
                "ts": e["ts"],
                "kind": e["kind"],
                "equity_cents": e["equity_cents"],
                "cash_cents": e["cash_cents"],
                "open_count": e["open_count"],
                "series": "REALIZED_ACCOUNTING",
            }
            for e in events
        ],
    )

    print("block lengths 1 and 3", flush=True)
    for block, seed in ((1, 11), (3, 13)):
        values = block_bootstrap_equity(cands, block=block, n_paths=1500, seed=seed)
        ordered = sorted(values)
        (RUN / "04_monte_carlo" / f"block_{block}_summary.json").write_text(
            json.dumps(
                {
                    "block_days": block,
                    "paths_run": len(values),
                    "seed": seed,
                    "p50": ordered[len(ordered) // 2] if ordered else None,
                    "p05": ordered[int(0.05 * (len(ordered) - 1))] if ordered else None,
                    "p95": ordered[int(0.95 * (len(ordered) - 1))] if ordered else None,
                    "label": "SENSITIVITY_NOT_THE_PRIMARY_7_DAY_BLOCK",
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    print("paths", flush=True)
    paths = load_paths(trades)
    within_game(trades, paths)
    marked = bid_mark_drawdown(trades, events, paths)
    (RUN / "02_portfolio_logs" / "bid_marked_drawdown.json").write_text(json.dumps(marked, indent=2), encoding="utf-8")
    addendum = {
        "written_utc": datetime.now(timezone.utc).isoformat(),
        "reverse_admitted": len(reverse.trades),
        "all_in_admitted": len(all_in.trades),
        "all_in_net_pnl_cents": sum(t["net_pnl_cents"] for t in all_in.trades),
        "capacity": capacity,
        "breakeven_unweighted_cents_per_contract": mean_pc,
        "day_cluster_combined_ci95": intervals["combined"]["ci95"],
        "holm": holm_rows,
        "bid_marked_drawdown": marked,
        "timing_null": "NOT_IDENTIFIABLE",
    }
    (RUN / "07_final_report" / "completion_addendum.json").write_text(json.dumps(addendum, indent=2), encoding="utf-8")
    print(json.dumps({"mean_pc": mean_pc, "marked_dd": marked.get("max_drawdown_fraction"), "capacity0": capacity[0]}, indent=2))


if __name__ == "__main__":
    main()
