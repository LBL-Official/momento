#!/usr/bin/env python3
"""Named uncertainty families, mark series, period attribution, and the root manifest.

Does not rewrite trades.csv or summary.json.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import random
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

EXP = Path(__file__).resolve().parent
SRC = EXP / "src"
sys.path.insert(0, str(SRC))

from first78.extract import _index_candles, _quality, _read_bars  # noqa: E402
from first78.money import fee_charged_cents, fee_raw  # noqa: E402
from first78.portfolio import replay  # noqa: E402
from first78.stats import max_drawdown, transition_matrix  # noqa: E402

RUN = EXP / "runs" / "first78_67_20260926T074540Z"
REPO = EXP.parents[1]
NBA_ROOT = REPO / "Backtesting Suite/Data/NBA/2025-2026/warehouse/normalized/nba"
NCAAB_ROOT = REPO / "Backtesting Suite/Data/NCAAB/2025-2026/warehouse/normalized/ncaab"


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


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def q_index(ordered: list[int], frac: float) -> int:
    return ordered[min(len(ordered) - 1, max(0, int(round(frac * (len(ordered) - 1)))))]


def week_start(iso_day: str) -> str:
    d = date.fromisoformat(iso_day)
    return (d - timedelta(days=d.weekday())).isoformat()


def candidates_from_trades(trades: list[dict]) -> list[dict]:
    return [
        {
            "game_id": t["game_id"],
            "contract_id": t["contract_id"],
            "sport": t["sport"],
            "signal_ts": int(t["entry_ts"]),
            "exit_ts": int(t["exit_ts"]),
            "cash_ts": int(t["cash_ts"]),
            "exit_reason": t["exit_reason"],
            "local_day": t["signal_pacific"][:10],
        }
        for t in trades
    ]


def rollup(trades: list[dict], keyfn) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for trade in trades:
        groups[keyfn(trade)].append(trade)
    rows = []
    for key in sorted(groups):
        items = groups[key]
        nets = [int(t["net_pnl_cents"]) for t in items]
        gross = [int(t["gross_pnl_cents"]) for t in items]
        rows.append(
            {
                "period": key,
                "n": len(items),
                "gross_pnl_cents": sum(gross),
                "net_pnl_cents": sum(nets),
                "wins": sum(1 for v in nets if v > 0),
                "losses": sum(1 for v in nets if v < 0),
                "flats": sum(1 for v in nets if v == 0),
                "book": "ONE_20000_BOOK_ATTRIBUTION",
            }
        )
    return rows


def write_period_tree(section: Path, trades: list[dict]) -> None:
    scopes = {
        "Universe": trades,
        "NBA": [t for t in trades if t["sport"] == "NBA"],
        "NCAAB": [t for t in trades if t["sport"] == "NCAAB"],
    }
    for name, rows in scopes.items():
        write_csv(section / name / "daily" / "by_day.csv", rollup(rows, lambda t: t["signal_pacific"][:10]))
        write_csv(section / name / "weekly" / "by_week.csv", rollup(rows, lambda t: week_start(t["signal_pacific"][:10])))
        write_csv(section / name / "monthly" / "by_month.csv", rollup(rows, lambda t: t["signal_pacific"][:7]))
        write_csv(section / name / "batch" / "by_completion_batch.csv", rollup(rows, lambda t: t["completion_batch_id"]))
        write_csv(
            section / name / "overall" / "summary.csv",
            [
                {
                    "n": len(rows),
                    "net_pnl_cents": sum(int(t["net_pnl_cents"]) for t in rows),
                    "gross_pnl_cents": sum(int(t["gross_pnl_cents"]) for t in rows),
                    "book": "ONE_20000_BOOK_ATTRIBUTION",
                }
            ],
        )


def label_wl(trade: dict) -> str:
    net = int(trade["net_pnl_cents"])
    if net > 0:
        return "W"
    if net < 0:
        return "L"
    return "F"


def reduced_form(trades: list[dict]) -> None:
    nets = [int(t["net_pnl_cents"]) for t in trades]
    start = 2_000_000

    def path_stats(seq: list[int]) -> dict:
        equity = start
        peak = equity
        worst = 0.0
        streak = 0
        longest = 0
        for value in seq:
            equity += value
            if value < 0:
                streak += 1
                longest = max(longest, streak)
            else:
                streak = 0
            if equity > peak:
                peak = equity
            if peak > 0:
                worst = max(worst, 1 - equity / peak)
        return {"ending_equity_cents": equity, "max_drawdown_fraction": worst, "longest_loss_streak": longest}

    rng = random.Random(78)
    perm_dd = []
    perm_streak = []
    for _ in range(5000):
        seq = nets[:]
        rng.shuffle(seq)
        stats = path_stats(seq)
        perm_dd.append(stats["max_drawdown_fraction"])
        perm_streak.append(stats["longest_loss_streak"])
    observed = path_stats(nets)
    rng_b = random.Random(67)
    iid_end = []
    for _ in range(5000):
        seq = [nets[rng_b.randrange(len(nets))] for _ in nets]
        iid_end.append(start + sum(seq))
    perm_dd.sort()
    iid_end.sort()
    out = RUN / "04_monte_carlo"
    (out / "family_A_permutation.json").write_text(
        json.dumps(
            {
                "family": "A",
                "method": "permutation_without_replacement_of_admitted_net_pnl",
                "draws": 5000,
                "seed": 78,
                "label": "REDUCED_FORM_TRADE_SEQUENCE",
                "cannot_validate_seven_slot_calendar_portfolio": True,
                "ending_equity_invariant_cents": start + sum(nets),
                "observed_cumulative_max_drawdown_fraction": observed["max_drawdown_fraction"],
                "observed_longest_loss_streak": observed["longest_loss_streak"],
                "permuted_drawdown_p50": perm_dd[len(perm_dd) // 2],
                "permuted_drawdown_p95": perm_dd[int(0.95 * (len(perm_dd) - 1))],
                "note": "The sum of these nets does not change. Drawdown and streaks do. This is not the cash-and-cap ledger.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (out / "family_B_iid_bootstrap.json").write_text(
        json.dumps(
            {
                "family": "B",
                "method": "iid_bootstrap_with_replacement_of_admitted_net_pnl",
                "draws": 5000,
                "seed": 67,
                "label": "REDUCED_FORM_DIAGNOSTIC",
                "cannot_validate_seven_slot_calendar_portfolio": True,
                "ending_equity_p05": iid_end[int(0.05 * (len(iid_end) - 1))],
                "ending_equity_p50": iid_end[len(iid_end) // 2],
                "ending_equity_p95": iid_end[int(0.95 * (len(iid_end) - 1))],
                "p_ending_below_start": sum(1 for v in iid_end if v < start) / len(iid_end),
                "note": "Sample composition changes. This is not a calendar-block portfolio path.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def primary_quantiles() -> dict:
    rows = read_csv(RUN / "04_monte_carlo" / "primary_ending_equity.csv")
    values = sorted(int(r["ending_equity_cents"]) for r in rows)
    fracs = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    se = math.sqrt(var / len(values))
    below = sum(1 for v in values if v < 2_000_000)
    payload = {
        "family": "C",
        "method": "contiguous_local_day_blocks",
        "block_days": 7,
        "paths": len(values),
        "seed": 20260926,
        "quantile_index": "round(frac * (n - 1))",
        "ending_equity_cents": {str(frac): q_index(values, frac) for frac in fracs},
        "mean_ending_equity_cents": mean,
        "monte_carlo_se_of_mean_cents": se,
        "count_ending_below_start": below,
        "plug_in_p_ending_below_start": below / len(values),
        "note": "A zero count makes the plug-in standard error of that proportion zero. That is not proof the probability is zero. Episode set is the 647 eligible candidates. Cap and cash are rerun. This file stores ending equity only.",
        "one_year_distribution": "NOT_PRODUCED",
        "nested_outer_refits": "NOT_RUN",
    }
    (RUN / "04_monte_carlo" / "family_C_primary_quantiles.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def path_subsample(cands: list[dict]) -> None:
    by_day: dict[str, list] = defaultdict(list)
    for cand in cands:
        by_day[cand["local_day"]].append(cand)
    days = sorted(by_day)
    rng = random.Random(20260929)
    block = 7
    span = max(1, len(days) - block + 1)
    rows = []
    for i in range(400):
        picked: list[str] = []
        while len(picked) < len(days):
            start = rng.randrange(span)
            picked.extend(days[start : start + block])
        picked = picked[: len(days)]
        built = []
        cursor = 1_800_000_000
        for day in picked:
            group = by_day[day]
            base = min(int(c["signal_ts"]) for c in group)
            shift = cursor - base
            for cand in group:
                nxt = dict(cand)
                nxt["signal_ts"] = int(cand["signal_ts"]) + shift
                nxt["exit_ts"] = int(cand["exit_ts"]) + shift
                nxt["cash_ts"] = int(cand["cash_ts"]) + shift
                nxt["game_id"] = f"{cand['game_id']}-s{i}-{shift}"
                built.append(nxt)
            cursor += 86400 * block + 5
        book = replay(built)
        equity = [int(e["equity_cents"]) for e in book.events]
        dd = max_drawdown(equity)
        after = {}
        for n in (40, 100):
            hits = [t for t in book.trades if int(t["completion_sequence"]) == n]
            after[n] = None if not hits else int(hits[-1]["net_pnl_cents"])
        # Equity after the nth completion is the event equity on that exit, before later cash.
        eq_after = {}
        for event in book.events:
            seq = event.get("completion_sequence")
            if seq in (40, 100):
                eq_after[int(seq)] = int(event["equity_cents"])
        rows.append(
            {
                "path": i,
                "ending_equity_cents": book.ending_equity_cents,
                "max_drawdown_fraction": dd["max_drawdown_fraction"],
                "equity_after_40_completions_cents": eq_after.get(40),
                "equity_after_100_completions_cents": eq_after.get(100),
                "insufficient_cash_rejections": sum(1 for r in book.rejections if r.get("reason") == "INSUFFICIENT_CASH"),
                "max_open": book.max_open,
            }
        )
    write_csv(RUN / "04_monte_carlo" / "family_C_path_subsample.csv", rows)
    def frac(pred) -> float:
        return sum(1 for r in rows if pred(r)) / len(rows)
    summary = {
        "paths": len(rows),
        "seed": 20260929,
        "block_days": 7,
        "label": "SUBSAMPLE_FOR_PATH_STATISTICS_NOT_IN_THE_12255_ENDING_EQUITY_FILE",
        "p_ending_below_start": frac(lambda r: r["ending_equity_cents"] < 2_000_000),
        "p_equity_after_40_below_start": frac(lambda r: (r["equity_after_40_completions_cents"] or 0) < 2_000_000),
        "p_equity_after_100_below_start": frac(lambda r: (r["equity_after_100_completions_cents"] or 0) < 2_000_000),
        "p_mdd_above_15pct": frac(lambda r: r["max_drawdown_fraction"] > 0.15),
        "p_mdd_above_10pct": frac(lambda r: r["max_drawdown_fraction"] > 0.10),
        "drawdown_series": "realized accounting equity inside the resampled ledger",
        "one_year_and_1000_trade_horizon": "NOT_PRODUCED",
    }
    (RUN / "04_monte_carlo" / "family_C_path_subsample_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def regimes(trades: list[dict]) -> None:
    ordered = sorted(trades, key=lambda t: (int(t["entry_ts"]), t["trade_id"]))
    (RUN / "06_markov_chains" / "entry_order_transitions.json").write_text(
        json.dumps(
            {
                "order": "entry_ts",
                "label": "DESCRIPTIVE_OVERLAPPING_GAMES",
                "matrix": transition_matrix([label_wl(t) for t in ordered]),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    completed = sorted(trades, key=lambda t: (int(t["exit_ts"]), t["trade_id"]))
    regimes_seq = [(t.get("entry_regime") or "UNKNOWN") for t in ordered]
    states = ["LOW", "HIGH", "UNKNOWN"]
    counts = {a: Counter() for a in states}
    for prev, nxt in zip(regimes_seq, regimes_seq[1:]):
        if prev not in counts:
            prev = "UNKNOWN"
        if nxt not in counts:
            nxt = "UNKNOWN"
        counts[prev][nxt] += 1
    probs = {}
    for state in states:
        total = sum(counts[state].values())
        probs[state] = None if total == 0 else {s: counts[state][s] / total for s in states}
    by_reg: dict[str, list[int]] = defaultdict(list)
    for trade in ordered:
        by_reg[trade.get("entry_regime") or "UNKNOWN"].append(int(trade["net_pnl_cents"]))
    (RUN / "06_markov_chains" / "entry_regime_transitions.json").write_text(
        json.dumps(
            {
                "family": "D",
                "regime_definition": "pre-entry volatility only; LOW < 2pp, HIGH >= 2pp, UNKNOWN if insufficient",
                "uses_future_exit": False,
                "counts": {a: dict(counts[a]) for a in states},
                "probs": probs,
                "n_by_regime": {k: len(v) for k, v in by_reg.items()},
                "mean_net_cents_by_regime": {k: (sum(v) / len(v) if v else None) for k, v in by_reg.items()},
                "label": "TRADE_SEQUENCE_RISK_ANALYSIS_NOT_A_SEVEN_SLOT_FORECAST",
                "completion_order_file": "completion_order_transitions.json",
                "entry_order_n": len(ordered),
                "completion_order_matches_exit_sort_n": len(completed),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def family_e() -> None:
    (RUN / "04_monte_carlo" / "family_E_parametric_stress.json").write_text(
        json.dumps(
            {
                "family": "E",
                "method": "bounded_price_and_fee_stress_grid",
                "probabilities": "NOT_ESTIMATED",
                "grid": "05_profitability_dissection/stresses.csv",
                "ordering_and_all_in": "05_profitability_dissection/ordering_and_all_in.csv",
                "failed_stop_or_gap_through_probability": "NOT_ESTIMATED",
                "note": "A winning settlement stays $1. A losing settlement stays $0. These rows are assumptions, not a fitted distribution of slippage.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (RUN / "04_monte_carlo" / "families.json").write_text(
        json.dumps(
            {
                "A": "family_A_permutation.json",
                "B": "family_B_iid_bootstrap.json",
                "C": "primary_summary.json and family_C_primary_quantiles.json; block_1 and block_3 are sensitivities",
                "D": "../06_markov_chains/entry_regime_transitions.json",
                "E": "family_E_parametric_stress.json",
                "timing_null": "../03_statistical_validation/timing_null.json",
                "nested_outer_refits": "NOT_RUN",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def mark_series(trades: list[dict], events: list[dict]) -> None:
    indexes = {"NBA": _index_candles(NBA_ROOT), "NCAAB": _index_candles(NCAAB_ROOT)}
    paths: dict[str, list[tuple[int, int]]] = {}
    for trade in trades:
        path = indexes[trade["sport"]].get(trade["contract_id"])
        kept = []
        if path is not None:
            had = False
            entry = int(trade["entry_ts"])
            end = int(trade["exit_ts"])
            for bar in _read_bars(path):
                if not _quality(bar["bid"], bar["ask"], bar["vol"], had):
                    continue
                had = True
                if bar["ts"] < entry or bar["ts"] > end or bar["bid"] is None:
                    continue
                kept.append((bar["ts"], bar["bid"] // 100))
        paths[trade["trade_id"]] = kept
    by_id = {t["trade_id"]: t for t in trades}
    open_ids: set[str] = set()
    rows = []
    for event in events:
        tid = event.get("trade_id") or ""
        if event["kind"] == "entry" and tid:
            open_ids.add(tid)
        if event["kind"] == "exit" and tid:
            open_ids.discard(tid)
        ts = int(event["ts"])
        gross = 0
        fees = 0
        for open_id in open_ids:
            bid = None
            for stamp, px in paths.get(open_id) or []:
                if stamp <= ts:
                    bid = px
                else:
                    break
            if bid is None:
                gross = None
                break
            contracts = int(by_id[open_id]["contracts"])
            gross += contracts * bid
            if 0 < bid < 100:
                fees += fee_charged_cents(fee_raw(contracts, bid))
        if gross is None:
            continue
        cash = int(event["cash_cents"])
        receivable = int(event["receivable_cents"])
        rows.append(
            {
                "ts": event["ts"],
                "kind": event["kind"],
                "realized_accounting_equity_cents": event["equity_cents"],
                "bid_marked_gross_equity_cents": cash + receivable + gross,
                "bid_marked_net_of_estimated_exit_fee_cents": cash + receivable + gross - fees,
            }
        )
    write_csv(RUN / "02_portfolio_logs" / "mark_equity_curve.csv", rows)
    gross_eq = [int(r["bid_marked_gross_equity_cents"]) for r in rows]
    net_eq = [int(r["bid_marked_net_of_estimated_exit_fee_cents"]) for r in rows]
    (RUN / "02_portfolio_logs" / "mark_equity_drawdowns.json").write_text(
        json.dumps(
            {
                "bid_marked_gross": max_drawdown(gross_eq),
                "bid_marked_net_of_estimated_exit_fee": max_drawdown(net_eq),
                "points": len(rows),
                "fee": "user coefficient 0.0175, ceil to the cent, charged as if the open bid were a sale. Not a fill.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def manifest() -> None:
    protected = [
        "ROLLER/roller/research/first80.py",
        "research/choosin_texas/library/nba_2q_regular_8040_1lot_2026_27/book.json",
        "ROLLER/roller/choosin_texas/locks.py",
        "research/first80_asked_six_chatgpt_export/first80_asked_six.csv",
    ]
    hashes = {rel: sha256(REPO / rel) for rel in protected}
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True, stderr=subprocess.DEVNULL).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True, stderr=subprocess.DEVNULL)
        git = {"commit": commit, "dirty": bool(dirty.strip()), "status": "OK"}
    except (subprocess.CalledProcessError, FileNotFoundError):
        git = {"commit": None, "dirty": None, "status": "GIT_UNAVAILABLE"}
    versions = {"python": platform.python_version()}
    try:
        import pyarrow

        versions["pyarrow"] = pyarrow.__version__
    except ImportError:
        versions["pyarrow"] = None
    payload = {
        "experiment": "FIRST78_67_PORTFOLIO_V1",
        "run_id": "first78_67_20260926T074540Z",
        "written_utc": datetime.now(timezone.utc).isoformat(),
        "git": git,
        "dependency_versions": versions,
        "source_sha256": hashes,
        "protected_files_not_edited_by_this_study": [
            "ROLLER/roller/research/first80.py",
            "research/choosin_texas/library/nba_2q_regular_8040_1lot_2026_27/book.json",
        ],
        "austin_confirmation_outcomes": "not opened and not hashed",
        "headline_files_sha256": {
            "trades.csv": sha256(RUN / "01_trade_logs" / "trades.csv"),
            "summary.json": sha256(RUN / "summary.json"),
        },
        "live_execution": False,
    }
    (EXP / "manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (RUN / "manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    trades = read_csv(RUN / "01_trade_logs" / "trades.csv")
    events = read_csv(RUN / "02_portfolio_logs" / "events.csv")
    cands = candidates_from_trades(trades)
    for section in (
        "02_portfolio_logs",
        "03_statistical_validation",
        "04_monte_carlo",
        "05_profitability_dissection",
        "06_markov_chains",
        "07_final_report",
    ):
        write_period_tree(RUN / section, trades)
    reduced_form(trades)
    primary_quantiles()
    print("path subsample", flush=True)
    path_subsample(cands)
    regimes(trades)
    family_e()
    print("marks", flush=True)
    mark_series(trades, events)
    manifest()
    print("done", flush=True)


if __name__ == "__main__":
    main()
