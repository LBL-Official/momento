"""Baseline replays. This module does not import the oracle bounds."""

from __future__ import annotations

import random
from decimal import Decimal

from first78.money import fee_charged_cents, fee_raw
from first78.portfolio import replay
from first78.stats import max_drawdown

from oos_adverse.eligibility import local_day

FEE = Decimal("0.0175")
BASELINE = (
    "REF",
    "ENTRY_1",
    "ENTRY_2",
    "EXIT_1",
    "EXIT_2",
    "JOINT_1",
    "JOINT_2",
    "FEE_007",
    "JOINT_2_FEE_007",
    "CASH_DELAY_15",
    "CASH_DELAY_60",
    "STOP_FAIL_1",
    "STOP_FAIL_5",
    "LATENCY_60",
    "LATENCY_120",
)
SPECS = {
    "REF": {"entry": 78, "stop": 67, "fee": FEE},
    "ENTRY_1": {"entry": 79, "stop": 67, "fee": FEE},
    "ENTRY_2": {"entry": 80, "stop": 67, "fee": FEE},
    "EXIT_1": {"entry": 78, "stop": 66, "fee": FEE},
    "EXIT_2": {"entry": 78, "stop": 65, "fee": FEE},
    "JOINT_1": {"entry": 79, "stop": 66, "fee": FEE},
    "JOINT_2": {"entry": 80, "stop": 65, "fee": FEE},
    "FEE_007": {"entry": 78, "stop": 67, "fee": Decimal("0.07")},
    "JOINT_2_FEE_007": {"entry": 80, "stop": 65, "fee": Decimal("0.07")},
    "CASH_DELAY_15": {"entry": 78, "stop": 67, "fee": FEE, "delay": 900},
    "CASH_DELAY_60": {"entry": 78, "stop": 67, "fee": FEE, "delay": 3600},
    "STOP_FAIL_1": {"entry": 78, "stop": 67, "fee": FEE, "fail_rate": 0.01},
    "STOP_FAIL_5": {"entry": 78, "stop": 67, "fee": FEE, "fail_rate": 0.05},
    "LATENCY_60": {"entry": None, "stop": 67, "fee": FEE, "latency": 60},
    "LATENCY_120": {"entry": None, "stop": 67, "fee": FEE, "latency": 120},
}


def assert_baseline(scenario_id: str) -> None:
    if scenario_id not in BASELINE or scenario_id.startswith("ORACLE"):
        raise RuntimeError(f"not a baseline scenario: {scenario_id}")


def _ready(cands: list[dict], spec: dict) -> list[dict]:
    rows = []
    for cand in cands:
        row = {
            "game_id": cand["game_id"],
            "contract_id": cand["contract_id"],
            "sport": cand["sport"],
            "signal_ts": int(cand["signal_ts"]),
            "exit_ts": int(cand["exit_ts"]),
            "cash_ts": int(cand["cash_ts"]) + int(spec.get("delay") or 0),
            "exit_reason": cand["exit_reason"],
            "local_day": cand["local_day"],
        }
        if spec.get("entry") is None:
            row["entry_price_cents"] = int(cand.get("entry_price_cents") or 78)
        else:
            row["entry_price_cents"] = int(spec["entry"])
        row["stop_price_cents"] = int(spec["stop"])
        if row["cash_ts"] < row["exit_ts"] or row["exit_ts"] < row["signal_ts"]:
            continue
        rows.append(row)
    return rows


def play(cands: list[dict], scenario_id: str, *, balance_cents: int = 2_000_000, cap: int = 7):
    assert_baseline(scenario_id)
    spec = SPECS[scenario_id]
    return replay(_ready(cands, spec), balance_cents=balance_cents, cap=cap, fee_coef=spec["fee"])


def with_stop_failures(cands: list[dict], fail_ids: set[str]) -> list[dict]:
    out = []
    for cand in cands:
        if cand["game_id"] not in fail_ids or cand["exit_reason"] != "STOP":
            out.append(cand)
            continue
        result = cand.get("terminal_result")
        settlement = cand.get("settlement_ts")
        if result not in {"yes", "no"} or settlement is None or int(settlement) < int(cand["signal_ts"]):
            out.append(cand)
            continue
        out.append(
            {
                **cand,
                "exit_reason": "WIN_SETTLEMENT" if result == "yes" else "LOSS_SETTLEMENT",
                "exit_ts": int(settlement),
                "cash_ts": int(settlement),
            }
        )
    return out


