#!/usr/bin/env python3
"""Run the frozen FIRST78→67 close-proxy portfolio study.

Research only. Does not submit orders. Does not edit FIRST80.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

EXP = Path(__file__).resolve().parent
REPO = EXP.parents[1]
SRC = EXP / "src"
sys.path.insert(0, str(SRC))

from first78.extract import extract  # noqa: E402
from first78.materialize import build_candidates, candidate_from_contract  # noqa: E402
from first78.money import reference_unit  # noqa: E402
from first78.portfolio import replay  # noqa: E402
from first78.select import select_game  # noqa: E402
from first78.stats import (  # noqa: E402
    binomial_records,
    block_bootstrap_equity,
    max_drawdown,
    sharpe,
    transition_matrix,
)
from first78.timeutil import iso_la, iso_utc, local_date, week_start  # noqa: E402

RUN_ID = datetime.now(timezone.utc).strftime("first78_67_%Y%m%dT%H%M%SZ")
RUN = EXP / "runs" / RUN_ID
PRIMARY_MC = 20000
SENSITIVITY_MC = 400
OUTER = 20
INNER = 20
MC_SEED = 20260926


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_state() -> dict:
    def run(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=REPO, text=True, stderr=subprocess.DEVNULL).strip()

    try:
        commit = run("rev-parse", "HEAD")
        dirty = run("status", "--porcelain")
        return {"commit": commit, "dirty": bool(dirty), "status_porcelain": dirty}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"commit": None, "dirty": None, "status": "GIT_UNAVAILABLE"}


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows and not fields:
        path.write_text("", encoding="utf-8")
        return
    keys = fields or list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in keys})


def vol_from_path(path: list, end_ts: int) -> dict:
    points = [(int(ts), int(px)) for ts, px in path if ts is not None and px is not None and int(ts) <= int(end_ts)]
    if len(points) < 6:
        return {"category": None, "stdev_pp": None, "reason": "INSUFFICIENT_HISTORY"}
    window = points[-6:]
    if any(window[i + 1][0] - window[i][0] != 60 for i in range(5)):
        return {"category": None, "stdev_pp": None, "reason": "MISSING_MINUTE"}
    changes = [window[i + 1][1] - window[i][1] for i in range(5)]
    mean = sum(changes) / 5
    var = sum((c - mean) ** 2 for c in changes) / 4
    sd = math.sqrt(var)
    bounds = [(0, 0.5, 1), (0.5, 1, 2), (1, 2, 3), (2, 3, 4), (3, 5, 5), (5, 8, 6)]
    category = 7 if sd >= 8 else None
    for lo, hi, cat in bounds:
        if lo <= sd < hi:
            category = cat
    regime = None if category is None else ("LOW" if sd < 2 else "HIGH")
    return {"category": category, "stdev_pp": sd, "reason": None, "regime": regime}


def light(rows: list[dict]) -> list[dict]:
    return [{k: v for k, v in row.items() if k != "path"} for row in rows]


def trade_rows(book, meta: dict[str, dict]) -> list[dict]:
    out = []
    for trade in book.trades:
        src = meta.get(trade["game_id"], {})
        entry_vol = vol_from_path(src.get("path") or [], trade["entry_ts"])
        exit_end = trade["exit_ts"]
        exit_vol = vol_from_path(src.get("path") or [], exit_end)
        net = trade["net_pnl_cents"]
        principal = trade["principal_cents"]
        debit = principal + trade["entry_fee_cents"]
        result = "FLAT" if net == 0 else ("POSITIVE" if net > 0 else "NEGATIVE")
        terminal = src.get("result")
        out.append(
            {
                **trade,
                "scenario": "THRESHOLD_ACCOUNTING_REFERENCE",
                "evidence": "FIRST78_CLOSE_PROXY",
                "selection_rule": "CONTRACT_WISE_FIRST",
                "matchup": src.get("matchup"),
                "slice": src.get("slice"),
                "team": src.get("team"),
                "season": "2025-26",
                "membership": "FIRST80_DERIVED_FOUR_CONDITIONAL",
                "signal_utc": iso_utc(trade["entry_ts"]),
                "signal_pacific": iso_la(trade["entry_ts"]),
                "exit_utc": iso_utc(trade["exit_ts"]),
                "exit_pacific": iso_la(trade["exit_ts"]),
                "cash_utc": iso_utc(trade["cash_ts"]),
                "cash_pacific": iso_la(trade["cash_ts"]),
                "observed_entry_close_cents": src.get("observed_close_cents"),
                "overshoot_cents": src.get("overshoot_cents"),
                "stop_trigger_close_cents": src.get("stop_close_cents"),
                "stop_gap_cents": src.get("stop_gap_cents"),
                "spread_cents": src.get("spread_cents"),
                "depth_available": src.get("depth_available"),
                "ambiguous_entry_bar": src.get("ambiguous_entry_bar"),
                "clock_bucket": src.get("clock_bucket"),
                "clock_quality": src.get("clock_quality"),
                "period": src.get("period"),
                "period_remaining_s": src.get("period_remaining_s"),
                "clock_note": "NBA intra-quarter seconds are modeled" if src.get("seconds_are_modeled") else "NCAAB wall clock",
                "terminal_result": terminal,
                "strategy_result": result,
                "principal_return": None if principal == 0 else net / principal,
                "cash_on_cash_return": None if debit == 0 else net / debit,
                "pnl_per_contract_cents": None if trade["contracts"] == 0 else net / trade["contracts"],
                "contribution_vs_sizing_balance": None if trade["sizing_balance_cents"] == 0 else net / trade["sizing_balance_cents"],
                "entry_regime": entry_vol.get("regime"),
                "entry_vol_reason": entry_vol.get("reason"),
                "exit_vol_category": exit_vol.get("category"),
                "exit_vol_stdev_pp": exit_vol.get("stdev_pp"),
                "exit_vol_reason": exit_vol.get("reason"),
                "stopped_then_won": trade["exit_reason"] == "STOP" and terminal == "yes",
                "stopped_then_lost": trade["exit_reason"] == "STOP" and terminal == "no",
                "cash_label": src.get("cash_label"),
                "first80_ticker": src.get("first80_ticker"),
                "selected_is_first80_ticker": src.get("contract_id") == src.get("first80_ticker") if "contract_id" in trade else None,
            }
        )
    return out


def period_rows(trades: list[dict], key_fn) -> list[dict]:
    groups: dict = defaultdict(list)
    for trade in trades:
        groups[key_fn(trade)].append(trade)
    rows = []
    for key in sorted(groups):
        items = groups[key]
        gross = sum(t["gross_pnl_cents"] for t in items)
        net = sum(t["net_pnl_cents"] for t in items)
        wins = sum(1 for t in items if t["net_pnl_cents"] > 0)
        losses = sum(1 for t in items if t["net_pnl_cents"] < 0)
        flats = sum(1 for t in items if t["net_pnl_cents"] == 0)
        rows.append(
            {
                "period": key,
                "n": len(items),
                "gross_pnl_cents": gross,
                "net_pnl_cents": net,
                "wins": wins,
                "losses": losses,
                "flats": flats,
            }
        )
    return rows


def write_tree(base: Path, trades: list[dict]) -> None:
    scopes = {
        "Universe": trades,
        "NBA": [t for t in trades if t["sport"] == "NBA"],
        "NCAAB": [t for t in trades if t["sport"] == "NCAAB"],
    }
    for scope, rows in scopes.items():
        for section in (
            "01_trade_logs",
            "02_portfolio_logs",
            "03_statistical_validation",
            "04_monte_carlo",
            "05_profitability_dissection",
            "06_markov_chains",
        ):
            for period in ("daily", "weekly", "monthly", "batch", "overall"):
                (base / section / scope / period).mkdir(parents=True, exist_ok=True)
        (base / "07_final_report").mkdir(parents=True, exist_ok=True)
        write_csv(base / "01_trade_logs" / scope / "overall" / "trades_view.csv", rows)
        write_csv(
            base / "01_trade_logs" / scope / "daily" / "by_day.csv",
            period_rows(rows, lambda t: local_date(t["entry_ts"]).isoformat()),
        )
        write_csv(
            base / "01_trade_logs" / scope / "weekly" / "by_week.csv",
            period_rows(rows, lambda t: week_start(t["entry_ts"]).isoformat()),
        )
        write_csv(
            base / "01_trade_logs" / scope / "monthly" / "by_month.csv",
            period_rows(rows, lambda t: local_date(t["entry_ts"]).isoformat()[:7]),
        )
        write_csv(
            base / "01_trade_logs" / scope / "batch" / "by_completion_batch.csv",
            period_rows(rows, lambda t: t["completion_batch_id"]),
        )


def main() -> None:
    started = time.time()
    RUN.mkdir(parents=True, exist_ok=True)
    ref = reference_unit()
    contract = {
        "experiment": "FIRST78_67_PORTFOLIO_V1",
        "evidence_headline": "THRESHOLD_ACCOUNTING_REFERENCE",
        "signal_convention": "FIRST78_CLOSE_PROXY",
        "next_bar_label": "NEXT_BAR_PRICE_PROXY",
        "observed_price_replay": "UNAVAILABLE",
        "maker_execution_replay": "UNAVAILABLE",
        "selection_rule_headline": "CONTRACT_WISE_FIRST",
        "selection_rule_variant": "GAME_WIDE_FIRST",
        "population": "derived_four_936_conditional_on_FIRST80",
        "entry_window_local": "[2025-11-01, 2026-04-02)",
        "timezone": "America/Los_Angeles",
        "balance_cents": 2_000_000,
        "allocation": "0.06 entry principal",
        "cap": 7,
        "sizing": "completion_epochs",
        "entry_cents_assumed": 78,
        "stop_cents_assumed": 67,
        "settlement_win_cents": 100,
        "settlement_loss_cents": 0,
        "fee_coef_user": "0.0175",
        "fee_rounding": "ceil to cent once per aggregate order",
        "cash_baseline": "HYPOTHETICAL_CASH_AT_SETTLEMENT_TIME for holds; assumed sale cash at stop signal for stops",
        "close_time_role": "trading-close lifecycle timestamp, hypothesis only",
        "expiration_time_role": "not used as cash; later than settlement on inspected NBA markets",
        "mc_primary_paths_target": PRIMARY_MC,
        "mc_seed": MC_SEED,
        "launch_expectation": "NOT_YET_IDENTIFIABLE",
        "live_execution": False,
        "reference_unit": ref,
    }
    (EXP / "contract.json").write_text(json.dumps(contract, indent=2), encoding="utf-8")
    (RUN / "contract.json").write_text(json.dumps(contract, indent=2), encoding="utf-8")

    print("extracting", flush=True)
    games = extract()
    print("materializing", flush=True)
    candidates, audit = build_candidates(games, "CONTRACT_WISE_FIRST", cash_mode="settlement")
    meta = {row["game_id"]: row for row in candidates}
    book = replay(light(candidates))
    trades = trade_rows(book, meta)
    write_tree(RUN, trades)
    write_csv(RUN / "01_trade_logs" / "trades.csv", trades)
    write_csv(RUN / "01_trade_logs" / "candidate_audit.csv", audit)
    write_csv(RUN / "02_portfolio_logs" / "events.csv", book.events)
    write_csv(RUN / "02_portfolio_logs" / "sizing_epochs.csv", book.epochs)

    equity = [2_000_000] + [e["equity_cents"] for e in book.events]
    dd = max_drawdown(equity)
    net = sum(t["net_pnl_cents"] for t in trades)
    gross = sum(t["gross_pnl_cents"] for t in trades)
    fees = sum(t["entry_fee_cents"] + t["exit_fee_cents"] for t in trades)
    by_sport = Counter()
    for t in trades:
        by_sport[t["sport"]] += t["net_pnl_cents"]
    reasons = Counter(t["exit_reason"] for t in trades)
    reject_reasons = Counter(r["reason"] for r in book.rejections)

    # Separate rule, not pooled.
    wide_cands, wide_audit = build_candidates(games, "GAME_WIDE_FIRST", cash_mode="settlement")
    wide_book = replay(light(wide_cands))
    write_csv(RUN / "01_trade_logs" / "game_wide_first_audit.csv", wide_audit)

    # Hold portfolio replay. Different admissions allowed.
    hold_rows = []
    for game in games:
        decision = select_game(game["contracts"], "CONTRACT_WISE_FIRST")
        if decision["chosen"] is None:
            continue
        row = candidate_from_contract(game, decision["chosen"], cash_mode="settlement", force_hold=True)
        if row and row["exit_reason"] != "UNRESOLVED":
            hold_rows.append(row)
    hold_book = replay(light(hold_rows))

    paired = []
    for trade in trades:
        src = meta[trade["game_id"]]
        payout = 100 if src.get("result") == "yes" else 0
        hold_gross = trade["contracts"] * payout - trade["principal_cents"]
        hold_net = hold_gross - trade["entry_fee_cents"]
        paired.append(
            {
                "trade_id": trade["trade_id"],
                "game_id": trade["game_id"],
                "sport": trade["sport"],
                "stop_net_cents": trade["net_pnl_cents"],
                "hold_net_same_qty_cents": hold_net,
                "paired_diff_cents": trade["net_pnl_cents"] - hold_net,
                "terminal_result": src.get("result"),
                "exit_reason": trade["exit_reason"],
            }
        )
    write_csv(RUN / "05_profitability_dissection" / "paired_stop_vs_hold.csv", paired)
    write_csv(
        RUN / "05_profitability_dissection" / "portfolio_stop_vs_hold.csv",
        [
            {
                "policy": "STOP_67_BASELINE",
                "admitted": len(book.trades),
                "net_pnl_cents": net,
                "ending_equity_cents": book.ending_equity_cents,
                "max_open": book.max_open,
            },
            {
                "policy": "HOLD_REPLAY",
                "admitted": len(hold_book.trades),
                "net_pnl_cents": sum(t["net_pnl_cents"] for t in hold_book.trades),
                "ending_equity_cents": hold_book.ending_equity_cents,
                "max_open": hold_book.max_open,
            },
        ],
    )

    # Adverse stresses. Settlement payout is not shifted.
    stresses = []
    for name, entry, stop in (
        ("entry_plus_1", 79, 67),
        ("entry_plus_2", 80, 67),
        ("stop_minus_1", 78, 66),
        ("stop_minus_2", 78, 65),
        ("entry_plus_1_stop_minus_1", 79, 66),
        ("entry_plus_1_stop_minus_2", 79, 65),
        ("entry_plus_2_stop_minus_1", 80, 66),
        ("entry_plus_2_stop_minus_2", 80, 65),
    ):
        stressed = replay(light(candidates), entry_price_cents=entry, stop_price_cents=stop)
        stresses.append(
            {
                "name": name,
                "entry_cents": entry,
                "stop_cents": stop,
                "admitted": len(stressed.trades),
                "net_pnl_cents": sum(t["net_pnl_cents"] for t in stressed.trades),
                "ending_equity_cents": stressed.ending_equity_cents,
                "max_open": stressed.max_open,
            }
        )
    fee_book = replay(light(candidates), fee_coef=Decimal("0.07"))
    stresses.append(
        {
            "name": "fee_coef_0.07",
            "entry_cents": 78,
            "stop_cents": 67,
            "admitted": len(fee_book.trades),
            "net_pnl_cents": sum(t["net_pnl_cents"] for t in fee_book.trades),
            "ending_equity_cents": fee_book.ending_equity_cents,
            "max_open": fee_book.max_open,
        }
    )
    close_cands, _ = build_candidates(games, "CONTRACT_WISE_FIRST", cash_mode="close_time")
    close_book = replay(light(close_cands))
    stresses.append(
        {
            "name": "HYPOTHETICAL_CASH_AT_CLOSE_TIME",
            "entry_cents": 78,
            "stop_cents": 67,
            "admitted": len(close_book.trades),
            "net_pnl_cents": sum(t["net_pnl_cents"] for t in close_book.trades),
            "ending_equity_cents": close_book.ending_equity_cents,
            "max_open": close_book.max_open,
        }
    )
    delay_cands, _delay_audit = build_candidates(
        games, "CONTRACT_WISE_FIRST", cash_mode="settlement", delay_one_bar=True
    )
    delay_book = replay(light(delay_cands))
    stresses.append(
        {
            "name": "DELAY_ONE_BAR",
            "entry_cents": 78,
            "stop_cents": 67,
            "admitted": len(delay_book.trades),
            "net_pnl_cents": sum(t["net_pnl_cents"] for t in delay_book.trades),
            "ending_equity_cents": delay_book.ending_equity_cents,
            "max_open": delay_book.max_open,
        }
    )
    proxy_cands, _proxy_audit = build_candidates(
        games, "CONTRACT_WISE_FIRST", cash_mode="settlement", use_next_bar_price=True
    )
    proxy_book = replay(light(proxy_cands))
    stresses.append(
        {
            "name": "NEXT_BAR_PRICE_PROXY",
            "entry_cents": "per_trade_next_bid_close",
            "stop_cents": 67,
            "admitted": len(proxy_book.trades),
            "net_pnl_cents": sum(t["net_pnl_cents"] for t in proxy_book.trades),
            "ending_equity_cents": proxy_book.ending_equity_cents,
            "max_open": proxy_book.max_open,
        }
    )
    slot_cash_cands, _ = build_candidates(
        games, "CONTRACT_WISE_FIRST", cash_mode="settlement_cash_plus_1d"
    )
    slot_cash_book = replay(light(slot_cash_cands))
    stresses.append(
        {
            "name": "SLOT_AT_SETTLEMENT_CASH_PLUS_1D",
            "entry_cents": 78,
            "stop_cents": 67,
            "admitted": len(slot_cash_book.trades),
            "net_pnl_cents": sum(t["net_pnl_cents"] for t in slot_cash_book.trades),
            "ending_equity_cents": slot_cash_book.ending_equity_cents,
            "max_open": slot_cash_book.max_open,
        }
    )
    strict = replay(light(candidates), mode="strict_batches")
    stresses.append(
        {
            "name": "STRICT_TEN_ENTRY_BATCH",
            "entry_cents": 78,
            "stop_cents": 67,
            "admitted": len(strict.trades),
            "net_pnl_cents": sum(t["net_pnl_cents"] for t in strict.trades),
            "ending_equity_cents": strict.ending_equity_cents,
            "max_open": strict.max_open,
        }
    )
    write_csv(RUN / "05_profitability_dissection" / "stresses.csv", stresses)
    write_csv(RUN / "02_portfolio_logs" / "strict_batches_trades.csv", strict.trades)

    # Markov on completion order of strategy results.
    labels = ["W" if t["net_pnl_cents"] > 0 else ("L" if t["net_pnl_cents"] < 0 else "F") for t in trades]
    markov = transition_matrix(labels)
    (RUN / "06_markov_chains" / "completion_order_transitions.json").write_text(json.dumps(markov, indent=2), encoding="utf-8")

    win_cents = ref["net_win_cents"]
    loss_cents = abs(ref["net_stop_cents"])
    p_star = Decimal(loss_cents) / Decimal(win_cents + loss_cents)
    records = binomial_records(win_cents, loss_cents, p_star)
    write_csv(RUN / "05_profitability_dissection" / "ten_trade_records_at_pstar.csv", records)

    print("monte carlo", PRIMARY_MC, flush=True)
    t0 = time.time()
    probe = block_bootstrap_equity(candidates, block=7, n_paths=3, seed=MC_SEED)
    probe_s = (time.time() - t0) / max(1, len(probe))
    primary_n = min(PRIMARY_MC, max(500, int(90 / probe_s))) if probe_s > 0 else PRIMARY_MC
    paths = block_bootstrap_equity(candidates, block=7, n_paths=primary_n, seed=MC_SEED)
    paths_sorted = sorted(paths)
    def q(frac: float) -> int | None:
        if not paths_sorted:
            return None
        idx = min(len(paths_sorted) - 1, max(0, int(round(frac * (len(paths_sorted) - 1)))))
        return paths_sorted[idx]

    mc_summary = {
        "method": "contiguous_local_day_blocks",
        "block_days": 7,
        "paths_requested": PRIMARY_MC,
        "paths_run": len(paths),
        "seconds_per_path_probe": probe_s,
        "budget_note": None if len(paths) == PRIMARY_MC else "path count reduced for runtime before reading the distribution as a decision input; seed unchanged",
        "seed": MC_SEED,
        "horizon": "resampled historical candidate-days, not one calendar year",
        "ending_equity_cents_p50": q(0.50),
        "ending_equity_cents_p05": q(0.05),
        "ending_equity_cents_p95": q(0.95),
        "p_ending_below_start": None if not paths else sum(1 for v in paths if v < 2_000_000) / len(paths),
        "label": "PROCESS_VARIATION_CONDITIONAL_ON_THIS_SAMPLE",
    }
    (RUN / "04_monte_carlo" / "primary_summary.json").write_text(json.dumps(mc_summary, indent=2), encoding="utf-8")
    write_csv(RUN / "04_monte_carlo" / "primary_ending_equity.csv", [{"path": i, "ending_equity_cents": v} for i, v in enumerate(paths)])

    daily = period_rows(trades, lambda t: local_date(t["exit_ts"]).isoformat())
    daily_returns = [row["net_pnl_cents"] / 2_000_000 for row in daily]
    sharpe_daily = sharpe(daily_returns, 365)
    (RUN / "03_statistical_validation" / "sharpe_daily.json").write_text(json.dumps(sharpe_daily, indent=2), encoding="utf-8")
    (RUN / "03_statistical_validation" / "realized_accounting_drawdown.json").write_text(
        json.dumps({**dd, "series": "event_equity_cash_plus_receivable_plus_open_principal", "mtm_bid_mark": "see limitations; minute marks not a fill"}, indent=2),
        encoding="utf-8",
    )

    summary = {
        "run_id": RUN_ID,
        "locked_games": len(games),
        "candidates": len(candidates),
        "admitted": len(trades),
        "rejected": len(book.rejections),
        "reject_reasons": dict(reject_reasons),
        "audit_reasons": dict(Counter(a["reason"] for a in audit if a.get("reason"))),
        "max_open": book.max_open,
        "cap_respected": book.max_open <= 7,
        "net_pnl_cents": net,
        "gross_pnl_cents": gross,
        "fees_cents": fees,
        "gross_minus_fees": gross - fees,
        "ending_equity_cents": book.ending_equity_cents,
        "sport_net_cents": dict(by_sport),
        "sport_net_sums_to_total": sum(by_sport.values()) == net,
        "exit_reasons": dict(reasons),
        "game_wide_admitted": len(wide_book.trades),
        "game_wide_net_pnl_cents": sum(t["net_pnl_cents"] for t in wide_book.trades),
        "hold_admitted": len(hold_book.trades),
        "hold_net_pnl_cents": sum(t["net_pnl_cents"] for t in hold_book.trades),
        "paired_diff_sum_cents": sum(r["paired_diff_cents"] for r in paired),
        "drawdown": dd,
        "sharpe_daily": sharpe_daily,
        "monte_carlo": mc_summary,
        "elapsed_sec": round(time.time() - started, 3),
        "evidence": "FIRST78_CLOSE_PROXY",
        "launch_expectation": "NOT_YET_IDENTIFIABLE",
        "maker_execution": "UNAVAILABLE",
        "observed_executable_quotes": "UNAVAILABLE",
    }
    (RUN / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    state = git_state()
    manifest = {
        "run_id": RUN_ID,
        "git": state,
        "source_csv_sha256": sha256_file(REPO / "research/first80_asked_six_chatgpt_export/first80_asked_six.csv"),
        "summary": summary,
    }
    (RUN / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    findings = _findings(summary, stresses, markov)
    (RUN / "07_final_report" / "findings.md").write_text(findings, encoding="utf-8")
    (RUN / "07_final_report" / "limitations.md").write_text(_limitations(), encoding="utf-8")
    (RUN / "07_final_report" / "launch_assessment.md").write_text(_launch(), encoding="utf-8")
    (RUN / "review_bundle" / "review_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (RUN / "review_bundle" / "questions_for_review.md").write_text(_questions(), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("admitted", "net_pnl_cents", "max_open", "ending_equity_cents", "launch_expectation")}, indent=2))


def _findings(summary: dict, stresses: list[dict], markov: dict) -> str:
    return f"""# FIRST78→67 findings

