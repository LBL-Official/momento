#!/usr/bin/env python3
"""Combined NBA 2Q+3Q + NCAAB P5 H1_2∪H2_1 FIRST80 portfolio sim.

Research only. One bankroll. 5% of start-of-day bankroll per bet.
Hard cap 6 taken bets *per sport* per calendar day (first 6 by
first_80_timestamp). A day with both sports can take 12 bets / 60% SOD.
That is the financial change versus the NBA-only 6 / 30% night.

Arrival is the overlaid 2025-26 analog:
  NBA Q2∪Q3 Nov 1–Apr 12 (508 prints → 499 taken)
  NCAAB P5 H1_2∪H2_1 Nov 7–Apr 4 (332 prints → 269 taken)

Outcomes: 50/30/20 loser slip on the 40 signal. Each sport draws from
its own frozen book. P&L haircut locks expected debit return at 3.000%
*per bet* (same conservative overlay as the NBA-only sim). Winner-touches
stay −40¢. Same-day bets share SOD size. Compound after the day.

Zero fee. Candle path. Does not change live FIRST01. Does not invent L2.
Does not invent extra NCAAB prints from the 76-team 2027 tournament.
Sports are drawn independently — slate correlation is not in the book.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parent
NCAAB_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/ncaab-data/scripts")
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(NCAAB_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(NCAAB_SCRIPTS))

import first80_p5_h12_h21_profit_likelihood as NC  # noqa: E402
import first80_q23_novapr_portfolio_sim as NBA  # noqa: E402

OUT = NBA.Q.OUT.parent / "first80_dual_sport_novapr_portfolio_sim"

WINDOW_START = NBA.WINDOW_START  # 2025-11-01
WINDOW_END = NBA.WINDOW_END  # 2026-04-12
PROJECT_START = date(2026, 11, 1)
PROJECT_END = date(2027, 4, 11)

EXPECTED_NBA_PRINTS = 508
EXPECTED_NCAAB_PRINTS = 332
EXPECTED_NBA_TAKEN = 499
EXPECTED_NCAAB_TAKEN = 269
EXPECTED_TAKEN = EXPECTED_NBA_TAKEN + EXPECTED_NCAAB_TAKEN  # 768
EXPECTED_NBA_DROPPED = 9
EXPECTED_NCAAB_DROPPED = 63
EXPECTED_BOTH_DAYS = 82
EXPECTED_NBA_ONLY_DAYS = 64
EXPECTED_NCAAB_ONLY_DAYS = 7
EXPECTED_ACTIVE_DAYS = 153
EXPECTED_CALENDAR_DAYS = 163
EXPECTED_WEEKS = 24
EXPECTED_DAYS_AT_12 = 4
EXPECTED_MAX_TAKEN = 12

# NCAAB 332 book raw 50/30/20: 250*(+20)+31*(−40)+51*(−52)=1,108¢
# Haircut so E[pnl]=2.4¢: 2.4*332/1108 = 996/1385.
NCAAB_SURVIVE = 250
NCAAB_WTOUCH = 31
NCAAB_LOSE = 51
NCAAB_N = 332
NCAAB_RAW_BOOK_SUM = 1108
NCAAB_EDGE_NUM = 996
NCAAB_EDGE_DEN = 1385

N_SIM = 10_000
SEED = 20260905
MAX_PER_SPORT = 6
FRACTION_PCT = NBA.FRACTION_PCT  # 5
ENTRY = NBA.ENTRY_CENTS  # 80
B0 = NBA.B0_CENTS
PNL_TABLE = NBA.PNL_TABLE

SPORT_NBA = 0
SPORT_NCAAB = 1


class IdentityHalt(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ncaab_mix_probs() -> np.ndarray:
    weights = (
        NCAAB_SURVIVE * 10,
        NCAAB_WTOUCH * 10,
        NCAAB_LOSE * NBA.LOSE_AT_40_WGT // 10,
        NCAAB_LOSE * NBA.LOSE_AT_20_WGT // 10,
        NCAAB_LOSE * NBA.LOSE_AT_10_WGT // 10,
    )
    if sum(weights) != NCAAB_N * 10:
        raise IdentityHalt(f"HALT ncaab weights {weights}")
    if NCAAB_RAW_BOOK_SUM != 1108:
        raise IdentityHalt("HALT ncaab raw book")
    return np.array(weights, dtype=np.float64) / (NCAAB_N * 10)


def scale_edge(raw_pnl_cents: np.ndarray, num: int, den: int) -> np.ndarray:
    raw = raw_pnl_cents.astype(np.int64) * num
    pos = raw >= 0
    mag = np.where(pos, raw, -raw)
    rounded = (mag + den // 2) // den
    return np.where(pos, rounded, -rounded)


def ncaab_raw_debit_return_pct() -> float:
    ev = float(ncaab_mix_probs() @ PNL_TABLE.astype(np.float64))
    return ev / ENTRY * 100.0


def load_overlay() -> dict:
    nba_rows = NBA.window_rows()
    ncaab_rows = NC.load_book_rows()
    if len(nba_rows) != EXPECTED_NBA_PRINTS:
        raise IdentityHalt(f"HALT nba n={len(nba_rows)}")
    if len(ncaab_rows) != EXPECTED_NCAAB_PRINTS:
        raise IdentityHalt(f"HALT ncaab n={len(ncaab_rows)}")
    days = NBA.calendar_days(WINDOW_START, WINDOW_END)
    if len(days) != EXPECTED_CALENDAR_DAYS:
        raise IdentityHalt(f"HALT calendar {len(days)}")
    nba_by: dict[date, list] = defaultdict(list)
    ncaab_by: dict[date, list] = defaultdict(list)
    for r in nba_rows:
        nba_by[NBA.game_date_of(r)].append(r)
    for r in ncaab_rows:
        ncaab_by[date.fromisoformat(str(r["game_date"])[:10])].append(r)
    nba_n = []
    ncaab_n = []
    nba_taken = []
    ncaab_taken = []
    for d in days:
        a = sorted(nba_by[d], key=lambda r: int(r["first_80_timestamp"]))
        b = sorted(ncaab_by[d], key=lambda r: int(r["first_80_timestamp"]))
        nba_n.append(len(a))
        ncaab_n.append(len(b))
        nba_taken.append(min(MAX_PER_SPORT, len(a)))
        ncaab_taken.append(min(MAX_PER_SPORT, len(b)))
    if sum(nba_n) != EXPECTED_NBA_PRINTS or sum(ncaab_n) != EXPECTED_NCAAB_PRINTS:
        raise IdentityHalt("HALT print sums")
    if sum(nba_taken) != EXPECTED_NBA_TAKEN or sum(ncaab_taken) != EXPECTED_NCAAB_TAKEN:
        raise IdentityHalt(f"HALT taken {sum(nba_taken)} {sum(ncaab_taken)}")
    both = sum(1 for a, b in zip(nba_n, ncaab_n) if a and b)
    nba_only = sum(1 for a, b in zip(nba_n, ncaab_n) if a and not b)
    ncaab_only = sum(1 for a, b in zip(nba_n, ncaab_n) if b and not a)
    active = sum(1 for a, b in zip(nba_n, ncaab_n) if a or b)
    taken_day = [a + b for a, b in zip(nba_taken, ncaab_taken)]
    if both != EXPECTED_BOTH_DAYS or nba_only != EXPECTED_NBA_ONLY_DAYS:
        raise IdentityHalt(f"HALT overlap {both} {nba_only} {ncaab_only}")
    if ncaab_only != EXPECTED_NCAAB_ONLY_DAYS or active != EXPECTED_ACTIVE_DAYS:
        raise IdentityHalt(f"HALT active {active} ncaab_only {ncaab_only}")
    if max(taken_day) != EXPECTED_MAX_TAKEN:
        raise IdentityHalt(f"HALT max taken {max(taken_day)}")
    if sum(1 for n in taken_day if n == 12) != EXPECTED_DAYS_AT_12:
        raise IdentityHalt("HALT days at 12")
    week_keys = []
    seen = set()
    for d in days:
        k = NBA.iso_week_key(d)
        if k not in seen:
            seen.add(k)
            week_keys.append(k)
    if len(week_keys) != EXPECTED_WEEKS:
        raise IdentityHalt(f"HALT weeks {len(week_keys)}")
    week_taken = defaultdict(int)
    week_nba = defaultdict(int)
    week_ncaab = defaultdict(int)
    for d, a, b in zip(days, nba_taken, ncaab_taken):
        k = NBA.iso_week_key(d)
        week_taken[k] += a + b
        week_nba[k] += a
        week_ncaab[k] += b
    return {
        "days": days,
        "nba_prints": nba_n,
        "ncaab_prints": ncaab_n,
        "nba_taken": nba_taken,
        "ncaab_taken": ncaab_taken,
        "taken": taken_day,
        "week_keys": week_keys,
        "week_taken": [week_taken[k] for k in week_keys],
        "week_nba": [week_nba[k] for k in week_keys],
        "week_ncaab": [week_ncaab[k] for k in week_keys],
        "week_labels": [f"{y}-W{w:02d}" for y, w in week_keys],
        "both_days": both,
        "nba_only_days": nba_only,
        "ncaab_only_days": ncaab_only,
        "active_days": active,
        "max_combined_prints": max(a + b for a, b in zip(nba_n, ncaab_n)),
        "max_combined_taken": max(taken_day),
        "days_at_12": sum(1 for n in taken_day if n == 12),
        "days_taken_ge_10": sum(1 for n in taken_day if n >= 10),
        "nba_days_over_cap": sum(1 for n in nba_n if n > MAX_PER_SPORT),
        "ncaab_days_over_cap": sum(1 for n in ncaab_n if n > MAX_PER_SPORT),
    }


def trade_schedule(nba_taken: list[int], ncaab_taken: list[int]) -> tuple[np.ndarray, np.ndarray]:
    """Per-trade sport id, grouped by day. NBA block then NCAAB block."""
    sports = []
    day_n = []
    for a, b in zip(nba_taken, ncaab_taken):
        sports.extend([SPORT_NBA] * a)
        sports.extend([SPORT_NCAAB] * b)
        day_n.append(a + b)
    return np.array(sports, dtype=np.int64), np.array(day_n, dtype=np.int64)


def draw_pnl(sports: np.ndarray, n_sim: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    nba_p = NBA.mix_probs_604()
    ncaab_p = ncaab_mix_probs()
    n = len(sports)
    draws = np.empty((n_sim, n), dtype=np.int64)
    nba_idx = np.where(sports == SPORT_NBA)[0]
    ncaab_idx = np.where(sports == SPORT_NCAAB)[0]
    if len(nba_idx):
        draws[:, nba_idx] = rng.choice(5, size=(n_sim, len(nba_idx)), p=nba_p)
    if len(ncaab_idx):
        draws[:, ncaab_idx] = rng.choice(5, size=(n_sim, len(ncaab_idx)), p=ncaab_p)
    return PNL_TABLE[draws]


def apply_sport_edge(raw: np.ndarray, sports_slice: np.ndarray) -> np.ndarray:
    """raw shape (n_sim, n_day_trades). Scale each column by its sport."""
    out = np.zeros_like(raw, dtype=np.int64)
    nba_c = sports_slice == SPORT_NBA
    ncaab_c = sports_slice == SPORT_NCAAB
    if nba_c.any():
        out[:, nba_c] = scale_edge(raw[:, nba_c], NBA.EDGE_SCALE_NUM, NBA.EDGE_SCALE_DEN)
    if ncaab_c.any():
        out[:, ncaab_c] = scale_edge(raw[:, ncaab_c], NCAAB_EDGE_NUM, NCAAB_EDGE_DEN)
    return out


def simulate(
    nba_taken: list[int],
    ncaab_taken: list[int],
    day_dates: list[date],
    n_sim: int = N_SIM,
    seed: int = SEED,
    start_cents: int = B0,
) -> dict:
    sports, day_n = trade_schedule(nba_taken, ncaab_taken)
    n_trades = int(day_n.sum())
    pnl = draw_pnl(sports, n_sim, seed)
    b = np.full(n_sim, start_cents, dtype=np.int64)
    peak = b.copy()
    min_b = b.copy()
    max_dd_bp = np.zeros(n_sim, dtype=np.int64)
    daily_ret = np.zeros((n_sim, len(day_n)), dtype=np.float64)
    week_keys = []
    seen = set()
    for d in day_dates:
        k = NBA.iso_week_key(d)
        if k not in seen:
            seen.add(k)
            week_keys.append(k)
    weekly_b = np.zeros((n_sim, len(week_keys)), dtype=np.int64)
    week_pos = {k: i for i, k in enumerate(week_keys)}
    cursor = 0
    for t, n in enumerate(day_n.tolist()):
        prev = b.copy()
        if n > 0:
            contracts = (b * FRACTION_PCT // 100) // ENTRY
            raw = contracts[:, None] * pnl[:, cursor : cursor + n]
            adj = apply_sport_edge(raw, sports[cursor : cursor + n])
            b = b + adj.sum(axis=1)
            cursor += n
        daily_ret[:, t] = np.where(prev > 0, b.astype(np.float64) / prev.astype(np.float64) - 1.0, 0.0)
        min_b = np.minimum(min_b, b)
        peak = np.maximum(peak, b)
        dd = np.where(peak > 0, (peak - b) * 10000 // peak, 0)
        max_dd_bp = np.maximum(max_dd_bp, dd)
        weekly_b[:, week_pos[NBA.iso_week_key(day_dates[t])]] = b
    if cursor != n_trades:
        raise IdentityHalt(f"HALT cursor {cursor} != {n_trades}")
    return {
        "end_cents": b,
        "min_cents": min_b,
        "max_dd_bp": max_dd_bp,
        "daily_ret": daily_ret,
        "weekly_cents": weekly_b,
        "week_labels": [f"{y}-W{w:02d}" for y, w in week_keys],
        "n_sim": n_sim,
        "n_trades": n_trades,
        "seed": seed,
        "day_n": day_n.tolist(),
    }


def naive_3pct_end_cents(taken_per_day: list[int], start_cents: int = B0) -> int:
    """Every taken bet earns exactly 3% of that bet's 5% debit. Daily compound."""
    b = int(start_cents)
    for n in taken_per_day:
        if n <= 0:
            continue
        c = NBA.contracts_from_bankroll_cents(b)
        b += n * (c * 12 // 5)
    return b


def analyze(n_sim: int = N_SIM, seed: int = SEED) -> dict:
    ov = load_overlay()
    nba_raw = NBA.expected_debit_return_pct()
    ncaab_raw = ncaab_raw_debit_return_pct()
    if abs(nba_raw - 3.4189) > 0.002:
        raise IdentityHalt(f"HALT nba raw {nba_raw}")
    if abs(ncaab_raw - 4.1717) > 0.01:
        raise IdentityHalt(f"HALT ncaab raw {ncaab_raw}")
    scaled_ncaab = scale_edge(np.array([NCAAB_RAW_BOOK_SUM], dtype=np.int64), NCAAB_EDGE_NUM, NCAAB_EDGE_DEN)
    if int(scaled_ncaab[0]) != 797:
        raise IdentityHalt(f"HALT ncaab haircut {int(scaled_ncaab[0])}")
    sim = simulate(ov["nba_taken"], ov["ncaab_taken"], ov["days"], n_sim=n_sim, seed=seed)
    nba_only = simulate(ov["nba_taken"], [0] * len(ov["days"]), ov["days"], n_sim=n_sim, seed=seed + 1)
    ncaab_only = simulate([0] * len(ov["days"]), ov["ncaab_taken"], ov["days"], n_sim=n_sim, seed=seed + 2)
    naive = naive_3pct_end_cents(ov["taken"])
    end = sim["end_cents"]
    taken = ov["taken"]
    return {
        "written_utc": utc_now(),
        "research_only": True,
        "live_execution_changed": False,
        "financial_behavior_change": (
            "Combining sports with a 6/day cap *per sport* raises the "
            "maximum same-day notional from 30% SOD (NBA-only) to 60% SOD "
            "(6 NBA + 6 NCAAB). Per-bet size is unchanged at 5% SOD. "
            "Risk Decision Engine is not in this research sim."
        ),
        "assumption": (
            "2026-27 Nov 1–Apr 11 uses the overlaid 2025-26 analog: NBA "
            "Q2∪Q3 Nov 1–Apr 12 plus NCAAB P5 H1_2∪H2_1 Nov 7–Apr 4. "
            "Each bet debits 5% of SOD bankroll. Cap is 6 per sport per "
            "day, not 6 combined. Exit signal is still first close-path 40. "
            "50/30/20 loser slip on that 40. Each sport’s class mix is its "
            "own frozen book. Haircut locks 3.000% of debit per bet. "
            "Sports drawn independently. Zero fee. Not a fill. Not live."
        ),
        "projection": {
            "season": "2026-27",
            "sim_window": f"{PROJECT_START.isoformat()} to {PROJECT_END.isoformat()}",
            "analog_window": f"{WINDOW_START.isoformat()} to {WINDOW_END.isoformat()}",
            "nba_prints": EXPECTED_NBA_PRINTS,
            "ncaab_prints": EXPECTED_NCAAB_PRINTS,
            "prints": EXPECTED_NBA_PRINTS + EXPECTED_NCAAB_PRINTS,
            "nba_taken": EXPECTED_NBA_TAKEN,
            "ncaab_taken": EXPECTED_NCAAB_TAKEN,
            "taken": EXPECTED_TAKEN,
            "nba_dropped": EXPECTED_NBA_DROPPED,
            "ncaab_dropped": EXPECTED_NCAAB_DROPPED,
            "n_calendar_days": EXPECTED_CALENDAR_DAYS,
            "n_active_days": EXPECTED_ACTIVE_DAYS,
            "n_iso_weeks": EXPECTED_WEEKS,
            "both_sport_days": EXPECTED_BOTH_DAYS,
            "nba_only_days": EXPECTED_NBA_ONLY_DAYS,
            "ncaab_only_days": EXPECTED_NCAAB_ONLY_DAYS,
            "max_same_day_prints": ov["max_combined_prints"],
            "max_same_day_taken": EXPECTED_MAX_TAKEN,
            "days_at_12_taken": EXPECTED_DAYS_AT_12,
            "days_taken_ge_10": ov["days_taken_ge_10"],
            "nba_days_over_own_cap": ov["nba_days_over_cap"],
            "ncaab_days_over_own_cap": ov["ncaab_days_over_cap"],
            "trades_per_week_taken_mean": round(EXPECTED_TAKEN / EXPECTED_WEEKS, 4),
            "week_taken": ov["week_taken"],
            "week_nba": ov["week_nba"],
            "week_ncaab": ov["week_ncaab"],
            "week_labels": ov["week_labels"],
            "ncaab_76_team_tournament": "NOT_INVENTED",
        },
        "sizing": {
            "start_bankroll_dollars": 20000.0,
            "fraction_of_bankroll_per_bet": 0.05,
            "max_bets_per_sport_per_day": MAX_PER_SPORT,
            "max_bets_per_day_if_both": 12,
            "max_day_fraction_of_bankroll": 0.60,
            "nba_only_max_day_fraction": 0.30,
            "entry_cents": ENTRY,
            "start_contracts_per_bet": NBA.contracts_from_bankroll_cents(B0),
            "compound": "daily_start_of_day",
            "overflow_rule": "first_6_per_sport_by_first_80_timestamp",
            "integer_contracts": True,
            "integer_cents": True,
            "fee": 0,
        },
        "edge": {
            "exit_signal": "FIRST_CLOSE_PATH_40",
            "nba_raw_50_30_20_pct_of_debit": round(nba_raw, 4),
            "ncaab_raw_50_30_20_pct_of_debit": round(ncaab_raw, 4),
            "conservative_locked_pct_of_debit": 3.0,
            "nba_haircut": f"{NBA.EDGE_SCALE_NUM}/{NBA.EDGE_SCALE_DEN}",
            "ncaab_haircut": f"{NCAAB_EDGE_NUM}/{NCAAB_EDGE_DEN}",
            "nba_class_source": "frozen 2Q+3Q n=604",
            "ncaab_class_source": "frozen P5 H1_2∪H2_1 n=332",
            "sports_independent": True,
        },
        "simulation": {
            "n_sim": n_sim,
            "seed": seed,
            "engine": "dual_sport_iid_5class_t40_503020_3pct_edge_5pct_bet_cap6_each",
        },
        "naive_3pct_end_dollars": NBA.dollars(naive),
        "naive_3pct_multiple": round(naive / B0, 4),
        "combined": {
            "terminal": NBA.terminal_distribution(end, B0),
            "risk_of_ruin": {
                **NBA.risk_of_ruin(end, sim["min_cents"], sim["max_dd_bp"], B0),
                "definition": (
                    "Each bet is 5% of SOD. Cap is 6 per sport (12 / 60% "
                    "SOD when both print). Worst taken-out is −87.5% of a "
                    "bet before haircut = 4.375% SOD per bet, 52.5% SOD if "
                    "all 12 max-slip. B=0 is still not a one-day event. "
                    "Ruin is start-relative and peak-to-trough."
                ),
            },
            "sharpe": NBA.sharpe_rows(sim["daily_ret"], taken),
            "weekly_fan": NBA.weekly_fan(sim["weekly_cents"], sim["week_labels"], B0),
            "histogram_end_dollars": NBA.histogram_dollars(end, 10000, 160000, 10000),
        },
        "nba_only": {
            "taken": EXPECTED_NBA_TAKEN,
            "terminal": NBA.terminal_distribution(nba_only["end_cents"], B0),
            "risk_of_ruin": NBA.risk_of_ruin(
                nba_only["end_cents"], nba_only["min_cents"], nba_only["max_dd_bp"], B0
            ),
        },
        "ncaab_only": {
            "taken": EXPECTED_NCAAB_TAKEN,
            "terminal": NBA.terminal_distribution(ncaab_only["end_cents"], B0),
            "risk_of_ruin": NBA.risk_of_ruin(
                ncaab_only["end_cents"], ncaab_only["min_cents"], ncaab_only["max_dd_bp"], B0
            ),
        },
        "taken_per_day_hist": {str(k): int(sum(1 for n in taken if n == k)) for k in range(13)},
    }


def write_outputs(summary: dict) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "summary.json"
    path.write_text(json.dumps(summary, indent=2) + "\n")
    t = summary["combined"]["terminal"]["percentiles_dollars"]
    print("wrote", path)
    print(
        "taken",
        summary["projection"]["taken"],
        "naive3",
        summary["naive_3pct_end_dollars"],
        "median",
        t["p50"],
        "p05",
        t["p05"],
        "P(end<start)",
        summary["combined"]["risk_of_ruin"]["p_end_below_start"],
        "nba_only_p50",
        summary["nba_only"]["terminal"]["percentiles_dollars"]["p50"],
        "ncaab_only_p50",
        summary["ncaab_only"]["terminal"]["percentiles_dollars"]["p50"],
    )
    return path


def main() -> None:
    write_outputs(analyze())


if __name__ == "__main__":
    main()
