#!/usr/bin/env python3
"""Asked-six FIRST80 path filter: 80 → peak∈[85,88] → 77 within 8m → 40.

Research only. Universe = published asked-six mid-game FIRST80 book:
  NBA Q2∪Q3, WNBA Q2∪Q3, NCAAB P5 vs P5 H1_2∪H2_1 (n=1,182).

Entry rule (close-path, quality-filtered, same as FIRST80 tape):
  1. Start at frozen first-80 timestamp (yes_bid_close ≥ 80).
  2. After that, must see a tradable close in [85, 88].
  3. Must never see a tradable close > 88 before entry.
  4. Then first tradable close ≤ 77 within ≤ 8 minutes of (1).
  5. Buy assumed at 77¢ (candle path — not a fill).

Exit: first later tradable close ≤ 40, else hold to expiration.
  WIN (survive + YES): +23¢
  STOP_40:            −37¢
  LOSS_HOLD (survive + NO): −77¢

Zero fee. Does not change live FIRST01. Does not invent L2.
Portfolio: $20k start, 5% SOD per bet, hard cap 6 taken / sport / day.
Historical compound on qualifying trades + Monte Carlo remix of the
observed outcome mix (clean −37 at 40; no 50/30/20 slip).
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

import importlib.util

SCRIPTS = Path(__file__).resolve().parent
WNBA_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/wnba-data/scripts")
NCAAB_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/ncaab-data/scripts")
for p in (SCRIPTS, NCAAB_SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


import nba_80_40_execution_audit as A  # noqa: E402

NBA_Q = _load_module(
    "nba_first80_quarter_barrier_survival_asked",
    SCRIPTS / "first80_quarter_barrier_survival.py",
)
WNBA_Q = _load_module(
    "wnba_first80_quarter_barrier_survival_asked",
    WNBA_SCRIPTS / "first80_quarter_barrier_survival.py",
)
NCAAB_Q = _load_module(
    "ncaab_first80_p5_half_barrier_survival_asked",
    NCAAB_SCRIPTS / "first80_p5_half_barrier_survival.py",
)

OUT = (
    Path(
        "/Users/user/Desktop/Momento/Backtesting Suite/Data/NBA/2025-2026/warehouse"
    )
    / "derived"
    / "nba"
    / "first80_asked_six_80_8588_77_8m_40"
)
DOCS = Path(
    "/Users/user/Desktop/Momento/docs/research/first80_asked_six_80_8588_77_8m_40"
)

HIT80_E4 = 8000
PEAK_LO_E4 = 8500
PEAK_HI_E4 = 8800
ENTRY_E4 = 7700
STOP_E4 = 4000
ENTRY_CENTS = 77
STOP_CENTS = 40
SETTLE_YES = 100
WINDOW_S = 8 * 60

PNL_WIN = SETTLE_YES - ENTRY_CENTS  # +23
PNL_STOP = STOP_CENTS - ENTRY_CENTS  # −37
PNL_LOSS_HOLD = 0 - ENTRY_CENTS  # −77

EXPECTED_ASKED = {"NBA": 604, "WNBA": 246, "NCAAB": 332}
EXPECTED_ASKED_TOTAL = 1182

B0_CENTS = 2_000_000  # $20,000
FRACTION_PCT = 5
MAX_PER_SPORT = 6
N_SIM = 10_000
SEED = 20260907


class IdentityHalt(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def wilson(k: int, n: int, z: float = 1.96):
    if n <= 0:
        return None, None, None
    p = k / n
    z2 = z * z
    den = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / den
    rad = z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n) / den
    return round(p * 100, 4), round(max(0.0, center - rad) * 100, 4), round(
        min(1.0, center + rad) * 100, 4
    )


def rate(num, den):
    if den == 0:
        return None
    return round(100.0 * num / den, 4)


def load_asked_six() -> list[dict]:
    """Frozen asked-six rows from published barrier-survival ledgers."""
    rows: list[dict] = []

    nba = pq.read_table(NBA_Q.OUT / "trades.parquet").to_pylist()
    for r in nba:
        if r.get("entry_quarter_bucket") not in ("Q2", "Q3"):
            continue
        rows.append(
            {
                **r,
                "sport": "NBA",
                "slice": r["entry_quarter_bucket"],
                "candles_dir": str(NBA_Q.CANDLES_DIR),
            }
        )

    wnba = pq.read_table(WNBA_Q.OUT / "trades.parquet").to_pylist()
    for r in wnba:
        if r.get("entry_quarter_bucket") not in ("Q2", "Q3"):
            continue
        rows.append(
            {
                **r,
                "sport": "WNBA",
                "slice": r["entry_quarter_bucket"],
                "candles_dir": str(WNBA_Q.CANDLES_DIR),
            }
        )

    ncaab = pq.read_table(NCAAB_Q.OUT / "trades.parquet").to_pylist()
    for r in ncaab:
        if r.get("entry_half_bucket") not in ("H1_2", "H2_1"):
            continue
        rows.append(
            {
                **r,
                "sport": "NCAAB",
                "slice": r["entry_half_bucket"],
                "entry_quarter_bucket": r.get("entry_half_bucket"),
                "candles_dir": str(NCAAB_Q.CANDLES_DIR),
            }
        )

    by_sport = Counter(r["sport"] for r in rows)
    for sport, n in EXPECTED_ASKED.items():
        if by_sport[sport] != n:
            raise IdentityHalt(f"HALT {sport} asked-six n={by_sport[sport]} expected {n}")
    if len(rows) != EXPECTED_ASKED_TOTAL:
        raise IdentityHalt(f"HALT total {len(rows)} expected {EXPECTED_ASKED_TOTAL}")
    return rows


def load_ticker_quotes(path: Path) -> list[dict]:
    cols = [
        "end_period_ts",
        "yes_bid_close_e4",
        "yes_ask_close_e4",
        "volume_hundredths",
        "is_valid",
    ]
    table = pq.read_table(path, columns=cols)
    get = {c: table.column(c) for c in cols}
    out = []
    for i in range(table.num_rows):
        if not get["is_valid"][i].as_py():
            continue
        out.append(
            {
                "ts": int(get["end_period_ts"][i].as_py()),
                "bid_c": A._opt_int(get["yes_bid_close_e4"][i].as_py()),
                "ask_c": A._opt_int(get["yes_ask_close_e4"][i].as_py()),
                "vol": A._opt_int(get["volume_hundredths"][i].as_py()),
            }
        )
    out.sort(key=lambda r: r["ts"])
    return out


def find_candle_file(candles_dir: Path, ticker: str) -> Path | None:
    hits = list(candles_dir.rglob(f"{ticker}.parquet"))
    return hits[0] if hits else None


def scan_entry_path(quotes: list[dict], f80_ts: int) -> dict:
    """Return entry qualification after first-80.

    reject reasons:
      NO_PEAK_85_88 — never close in [85,88] before deadline / entry
      PEAK_ABOVE_88 — saw close > 88 before entry
      NO_REVERT_77 — peaked ok but never ≤77 within 8m
      NO_QUOTES — empty / missing post-80 tape
    """
    deadline = int(f80_ts) + WINDOW_S
    had_q = True
    seen_peak = False
    peak_ts = None
    peak_px = None
    max_before_entry = None

    post = [q for q in quotes if q["ts"] > f80_ts]
    if not post:
        return {"qualified": False, "reject": "NO_QUOTES"}

    for q in post:
        if q["ts"] > deadline:
            break
        if not A.quality(q["bid_c"], q["ask_c"], q["vol"], had_q):
            continue
        had_q = True
        c = q["bid_c"]
        if c is None:
            continue
        if max_before_entry is None or c > max_before_entry:
            max_before_entry = c
        if c > PEAK_HI_E4:
            return {
                "qualified": False,
                "reject": "PEAK_ABOVE_88",
                "breach_ts": q["ts"],
                "breach_px_e4": c,
                "max_before_entry_e4": max_before_entry,
                "seen_peak": seen_peak,
                "peak_ts": peak_ts,
                "peak_px_e4": peak_px,
            }
        if PEAK_LO_E4 <= c <= PEAK_HI_E4:
            if (not seen_peak) or (peak_px is not None and c >= peak_px):
                seen_peak = True
                peak_ts = q["ts"]
                peak_px = c
            else:
                seen_peak = True
        if seen_peak and c <= ENTRY_E4:
            return {
                "qualified": True,
                "reject": None,
                "entry_ts": q["ts"],
                "entry_px_e4": c,
                "entry_minutes_after_80": round((q["ts"] - f80_ts) / 60.0, 4),
                "peak_ts": peak_ts,
                "peak_px_e4": peak_px,
                "max_before_entry_e4": max_before_entry,
                "seconds_after_80": q["ts"] - f80_ts,
            }

    if not seen_peak:
        return {
            "qualified": False,
            "reject": "NO_PEAK_85_88",
            "max_before_entry_e4": max_before_entry,
        }
    return {
        "qualified": False,
        "reject": "NO_REVERT_77",
        "peak_ts": peak_ts,
        "peak_px_e4": peak_px,
        "max_before_entry_e4": max_before_entry,
    }


def scan_exit_after_entry(quotes: list[dict], entry_ts: int) -> dict:
    had_q = True
    for q in quotes:
        if q["ts"] <= entry_ts:
            continue
        if not A.quality(q["bid_c"], q["ask_c"], q["vol"], had_q):
            continue
        had_q = True
        if q["bid_c"] is not None and q["bid_c"] <= STOP_E4:
            return {"t40": True, "t40_ts": q["ts"], "t40_px_e4": q["bid_c"]}
    return {"t40": False, "t40_ts": None, "t40_px_e4": None}


def outcome_of(won: bool, t40: bool) -> tuple[str, int]:
    if t40:
        return "STOP_40", PNL_STOP
    if won:
        return "WIN", PNL_WIN
    return "LOSS_HOLD", PNL_LOSS_HOLD


def evaluate_row(rec: dict, quotes: list[dict] | None) -> dict:
    f80 = int(rec["first_80_timestamp"])
    won = bool(rec["W"])
    base = {
        "sport": rec["sport"],
        "slice": rec["slice"],
        "event_id": rec.get("event_id"),
        "ticker": rec.get("ticker"),
        "game_date": rec.get("game_date"),
        "team": rec.get("team"),
        "first_80_timestamp": f80,
        "W": won,
        "book_T40_after_80": bool(rec.get("T40")),
    }
    if quotes is None:
        return {**base, "qualified": False, "reject": "MISSING_CANDLES"}
    path = scan_entry_path(quotes, f80)
    if not path["qualified"]:
        return {**base, **path, "outcome": None, "pnl_cents": None}
    ex = scan_exit_after_entry(quotes, path["entry_ts"])
    outcome, pnl = outcome_of(won, ex["t40"])
    return {
        **base,
        **path,
        **ex,
        "outcome": outcome,
        "pnl_cents": pnl,
    }


def joints(rows: list[dict]) -> dict:
    n = len(rows)
    w = sum(1 for r in rows if r["outcome"] == "WIN")
    stop = sum(1 for r in rows if r["outcome"] == "STOP_40")
    hold = sum(1 for r in rows if r["outcome"] == "LOSS_HOLD")
    wr, lo, hi = wilson(w, n)
    pnl = [r["pnl_cents"] for r in rows]
    total = sum(pnl) if n else 0
    ev = None if n == 0 else total / n
    return {
        "n": n,
        "WIN": w,
        "STOP_40": stop,
        "LOSS_HOLD": hold,
        "p_win_pct": wr,
        "p_win_ci95": [lo, hi],
        "p_stop_pct": rate(stop, n),
        "p_loss_hold_pct": rate(hold, n),
        "sum_pnl_cents": total,
        "ev_cents": None if ev is None else round(ev, 4),
        "ev_pct_of_77_debit": None if ev is None else round(ev / ENTRY_CENTS * 100.0, 4),
        "label": "GROSS CANDLE PATH — BUY@77 / STOP@40 / HOLD — ZERO FEE — NOT A FILL",
    }


def funnel(all_rows: list[dict]) -> dict:
    c = Counter(r.get("reject") or ("QUALIFIED" if r.get("qualified") else "UNKNOWN") for r in all_rows)
    return {
        "asked_six_n": len(all_rows),
        "qualified_n": sum(1 for r in all_rows if r.get("qualified")),
        "qualify_rate_pct": rate(sum(1 for r in all_rows if r.get("qualified")), len(all_rows)),
        "rejects": dict(c),
    }


def historical_portfolio(taken: list[dict]) -> dict:
    """Compound on actual chronological outcomes. Cap 6/sport/day."""
    by_day: dict[date, list[dict]] = defaultdict(list)
    for r in taken:
        by_day[date.fromisoformat(str(r["game_date"])[:10])].append(r)
    days = sorted(by_day)
    bank = B0_CENTS
    equity = [{"date": None, "bankroll_cents": bank, "taken": 0, "pnl_cents": 0}]
    dropped = 0
    taken_n = 0
    max_dd = 0
    peak = bank
    for d in days:
        sod = bank
        day_rows = sorted(by_day[d], key=lambda r: (int(r["entry_ts"]), r["ticker"] or ""))
        per_sport: dict[str, int] = defaultdict(int)
        day_pnl = 0
        day_taken = 0
        for r in day_rows:
            if per_sport[r["sport"]] >= MAX_PER_SPORT:
                dropped += 1
                continue
            debit = sod * FRACTION_PCT // 100
            contracts = debit // ENTRY_CENTS
            if contracts <= 0:
                dropped += 1
                continue
            pnl = int(r["pnl_cents"]) * contracts
            bank += pnl
            day_pnl += pnl
            day_taken += 1
            taken_n += 1
            per_sport[r["sport"]] += 1
            peak = max(peak, bank)
            max_dd = min(max_dd, bank - peak)
        equity.append(
            {
                "date": d.isoformat(),
                "bankroll_cents": bank,
                "taken": day_taken,
                "pnl_cents": day_pnl,
                "sod_cents": sod,
            }
        )
    return {
        "start_cents": B0_CENTS,
        "end_cents": bank,
        "end_dollars": round(bank / 100.0, 2),
        "multiple": round(bank / B0_CENTS, 4),
        "taken_bets": taken_n,
        "dropped_cap": dropped,
        "active_days": sum(1 for e in equity[1:] if e["taken"] > 0),
        "calendar_days": len(days),
        "max_drawdown_cents": max_dd,
        "max_drawdown_pct_of_peak": None
        if peak <= 0
        else round(100.0 * max_dd / peak, 4),
        "fraction_pct_per_bet": FRACTION_PCT,
        "max_per_sport_per_day": MAX_PER_SPORT,
        "entry_cents": ENTRY_CENTS,
        "equity_curve": equity,
    }


def monte_carlo(taken: list[dict]) -> dict:
    """Remix observed outcomes onto the observed daily arrival vector."""
    if not taken:
        return {"n_sim": 0, "note": "no qualifying trades"}
    outcomes = np.array([r["pnl_cents"] for r in taken], dtype=np.int64)
    by_day: dict[date, list[dict]] = defaultdict(list)
    for r in taken:
        by_day[date.fromisoformat(str(r["game_date"])[:10])].append(r)
    days = sorted(by_day)
    daily_counts = []
    for d in days:
        # respect sport caps the same way as historical
        per_sport: dict[str, int] = defaultdict(int)
        n = 0
        for r in sorted(by_day[d], key=lambda x: int(x["entry_ts"])):
            if per_sport[r["sport"]] >= MAX_PER_SPORT:
                continue
            per_sport[r["sport"]] += 1
            n += 1
        if n:
            daily_counts.append(n)
    daily_counts = np.array(daily_counts, dtype=np.int64)
    rng = np.random.default_rng(SEED)
    ends = np.empty(N_SIM, dtype=np.int64)
    mins = np.empty(N_SIM, dtype=np.int64)
    dds = np.empty(N_SIM, dtype=np.int64)
    for i in range(N_SIM):
        b = B0_CENTS
        peak = b
        mn = b
        mdd = 0
        for n in daily_counts:
            sod = b
            contracts = (sod * FRACTION_PCT // 100) // ENTRY_CENTS
            if contracts <= 0:
                continue
            pnl_each = rng.choice(outcomes, size=int(n), replace=True)
            b += int(pnl_each.sum() * contracts)
            peak = max(peak, b)
            mn = min(mn, b)
            mdd = min(mdd, b - peak)
        ends[i] = b
        mins[i] = mn
        dds[i] = mdd
    def pct(a, p):
        return int(np.percentile(a, p))

    return {
        "n_sim": N_SIM,
        "seed": SEED,
        "arrival": "observed qualifying days with 6/sport cap",
        "outcome_mix": "bootstrap of realized +23/−37/−77 path P&L",
        "end_median_cents": int(np.median(ends)),
        "end_mean_cents": int(round(float(ends.mean()))),
        "end_p05_cents": pct(ends, 5),
        "end_p25_cents": pct(ends, 25),
        "end_p75_cents": pct(ends, 75),
        "end_p95_cents": pct(ends, 95),
        "end_median_dollars": round(float(np.median(ends)) / 100.0, 2),
        "end_p05_dollars": round(pct(ends, 5) / 100.0, 2),
        "end_p95_dollars": round(pct(ends, 95) / 100.0, 2),
        "multiple_median": round(float(np.median(ends)) / B0_CENTS, 4),
        "p_end_above_start_pct": round(100.0 * float(np.mean(ends > B0_CENTS)), 2),
        "p_end_below_half_pct": round(100.0 * float(np.mean(ends < B0_CENTS // 2)), 2),
        "p_touch_below_5k_pct": round(
            100.0 * float(np.mean(mins < 500_000)), 2
        ),
        "max_dd_median_cents": int(np.median(dds)),
    }


def run() -> dict:
    asked = load_asked_six()
    # Index candle files once per sport dir.
    candle_index: dict[str, dict[str, Path]] = {}
    for sport_dir in {r["candles_dir"] for r in asked}:
        root = Path(sport_dir)
        idx = {}
        for p in root.rglob("*.parquet"):
            idx[p.stem] = p
        candle_index[sport_dir] = idx

    evaluated = []
    for rec in asked:
        path = candle_index[rec["candles_dir"]].get(rec["ticker"])
        quotes = load_ticker_quotes(path) if path else None
        evaluated.append(evaluate_row(rec, quotes))

    taken = [r for r in evaluated if r.get("qualified")]
    taken.sort(key=lambda r: (str(r["game_date"]), int(r["entry_ts"]), r["ticker"] or ""))

    by_sport = {}
    for sport in ("NBA", "WNBA", "NCAAB"):
        sub_all = [r for r in evaluated if r["sport"] == sport]
        sub_q = [r for r in sub_all if r.get("qualified")]
        by_sport[sport] = {
            "funnel": funnel(sub_all),
            "backtest": joints(sub_q),
            "by_slice": {
                sl: joints([r for r in sub_q if r["slice"] == sl])
                for sl in sorted({r["slice"] for r in sub_q})
            },
        }

    hist = historical_portfolio(taken)
    mc = monte_carlo(taken)

    summary = {
        "generated_at_utc": utc_now(),
        "rule": {
            "universe": "asked-six FIRST80 (NBA Q2∪Q3, WNBA Q2∪Q3, NCAAB P5 H1_2∪H2_1)",
            "path": "first80 → close∈[85,88] → close≤77 within 8 minutes of first80; reject if close>88 before entry",
            "buy": "77¢ (assumed on first ≤77 close)",
            "exit": "first later close ≤40 else hold to expiration",
            "pnl": {"WIN": PNL_WIN, "STOP_40": PNL_STOP, "LOSS_HOLD": PNL_LOSS_HOLD},
            "path_basis": "tradable yes_bid_close, quality filter, 1m candles",
            "fees": "ZERO",
            "fills": "NOT MODELED — candle path only",
        },
        "identity": {
            "asked_six_by_sport": EXPECTED_ASKED,
            "asked_six_total": EXPECTED_ASKED_TOTAL,
            "halted": False,
        },
        "funnel": funnel(evaluated),
        "backtest_pooled": joints(taken),
        "by_sport": by_sport,
        "portfolio_historical": {
            k: v for k, v in hist.items() if k != "equity_curve"
        },
        "portfolio_historical_equity": hist["equity_curve"],
        "portfolio_monte_carlo": mc,
    }
    return summary, evaluated, taken


def main() -> int:
    summary, evaluated, taken = run()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (DOCS / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    pq.write_table(pa.Table.from_pylist(evaluated), OUT / "evaluated.parquet")
    if taken:
        pq.write_table(pa.Table.from_pylist(taken), OUT / "qualified.parquet")
    # Compact markdown
    f = summary["funnel"]
    b = summary["backtest_pooled"]
    h = summary["portfolio_historical"]
    m = summary["portfolio_monte_carlo"]
    lines = [
        "# Asked-six 80 → [85,88] → 77/8m → 40",
        "",
        f"Generated: {summary['generated_at_utc']}",
        "",
        "## Funnel",
        f"- Asked-six n = **{f['asked_six_n']}**",
        f"- Qualified = **{f['qualified_n']}** ({f['qualify_rate_pct']}%)",
        f"- Rejects: `{json.dumps(f['rejects'])}`",
        "",
        "## Backtest (qualified)",
        f"- n={b['n']} WIN={b['WIN']} STOP_40={b['STOP_40']} LOSS_HOLD={b['LOSS_HOLD']}",
        f"- P(WIN)={b['p_win_pct']}% CI95={b['p_win_ci95']}",
        f"- EV={b['ev_cents']}¢/contract ({b['ev_pct_of_77_debit']}% of 77¢ debit)",
        "",
        "## Portfolio ($20k, 5% SOD, ≤6/sport/day)",
        f"- Historical end = **${h['end_dollars']}** ({h['multiple']}×), taken={h['taken_bets']}, dropped={h['dropped_cap']}",
        f"- MC median end = **${m.get('end_median_dollars')}** (p05=${m.get('end_p05_dollars')}, p95=${m.get('end_p95_dollars')})",
        f"- P(end>start)={m.get('p_end_above_start_pct')}%",
        "",
        "Candle path, zero fee, not a fill. Live FIRST01 unchanged.",
        "",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines))
    (DOCS / "REPORT.md").write_text("\n".join(lines))
    print(json.dumps({"funnel": f, "backtest": b, "historical": h, "mc": m}, indent=2))
    print("wrote", OUT / "summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