Evidence tier: `FIRST78_CLOSE_PROXY` inside `THRESHOLD_ACCOUNTING_REFERENCE`.
This is an assumed-fill accounting path on minute bid closes. It is not a maker fill and not live P&L.

Population: {summary['locked_games']} locked derived-four games, conditional on a later FIRST80 in the window. Candidates after the contract-wise rule and the Nov 1–Apr 1 local window: {summary['candidates']}. Admitted: {summary['admitted']}. Rejected by the ledger: {summary['rejected']} ({summary['reject_reasons']}).

Headline rule: `CONTRACT_WISE_FIRST`. `GAME_WIDE_FIRST` is separate (admitted {summary['game_wide_admitted']}, net cents {summary['game_wide_net_cents']}).

Combined net P&L: {summary['net_pnl_cents']} cents. Gross {summary['gross_pnl_cents']} cents. Fees {summary['fees_cents']} cents. Gross minus fees equals net: {summary['gross_minus_fees'] == summary['net_pnl_cents']}. Ending realized-accounting equity: {summary['ending_equity_cents']} cents. Max concurrent positions: {summary['max_open']} (cap 7 respected: {summary['cap_respected']}).

Sport net cents (attribution of the one book): {summary['sport_net_cents']}. Sums to combined: {summary['sport_net_sums_to_total']}.

