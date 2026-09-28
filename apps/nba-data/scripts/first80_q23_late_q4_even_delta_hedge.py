#!/usr/bin/env python3
"""NBA 2Q/3Q FIRST80 late-4Q even-delta hedge (research only).

For each frozen 2Q and 3Q FIRST80 trade and each close-path level L in
{40, 50, 60}:

- If L was close-touched at or before the 4Q 6:00 mark, treat as the
  original stop-at-L (those trades never enter the hedge).
- Else if held yes_bid_close < 75¢ at 4Q 6:00, taker-buy 1 opponent YES
  at that bar's opponent yes_ask_close (even delta).
- Else if held yes_bid_close first drops < 75¢ after 4Q 6:00 and before
  4Q 3:00, same even-delta taker hedge at that bar.
- Else hold the original YES to Kalshi settlement.

Lock P&L of 1 YES @ 80 + 1 opponent YES @ H is (100 − 80 − H) = 20 − H
cents, independent of which side settles.

Does not change live FIRST01 / 80/81/83/89. Candle path, not fills.
Does not invent L2, queue, or taker fees. Opponent ask is observed
candle ask, not 100 − held bid.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
GPE_DIR = SCRIPTS / "game_path_engine_v2"
if str(GPE_DIR) not in sys.path:
    sys.path.insert(0, str(GPE_DIR))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import first80_quarter_barrier_survival as Q  # noqa: E402
import nba_80_40_execution_audit as audit  # noqa: E402
from pbp import _interp_wall  # noqa: E402

ROOT = audit.ROOT
NORM = audit.NORM
GAMES_PATH = NORM / "games" / "nba_games.parquet"
TRADES_PATH = Q.OUT / "trades.parquet"
OUT = ROOT / "derived" / "nba" / "first80_q23_late_q4_even_delta_hedge"

EXPECTED_Q2 = 314
EXPECTED_Q3 = 290
ENTRY_BUCKETS = ("Q2", "Q3")
LEVELS = (40, 50, 60)
ENTRY_CENTS = 80
WIN_PNL_CENTS = 20
LOSE_HOLD_PNL_CENTS = -80
HEDGE_BELOW_E4 = 7500  # strictly below 75.00¢
MARK_6_S = 360
MARK_3_S = 180
Q4 = 4

PATH_EARLY = "EARLY_L_STOP"
PATH_HEDGE_A = "HEDGE_AT_6"
PATH_HEDGE_B = "HEDGE_6_TO_3"
PATH_UNHEDGED = "UNHEDGED"
PATH_NO_CLOCK = "NO_CLOCK"
PATH_UNPRICED = "HEDGE_UNPRICED"


class IdentityHalt(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def e4_to_cents(e4: int | None) -> int | None:
    if e4 is None:
        return None
    return int(e4) // 100


def stop_pnl_cents(level: int) -> int:
    return int(level) - ENTRY_CENTS


def lock_pnl_cents(opp_ask_cents: int) -> int:
    """Even-delta: +1 YES @ 80 + 1 opponent YES @ H → 20 − H."""
    return WIN_PNL_CENTS - int(opp_ask_cents)


def hold_pnl_cents(won: bool) -> int:
    return WIN_PNL_CENTS if won else LOSE_HOLD_PNL_CENTS


def touched_by_q4_6(
    touched: bool,
    period: int | None,
    remaining_s: float | None,
) -> bool | None:
    """Whether L was close-touched at or before 4Q 6:00 remaining.

    None = touched but clock unusable.
    """
    if not touched:
        return False
    if period is None or remaining_s is None:
        return None
    p = int(period)
    if p < Q4:
        return True
    if p == Q4:
        return float(remaining_s) >= float(MARK_6_S)
    return False


def period_knots(actions: list[dict], period: int) -> list[tuple[float, int]]:
    knots: list[tuple[float, int]] = []
    seen: set[float] = set()
    for r in actions:
        if r.get("period") != period:
            continue
        rem = r.get("remaining_s")
        wall = r.get("modeled_wall_ts")
        if rem is None or wall is None:
            continue
        key = round(float(rem), 2)
        if key in seen:
            continue
        seen.add(key)
        knots.append((float(rem), int(wall)))
    knots.sort(key=lambda t: -t[0])
    return knots


def wall_at_remaining(actions: list[dict], period: int, remaining_s: float) -> int | None:
    """Wallclock when period remaining hits `remaining_s`.

    If observed remaining never reaches the mark, return None (do not
    invent a later wall). If the first observed remaining is already
    past the mark, return that first observed wall.
    """
    knots = period_knots(actions, period)
    if not knots:
        return None
    target = float(remaining_s)
    if min(k[0] for k in knots) > target:
        return None
    return _interp_wall(target, knots)


def last_quality_at_or_before(
    quotes: list[dict],
    t0: int,
    ts: int,
    scan_end: int | None,
) -> dict | None:
    had_q = True
    last = None
    for q in quotes:
        if scan_end is not None and int(q["ts"]) > scan_end:
            continue
        if not audit.quality(q.get("bid_c"), q.get("ask_c"), q.get("vol"), had_q):
            continue
        had_q = True
        if int(q["ts"]) <= t0:
            continue
        if int(q["ts"]) > ts:
            break
        last = q
    return last


def first_bid_below_after(
    quotes: list[dict],
    t0: int,
    after_ts: int,
    before_ts: int,
    threshold_e4: int,
    scan_end: int | None,
) -> dict | None:
    """First tradable bar with after_ts < t < before_ts and bid < threshold."""
    had_q = True
    for q in quotes:
        ts = int(q["ts"])
        if scan_end is not None and ts > scan_end:
            continue
        if not audit.quality(q.get("bid_c"), q.get("ask_c"), q.get("vol"), had_q):
            continue
        had_q = True
        if ts <= t0 or ts <= after_ts:
            continue
        if ts >= before_ts:
            break
        bid = q.get("bid_c")
        if bid is not None and int(bid) < int(threshold_e4):
            return q
    return None


def pair_tickers(game: dict) -> list[str]:
    home = game.get("home_market_ticker")
    away = game.get("away_market_ticker")
    if home and away:
        return [str(home), str(away)]
    raw = game.get("market_tickers")
    if isinstance(raw, str):
        return [x.strip() for x in raw.split(",") if x.strip()]
    if isinstance(raw, list):
        return [str(x) for x in raw]
    return []


def opponent_of(game: dict | None, held: str) -> str | None:
    if not game:
        return None
    others = [t for t in pair_tickers(game) if t != held]
    if len(others) == 1:
        return others[0]
    return None


def classify_trade(
    *,
    won: bool,
    level: int,
    touched: bool,
    touch_period: int | None,
    touch_remaining_s: float | None,
    touch_ts: int | None = None,
    mark6: int | None,
    mark3: int | None,
    held_quotes: list[dict],
    opp_quotes: list[dict] | None,
    t0: int,
    scan_end: int | None,
) -> dict:
    """Classify one trade at one L. P&L in integer cents when priced."""
    early = touched_by_q4_6(touched, touch_period, touch_remaining_s)
    if early is None and touched and mark6 is not None and touch_ts is not None:
        early = int(touch_ts) <= int(mark6)
    base = {
        "level": level,
        "W": bool(won),
        "touched_L": bool(touched),
        "early_L": early,
        "path": None,
        "held_bid_e4": None,
        "opp_ask_e4": None,
        "hedge_ts": None,
        "hedge_H_cents": None,
        "pnl_cents": None,
        "priced": False,
        "reason": None,
    }

    if early is True:
        pnl = stop_pnl_cents(level)
        base.update(path=PATH_EARLY, pnl_cents=pnl, priced=True, reason="L_BEFORE_Q4_6")
        return base

    if early is None:
        base.update(path=PATH_NO_CLOCK, reason="TOUCH_CLOCK_MISSING")
        return base

    if mark6 is None or mark3 is None:
        base.update(path=PATH_NO_CLOCK, reason="Q4_MARK_MISSING")
        return base

    at6 = last_quality_at_or_before(held_quotes, t0, mark6, scan_end)
    if at6 is None or at6.get("bid_c") is None:
        base.update(path=PATH_NO_CLOCK, reason="NO_HELD_PRICE_AT_6")
        return base

    held6 = int(at6["bid_c"])
    base["held_bid_e4"] = held6

    hedge_q = None
    hedge_path = None
    if held6 < HEDGE_BELOW_E4:
        hedge_q = at6
        hedge_path = PATH_HEDGE_A
    else:
        later = first_bid_below_after(
            held_quotes, t0, mark6, mark3, HEDGE_BELOW_E4, scan_end
        )
        if later is not None:
            hedge_q = later
            hedge_path = PATH_HEDGE_B
            base["held_bid_e4"] = int(later["bid_c"])

    if hedge_q is None:
        pnl = hold_pnl_cents(won)
        base.update(
            path=PATH_UNHEDGED,
            pnl_cents=pnl,
            priced=True,
            reason="HELD_GE_75_THROUGH_WINDOW",
        )
        return base

    hedge_ts = int(hedge_q["ts"])
    base["hedge_ts"] = hedge_ts
    if not opp_quotes:
        base.update(path=PATH_UNPRICED, reason="OPPONENT_UNAVAILABLE")
        return base
    opp = last_quality_at_or_before(opp_quotes, t0, hedge_ts, scan_end)
    if opp is None or opp.get("ask_c") is None:
        base.update(path=PATH_UNPRICED, reason="OPPONENT_ASK_MISSING")
        return base
    ask_e4 = int(opp["ask_c"])
    h_cents = e4_to_cents(ask_e4)
    if h_cents is None:
        base.update(path=PATH_UNPRICED, reason="OPPONENT_ASK_MISSING")
        return base
    pnl = lock_pnl_cents(h_cents)
    base.update(
        path=hedge_path,
        opp_ask_e4=ask_e4,
        hedge_H_cents=h_cents,
        pnl_cents=pnl,
        priced=True,
        reason="EVEN_DELTA_TAKER_OPPONENT_ASK",
    )
    return base


def ev_from_pnls(pnls: list[int]) -> dict:
    n = len(pnls)
    if n <= 0:
        return {
            "n": 0,
            "sum_pnl_cents": 0,
            "ev_cents_per_contract": None,
            "ev_pct_of_1_dollar": None,
            "ev_pct_of_80_debit": None,
            "label": "GROSS CANDLE PATH — NOT A FILL — ZERO FEE",
        }
    total = int(sum(pnls))
    ev = total / n
    return {
        "n": n,
        "sum_pnl_cents": total,
        "ev_cents_per_contract": round(ev, 4),
        "ev_pct_of_1_dollar": round(ev, 4),
        "ev_pct_of_80_debit": round(ev / ENTRY_CENTS * 100.0, 4),
        "label": "GROSS CANDLE PATH — NOT A FILL — ZERO FEE",
    }


def rate(k: int, n: int) -> float | None:
    if n <= 0:
        return None
    return round(100.0 * k / n, 2)


def load_games() -> dict[str, dict]:
    pq = Q._pq()
    t = pq.read_table(GAMES_PATH)
    names = t.column_names
    out = {}
    for i in range(t.num_rows):
        row = {n: t.column(n)[i].as_py() for n in names}
        out[row["event_id"]] = row
    return out


def load_quarter_trades() -> list[dict]:
    pq = Q._pq()
    table = pq.read_table(TRADES_PATH)
    return table.to_pylist()


def load_quotes_for(tickers: set[str]) -> dict[str, list[dict]]:
    files = [p for p in Q.CANDLES_DIR.rglob("*.parquet") if p.stem in tickers]
    out: dict[str, list[dict]] = {}
    print(f"candle files {len(files)} / needed {len(tickers)}", flush=True)
    for i, path in enumerate(files, 1):
        if i == 1 or i == len(files) or i % 400 == 0:
            print(f"  scan {i}/{len(files)}", flush=True)
        out[path.stem] = Q.load_ticker_quotes(path)
    return out


def cell_summary(rows: list[dict], bucket: str, level: int) -> dict:
    sub = [r for r in rows if r["entry_quarter_bucket"] == bucket and r["level"] == level]
    n = len(sub)
    w = sum(1 for r in sub if r["W"])
    n_touch = sum(1 for r in sub if r["touched_L"])
    n_w_not = sum(1 for r in sub if r["W"] and not r["touched_L"])
    paths = Counter(r["path"] for r in sub)

    def of(path: str) -> list[dict]:
        return [r for r in sub if r["path"] == path]

    early = of(PATH_EARLY)
    ha = of(PATH_HEDGE_A)
    hb = of(PATH_HEDGE_B)
    unh = of(PATH_UNHEDGED)
    noclock = of(PATH_NO_CLOCK)
    unpriced = of(PATH_UNPRICED)
    hedged = ha + hb
    priced = [r for r in sub if r["priced"] and r["pnl_cents"] is not None]
    priced_hedged = [r for r in hedged if r["priced"] and r["pnl_cents"] is not None]

    unh_w = sum(1 for r in unh if r["W"])
    unh_l = len(unh) - unh_w
    hedge_w = sum(1 for r in priced_hedged if r["W"])
    hs = [int(r["hedge_H_cents"]) for r in priced_hedged if r.get("hedge_H_cents") is not None]
    mean_h = round(sum(hs) / len(hs), 2) if hs else None
    mean_lock = round(sum(lock_pnl_cents(h) for h in hs) / len(hs), 4) if hs else None

    hold = Q.ev_hold_gross(n, w)
    stop = Q.ev_stop_gross(n, n_w_not, n_touch, level)
    strat = ev_from_pnls([int(r["pnl_cents"]) for r in priced])
    vs_hold = None
    vs_stop = None
    if strat["ev_cents_per_contract"] is not None and hold["ev_cents_per_contract"] is not None:
        vs_hold = round(strat["ev_cents_per_contract"] - hold["ev_cents_per_contract"], 4)
    if strat["ev_cents_per_contract"] is not None and stop["ev_cents_per_contract"] is not None:
        vs_stop = round(strat["ev_cents_per_contract"] - stop["ev_cents_per_contract"], 4)

    return {
        "cell": f"{bucket} {level}",
        "bucket": bucket,
        "level": level,
        "n": n,
        "n_winners": w,
        "pct_win": rate(w, n),
        "n_touch_L": n_touch,
        "n_winner_before_touch": n_w_not,
        "pct_winner_before_touch": rate(n_w_not, n),
        "path_counts": {
            PATH_EARLY: len(early),
            PATH_HEDGE_A: len(ha),
            PATH_HEDGE_B: len(hb),
            PATH_UNHEDGED: len(unh),
            PATH_NO_CLOCK: len(noclock),
            PATH_UNPRICED: len(unpriced),
        },
        "n_hedged": len(hedged),
        "n_hedged_priced": len(priced_hedged),
        "n_unhedged": len(unh),
        "unhedged_won": unh_w,
        "unhedged_lost": unh_l,
        "pct_unhedged_won": rate(unh_w, len(unh)),
        "n_priced": len(priced),
        "n_residual": len(noclock) + len(unpriced),
        "mean_hedge_H_cents": mean_h,
        "mean_lock_pnl_cents": mean_lock,
        "n_hedge_winners_settlement": hedge_w,
        "ev_hold": hold,
        "ev_stop_L": stop,
        "ev_strategy_priced": strat,
        "vs_hold_cents": vs_hold,
        "vs_stop_L_cents": vs_stop,
        "unhedged_ev_hold": Q.ev_hold_gross(len(unh), unh_w),
        "hedge_ev": ev_from_pnls([int(r["pnl_cents"]) for r in priced_hedged]),
        "early_ev": ev_from_pnls([int(r["pnl_cents"]) for r in early if r["pnl_cents"] is not None]),
    }


def analyze() -> dict:
    frozen = Q.load_frozen_first80()
    identity = Q.halt_unless_identity(frozen)
    frozen_by_ticker = {t["ticker"]: t for t in frozen}
    ledger = load_quarter_trades()
    q23 = [r for r in ledger if r.get("entry_quarter_bucket") in ENTRY_BUCKETS]
    part = Counter(r["entry_quarter_bucket"] for r in q23)
    if part.get("Q2") != EXPECTED_Q2 or part.get("Q3") != EXPECTED_Q3:
        raise IdentityHalt(f"HALT Q2/Q3 partition {dict(part)}")
    if len(q23) != EXPECTED_Q2 + EXPECTED_Q3:
        raise IdentityHalt(f"HALT Q2+Q3 n={len(q23)}")

    games = load_games()
    xwalk = Q.load_crosswalk()
    pbp_cache: dict = {}
    held_tickers = {r["ticker"] for r in q23}
    opp_by_held: dict[str, str | None] = {}
    for r in q23:
        g = games.get(r.get("event_id"))
        opp_by_held[r["ticker"]] = opponent_of(g, r["ticker"])
    needed = set(held_tickers)
    needed.update(t for t in opp_by_held.values() if t)
    quotes = load_quotes_for(needed)

    rows = []
    for rec in q23:
        ticker = rec["ticker"]
        frozen_rec = frozen_by_ticker[ticker]
        t0 = int(rec["first_80_timestamp"])
        scan_end = Q.scan_window_end(frozen_rec)
        nba_id = rec.get("nba_game_id")
        packed = Q._pbp_pack(nba_id, pbp_cache) if nba_id else None
        actions = packed[0] if packed else []
        mark6 = wall_at_remaining(actions, Q4, MARK_6_S)
        mark3 = wall_at_remaining(actions, Q4, MARK_3_S)
        held_q = quotes.get(ticker) or []
        opp = opp_by_held.get(ticker)
        opp_q = quotes.get(opp) if opp else None
        won = bool(rec["W"])
        for level in LEVELS:
            touched = bool(rec.get(f"T{level}"))
            touch_ts = rec.get(f"t{level}_ts")
            classified = classify_trade(
                won=won,
                level=level,
                touched=touched,
                touch_period=rec.get(f"t{level}_period"),
                touch_remaining_s=rec.get(f"t{level}_period_remaining_s"),
                touch_ts=touch_ts,
                mark6=mark6,
                mark3=mark3,
                held_quotes=held_q,
                opp_quotes=opp_q,
                t0=t0,
                scan_end=scan_end,
            )
            rows.append(
                {
                    "event_id": rec.get("event_id"),
                    "ticker": ticker,
                    "opponent_ticker": opp,
                    "game_date": rec.get("game_date"),
                    "team": rec.get("team"),
                    "first_80_timestamp": t0,
                    "entry_quarter_bucket": rec["entry_quarter_bucket"],
                    "nba_game_id": nba_id,
                    "mark6_ts": mark6,
                    "mark3_ts": mark3,
                    "touch_ts": touch_ts,
                    "touch_period": rec.get(f"t{level}_period"),
                    "touch_period_remaining_s": rec.get(f"t{level}_period_remaining_s"),
                    **classified,
                }
            )

    cells = [cell_summary(rows, b, lv) for b in ENTRY_BUCKETS for lv in LEVELS]
    summary = {
        "written_utc": utc_now(),
        "research_only": True,
        "candle_path_not_fill": True,
        "live_execution_changed": False,
        "universe": "KXNBAGAME 2025-26 FIRST80 entry Q2 n=314 and Q3 n=290",
        "touch_definition": "first later tradable yes_bid_close <= L (close-path, not wick)",
        "hedge_definition": (
            "If L untouched by 4Q 6:00 remaining and held yes_bid_close < 75¢ "
            "at 4Q 6:00, or first such close after 4Q 6:00 and before 4Q 3:00, "
            "taker-buy 1 opponent YES at yes_ask_close. Even-delta lock = 20 − H."
        ),
        "early_L_definition": (
            "L close-touched in Q1–Q3, or in Q4 with remaining >= 360s. "
            "Those trades keep stop-at-L P&L and do not hedge."
        ),
        "clock_model": "PERIOD_BOUNDED_LINEAR_GAME_CLOCK",
        "hedge_threshold": "held yes_bid_close < 75.00¢ (7500 e4); 75 does not trigger",
        "opponent_fill": "opponent yes_ask_close (taker). Not 100-held_bid. Not a proven fill.",
        "fee": "ZERO — taker fee unresolved",
        "identity": identity,
        "partition": dict(part),
        "cells": cells,
        "unhedged_table": [
            {
                "cell": c["cell"],
                "n_unhedged": c["n_unhedged"],
                "won": c["unhedged_won"],
                "lost": c["unhedged_lost"],
                "pct_won": c["pct_unhedged_won"],
                "hold_ev_cents": c["unhedged_ev_hold"]["ev_cents_per_contract"],
            }
            for c in cells
        ],
        "backtest_table": [
            {
                "cell": c["cell"],
                "n": c["n"],
                "W_before_L": c["n_winner_before_touch"],
                "pct_W_before_L": c["pct_winner_before_touch"],
                "early_L_stop": c["path_counts"][PATH_EARLY],
                "hedge_at_6": c["path_counts"][PATH_HEDGE_A],
                "hedge_6_to_3": c["path_counts"][PATH_HEDGE_B],
                "unhedged": c["n_unhedged"],
                "unhedged_won": c["unhedged_won"],
                "unhedged_lost": c["unhedged_lost"],
                "residual": c["n_residual"],
                "mean_H": c["mean_hedge_H_cents"],
                "ev_hold": c["ev_hold"]["ev_cents_per_contract"],
                "ev_stop_L": c["ev_stop_L"]["ev_cents_per_contract"],
                "ev_strategy": c["ev_strategy_priced"]["ev_cents_per_contract"],
                "vs_hold": c["vs_hold_cents"],
                "vs_stop_L": c["vs_stop_L_cents"],
            }
            for c in cells
        ],
    }
    return {"summary": summary, "rows": rows}


def write_outputs(result: dict) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    OUT.mkdir(parents=True, exist_ok=True)
    summary = result["summary"]
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    pq.write_table(pa.Table.from_pylist(result["rows"]), OUT / "trades.parquet")
    print("wrote", OUT / "summary.json")
    for row in summary["backtest_table"]:
        print(
            row["cell"],
            "n",
            row["n"],
            "W¬L",
            row["pct_W_before_L"],
            "early",
            row["early_L_stop"],
            "H6",
            row["hedge_at_6"],
            "H63",
            row["hedge_6_to_3"],
            "unh",
            row["unhedged"],
            f"{row['unhedged_won']}W/{row['unhedged_lost']}L",
            "EV",
            row["ev_strategy"],
            "vs hold",
            row["vs_hold"],
            "vs stop",
            row["vs_stop_L"],
        )


def main() -> int:
    result = analyze()
    write_outputs(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