def latency_candidates(cands: list[dict], delay: int, extra: int = 60) -> tuple[list[dict], list[dict]]:
    kept = []
    skipped = []
    for cand in cands:
        bars = cand.get("bars") or []
        start = int(cand["signal_ts"]) + delay
        limit = start + extra
        window = [bar for bar in bars if start <= int(bar["ts"]) <= limit and bar.get("bid") is not None]
        if not window:
            skipped.append({"game_id": cand["game_id"], "reason": "LATENCY_GAP_UNRESOLVED"})
            continue
        entry = window[0]
        if any(
            int(cand["signal_ts"]) < int(bar["ts"]) <= int(entry["ts"]) and bar.get("bid") is not None and bar["bid"] <= 6700
            for bar in bars
        ):
            skipped.append({"game_id": cand["game_id"], "reason": "STOP_ALREADY_TRUE"})
            continue
        price = int(entry["bid"]) // 100
        if price <= 67 or price >= 100:
            skipped.append({"game_id": cand["game_id"], "reason": "PRICE_NOT_ABOVE_STOP"})
            continue
        nxt = dict(cand)
        nxt["signal_ts"] = int(entry["ts"])
        nxt["entry_price_cents"] = price
        nxt["local_day"] = local_day(nxt["signal_ts"])
        nxt["evidence"] = "NEXT_BAR_PRICE_PROXY"
        later = next((bar for bar in bars if int(bar["ts"]) > int(entry["ts"]) and bar.get("bid") is not None and bar["bid"] <= 6700), None)
        if later is not None:
            nxt["exit_reason"] = "STOP"
            nxt["exit_ts"] = int(later["ts"])
            nxt["cash_ts"] = int(later["ts"])
        elif int(cand["exit_ts"]) < nxt["signal_ts"]:
            skipped.append({"game_id": cand["game_id"], "reason": "UNRESOLVED_EXIT"})
            continue
        kept.append(nxt)
    return kept, skipped


def hold_candidates(cands: list[dict]) -> list[dict]:
    out = []
    for cand in cands:
        result = cand.get("terminal_result")
        settlement = cand.get("settlement_ts")
        if result not in {"yes", "no"} or settlement is None or int(settlement) < int(cand["signal_ts"]):
            continue
        out.append(
            {
                **cand,
                "exit_reason": "WIN_SETTLEMENT" if result == "yes" else "LOSS_SETTLEMENT",
                "exit_ts": int(settlement),
                "cash_ts": int(settlement),
            }
        )
    return out


def book_net(book) -> int:
    return sum(int(trade["net_pnl_cents"]) for trade in book.trades)


def annotate(book, cands: list[dict]) -> list[dict]:
    meta = {c["game_id"]: c for c in cands}
    rows = []
    for trade in book.trades:
        src = meta.get(trade["game_id"], {})
        row = dict(trade)
        row["local_day"] = src.get("local_day")
        row["terminal_result"] = src.get("terminal_result")
        row["event_id"] = src.get("event_id")
        rows.append(row)
    return rows


def block_summaries(cands: list[dict], *, n_paths: int, seed: int) -> list[dict]:
    by_day: dict[str, list[dict]] = {}
    for cand in cands:
        by_day.setdefault(cand["local_day"], []).append(cand)
    days = sorted(by_day)
    if len(days) < 2:
        return [{"block_days": block, "status": "INSUFFICIENT_DAYS", "n_days": len(days)} for block in (1, 3, 7)]
    out = []
    for block in (1, 3, 7):
        rng = random.Random(seed + block)
        span = max(1, len(days) - block + 1)
        endings = []
        drawdowns = []
        for i in range(n_paths):
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
                    nxt = {k: v for k, v in cand.items() if k not in {"bars"}}
                    nxt["signal_ts"] = int(cand["signal_ts"]) + shift
                    nxt["exit_ts"] = int(cand["exit_ts"]) + shift
                    nxt["cash_ts"] = int(cand["cash_ts"]) + shift
                    nxt["game_id"] = f"{cand['game_id']}-b{i}-{shift}"
                    built.append(nxt)
                cursor += 86400 * block + 5
            book = play(built, "REF")
            equity = [2_000_000] + [int(event["equity_cents"]) for event in book.events]
            endings.append(book.ending_equity_cents)
            drawdowns.append(max_drawdown(equity)["max_drawdown_fraction"])
        endings.sort()
        drawdowns.sort()
        out.append(
            {
                "block_days": block,
                "status": "DESCRIPTIVE",
                "paths": len(endings),
                "seed": seed + block,
                "ending_p50": endings[len(endings) // 2],
                "drawdown_p95": drawdowns[int(0.95 * (len(drawdowns) - 1))],
                "p_drawdown_above_10pct": sum(1 for value in drawdowns if value > 0.10) / len(drawdowns),
                "label": "DESCRIPTIVE_SHORT_CALENDAR",
            }
        )
    return out


def paired_rows(trades: list[dict], cands: list[dict]) -> list[dict]:
    meta = {c["game_id"]: c for c in cands}
    rows = []
    for trade in trades:
        src = meta.get(trade["game_id"])
        if src is None or src.get("terminal_result") not in {"yes", "no"}:
            continue
        contracts = int(trade["contracts"])
        entry = int(trade["entry_price_cents"])
        entry_fee = fee_charged_cents(fee_raw(contracts, entry, FEE))
        payout = contracts * (100 if src["terminal_result"] == "yes" else 0)
        hold_net = payout - contracts * entry - entry_fee
        rows.append(
            {
                "trade_id": trade["trade_id"],
                "game_id": trade["game_id"],
                "sport": trade["sport"],
                "stop_net_cents": int(trade["net_pnl_cents"]),
                "hold_net_same_quantity_cents": hold_net,
                "stop_minus_hold_cents": int(trade["net_pnl_cents"]) - hold_net,
            }
        )
    return rows