Exit reasons: {summary['exit_reasons']}.

Hold replay on the same selection rule admitted {summary['hold_admitted']} and netted {summary['hold_net_pnl_cents']} cents. Same-quantity paired stop-minus-hold sum: {summary['paired_diff_sum_cents']} cents. That paired sum is not the portfolio difference, because hold duration changes slots and later sizes.

Event-equity drawdown fraction: {summary['drawdown'].get('max_drawdown_fraction')}. This is realized accounting equity, not a bid-marked liquidation path.

Daily Sharpe object: `{json.dumps(summary['sharpe_daily'])}`.

Monte Carlo: {json.dumps(summary['monte_carlo'])}.

Markov completion-order transitions are descriptive: `{json.dumps(markov)}`.

Stresses (adverse entry/stop, fee coefficient 0.07, close_time cash hypothesis, strict batches) are in `05_profitability_dissection/stresses.csv`.

Launch expectation for November 1, 2026–April 1, 2027: NOT_YET_IDENTIFIABLE.
"""


def _limitations() -> str:
    return """# Limitations

- The 936-game book was selected because FIRST80 landed in the window. A 78¢ entry can occur before that 80¢ event. These results do not estimate every prospective FIRST78 opportunity.
- Minute `yes_bid_close` is not an executable quote, not available size, and not a maker fill. `OBSERVED_PRICE_REPLAY` and `MAKER_EXECUTION_REPLAY` are UNAVAILABLE. `NEXT_BAR_PRICE_PROXY` is a later close, not a buyable price.
- `close_time` is the trading-close lifecycle field. On the NBA market file it is always earlier than `settlement_time`. `expiration_time` is later still and is not treated as cash. Hold cash at `settlement_time` is a hypothesis.
- NBA intra-quarter seconds come from the period-bounded linear clock. They are modeled. NCAAB uses ESPN wall clocks, with interpolation only where a wall was missing inside a half.
- User fee coefficient 0.0175 with cent ceiling is a hypothetical. It is not proof of the 2025–26 Kalshi series schedule.
- No sealed Austin confirmation cohort was opened.
- Deflated Sharpe and probability of backtest overfitting are NOT_ESTIMABLE. The abandoned-trial history is incomplete.
- This run does not authorize live trading.
"""


def _launch() -> str:
    return """# Launch assessment

Target window: America/Los_Angeles [2026-11-01, 2027-04-02).
Status: NOT_YET_IDENTIFIABLE.

A prospective FIRST78 population is not the historical FIRST80-conditioned 936. Executable net expectancy is not identified from bid closes. No numerical launch expectation is reported.

Gates:
- data/ledger validity: see validation counts in summary.json
- population validity: FAIL for a deployable all-opportunity FIRST78 book; the historical conditional book is identified
- execution evidence: INSUFFICIENT_EVIDENCE
- prospective validation: INSUFFICIENT_EVIDENCE
- capacity: NOT_IDENTIFIED
- live authorization: REQUIRED_USER_INPUT
"""


def _questions() -> str:
    return """# Questions for review

1. Accounting: do event cash, fees, and ending equity reconcile to summary.json?
2. Is the historical result being read as conditional on FIRST80 membership?
3. Does the paired file separate same-quantity stop-versus-hold from the full hold replay?
4. Are executable economics still UNAVAILABLE?
5. Is the November 2026–April 2027 expectation left unidentified, rather than filled with the historical point estimate?
"""


if __name__ == "__main__":
    main()
