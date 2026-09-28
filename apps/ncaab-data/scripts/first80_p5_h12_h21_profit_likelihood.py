#!/usr/bin/env python3
"""Realistic P(season EV>0) for P5 H1_2 ∪ H2_1 FIRST80 — research only.

Same object as the NBA 2Q+3Q profit-likelihood table:

- Exit signal is still first later close-path 40.
- Loser fills 50/30/20 on that 40 (−40 / −60 / −70). Winner-touches −40.
- Survivors +20. L∩¬T40 = 0 in the frozen book.
- Naive: known p, iid trades, n after the 6/day cap.
- Realistic: unknown persist p from the book Beta, week-residual remix
  of the observed season, random 50/30/20 fills.
- Worlds: last-year persist, World A (K=80 means P(W)=0.75, path|W held),
  December as a hypothesized mean. January is added because it is the
  NCAAB weak month — December is not.

Does not change live FIRST01. Zero fee. Does not invent L2.
Candle path ≠ fill. P5 vs P5 only.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parent
NBA_SCRIPTS = Path("/Users/user/Desktop/Momento/apps/nba-data/scripts")
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(NBA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(NBA_SCRIPTS))

import first80_p5_half_barrier_survival as P5  # noqa: E402
import first80_q23_profit_likelihood as NBA  # noqa: E402
import ncaab_pbp_align as ALIGN  # noqa: E402

OUT = P5.OUT.parent / "first80_p5_h12_h21_profit_likelihood"
TRADES_PATH = OUT / "trades.parquet"

BUCKETS = ("H1_2", "H2_1")
H12_N = 193
H12_W = 163
H12_T40 = 51
H12_SURVIVE = 142
H12_WTOUCH = 21
H12_LOSE = 30
H21_N = 139
H21_W = 118
H21_T40 = 31
H21_SURVIVE = 108
H21_WTOUCH = 10
H21_LOSE = 21

BOOK_N = H12_N + H21_N  # 332
BOOK_W = H12_W + H21_W  # 281
BOOK_SURVIVE = H12_SURVIVE + H21_SURVIVE  # 250
BOOK_WTOUCH = H12_WTOUCH + H21_WTOUCH  # 31
BOOK_LOSE = H12_LOSE + H21_LOSE  # 51
BOOK_T40 = BOOK_WTOUCH + BOOK_LOSE  # 82

DEC_N = 31
DEC_SURVIVE = 24
DEC_WTOUCH = 3
DEC_LOSE = 4

JAN_N = 101
JAN_SURVIVE = 72
JAN_WTOUCH = 12
JAN_LOSE = 17

WINDOW_WEEKS = 21
WORST_WEEK = (2026, 1)
WORST_WEEK_N = 12
WORST_WEEK_SURVIVE = 7
DATE_MIN = date(2025, 11, 7)
DATE_MAX = date(2026, 4, 4)
MAX_TRADES_PER_DAY = 6
NAIVE_N = 269  # 332 − 63 overflow after first-6 by first_80_timestamp
EXPECTED_DROPPED = 63
EXPECTED_DAYS_OVER_CAP = 21

N_SIM = 20_000
SEED = 20260905

P_BAR_BOOK = BOOK_SURVIVE / BOOK_N
Q_WT_BOOK = BOOK_WTOUCH / BOOK_T40
P_BAR_WORLD_A = 0.75 * BOOK_SURVIVE / BOOK_W
Q_WT_WORLD_A = (0.75 * BOOK_WTOUCH / BOOK_W) / (1.0 - P_BAR_WORLD_A)
P_BAR_DEC = DEC_SURVIVE / DEC_N
Q_WT_DEC = DEC_WTOUCH / (DEC_WTOUCH + DEC_LOSE)
P_BAR_JAN = JAN_SURVIVE / JAN_N
Q_WT_JAN = JAN_WTOUCH / (JAN_WTOUCH + JAN_LOSE)

# Locked NBA 2Q+3Q realistic table (same seed / DGP / slip). Do not silently
# re-average; these are the published NBA canvas numbers.
NBA_REALISTIC_SLIP = {
    "persist": 0.89665,
    "world_a": 0.05765,
    "december": 0.0535,
}
NBA_REALISTIC_CLEAN = {
    "persist": 0.9921,
    "world_a": 0.51885,
    "december": 0.38385,
}


class IdentityHalt(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def game_date_of(row: dict) -> date:
    raw = row.get("game_date")
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    return date.fromisoformat(str(raw)[:10])


def iso_week_key(d: date) -> tuple[int, int]:
    iso = d.isocalendar()
    return (iso.year, iso.week)


def _build_book_rows() -> list[dict]:
    trades = P5.load_frozen_p5_first80()
    P5.halt_unless_identity(trades)
    xwalk = ALIGN.load_crosswalk()
    cache: dict = {}
    out = []
    for rec in trades:
        align = P5.align_entry(rec, xwalk, cache)
        bucket = align["entry_half_bucket"]
        if bucket not in BUCKETS:
            continue
        out.append(
            {
                "event_id": rec.get("event_id"),
                "ticker": rec.get("ticker"),
                "game_date": str(rec.get("game_date"))[:10],
                "first_80_timestamp": int(rec["first_80_timestamp"]),
                "entry_half_bucket": bucket,
                "W": bool(rec["expiration_result_yes"]),
                "T40": bool(rec.get("stop_close_triggered")),
            }
        )
    return sorted(out, key=lambda r: (r["game_date"], r["first_80_timestamp"]))


def load_book_rows() -> list[dict]:
    import pyarrow as pa
    import pyarrow.parquet as pq

    if TRADES_PATH.exists():
        rows = pq.read_table(TRADES_PATH).to_pylist()
    else:
        rows = _build_book_rows()
        OUT.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pylist(rows), TRADES_PATH)
    halt_book(rows)
    return rows


def four_cell(rows: list[dict]) -> dict:
    n = len(rows)
    w = sum(1 for r in rows if r["W"])
    t40 = sum(1 for r in rows if r["T40"])
    survive = sum(1 for r in rows if r["W"] and not r["T40"])
    wtouch = sum(1 for r in rows if r["W"] and r["T40"])
    lose = n - w
    l_not = sum(1 for r in rows if (not r["W"]) and not r["T40"])
    return {
        "n": n,
        "w": w,
        "t40": t40,
        "survive": survive,
        "wtouch": wtouch,
        "lose": lose,
        "l_not": l_not,
    }


def halt_book(rows: list[dict]) -> dict:
    c = four_cell(rows)
    if (
        c["n"] != BOOK_N
        or c["w"] != BOOK_W
        or c["survive"] != BOOK_SURVIVE
        or c["wtouch"] != BOOK_WTOUCH
        or c["lose"] != BOOK_LOSE
        or c["l_not"] != 0
    ):
        raise IdentityHalt(f"HALT H1_2∪H2_1 book {c}")
    h12 = four_cell([r for r in rows if r["entry_half_bucket"] == "H1_2"])
    h21 = four_cell([r for r in rows if r["entry_half_bucket"] == "H2_1"])
    if h12["n"] != H12_N or h12["survive"] != H12_SURVIVE or h12["lose"] != H12_LOSE:
        raise IdentityHalt(f"HALT H1_2 {h12}")
    if h21["n"] != H21_N or h21["survive"] != H21_SURVIVE or h21["lose"] != H21_LOSE:
        raise IdentityHalt(f"HALT H2_1 {h21}")
    return {"combined": c, "H1_2": h12, "H2_1": h21}


def cap_stats(rows: list[dict]) -> dict:
    by_day: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_day[r["game_date"]].append(r)
    taken = 0
    dropped = 0
    over = 0
    max_day = 0
    for rs in by_day.values():
        rs = sorted(rs, key=lambda r: int(r["first_80_timestamp"]))
        n = len(rs)
        max_day = max(max_day, n)
        taken += min(MAX_TRADES_PER_DAY, n)
        extra = max(0, n - MAX_TRADES_PER_DAY)
        dropped += extra
        if extra:
            over += 1
    if taken != NAIVE_N or dropped != EXPECTED_DROPPED or over != EXPECTED_DAYS_OVER_CAP:
        raise IdentityHalt(f"HALT 6-cap taken={taken} dropped={dropped} over={over}")
    return {
        "n_prints": len(rows),
        "n_taken": taken,
        "n_dropped": dropped,
        "days_over_cap": over,
        "max_same_day": max_day,
        "n_active_days": len(by_day),
        "rule": "first_6_by_first_80_timestamp",
    }


def week_blocks(rows: list[dict] | None = None) -> dict:
    rows = rows if rows is not None else load_book_rows()
    dates = [game_date_of(r) for r in rows]
    if min(dates) != DATE_MIN or max(dates) != DATE_MAX:
        raise IdentityHalt(f"HALT date range {min(dates)} {max(dates)}")
    by_week: dict[tuple[int, int], list[dict]] = {}
    for r in rows:
        by_week.setdefault(iso_week_key(game_date_of(r)), []).append(r)
    if len(by_week) != WINDOW_WEEKS:
        raise IdentityHalt(f"HALT weeks={len(by_week)}")
    keys = sorted(by_week)
    n = np.array([len(by_week[k]) for k in keys], dtype=np.int64)
    survive = np.array(
        [sum(1 for r in by_week[k] if r["W"] and not r["T40"]) for k in keys],
        dtype=np.int64,
    )
    wtouch = np.array(
        [sum(1 for r in by_week[k] if r["W"] and r["T40"]) for k in keys],
        dtype=np.int64,
    )
    lose = n - survive - wtouch
    if int(survive.sum()) != BOOK_SURVIVE:
        raise IdentityHalt(f"HALT week survive {int(survive.sum())}")
    i_w = keys.index(WORST_WEEK)
    if int(n[i_w]) != WORST_WEEK_N or int(survive[i_w]) != WORST_WEEK_SURVIVE:
        raise IdentityHalt("HALT worst week 2026-W1")
    dec = [r for r in rows if r["game_date"].startswith("2025-12")]
    jan = [r for r in rows if r["game_date"].startswith("2026-01")]
    dc = four_cell(dec)
    jc = four_cell(jan)
    if dc["n"] != DEC_N or dc["survive"] != DEC_SURVIVE:
        raise IdentityHalt(f"HALT December {dc}")
    if jc["n"] != JAN_N or jc["survive"] != JAN_SURVIVE:
        raise IdentityHalt(f"HALT January {jc}")
    p_week = survive / n.astype(np.float64)
    return {
        "keys": keys,
        "n": n,
        "survive": survive,
        "wtouch": wtouch,
        "lose": lose,
        "p_week": p_week,
        "p_season": float(survive.sum() / n.sum()),
        "worst_week_p": float(survive[i_w] / n[i_w]),
        "december": dc,
        "january": jc,
    }


def _row(world: str, p_bar: float, naive: dict, real: dict, what: str) -> dict:
    return {
        "world": world,
        "mean_p_bar": p_bar,
        "naive_p_clean": naive["p_clean_gt0"],
        "naive_p_slip": naive["p_slip_gt0"],
        "realistic_p_clean": real["p_clean_gt0"],
        "realistic_p_slip": real["p_slip_gt0"],
        "realistic_ev_slip_p50": real["ev_slip_p50"],
        "realistic_ev_slip_p05": real["ev_slip_p05"],
        "realistic_what_is_random": what,
    }


def analyze(n_sim: int = N_SIM, seed: int = SEED) -> dict:
    rows = load_book_rows()
    caps = cap_stats(rows)
    weeks = week_blocks(rows)
    persist_naive = NBA.sim_naive_iid(P_BAR_BOOK, Q_WT_BOOK, n_trades=NAIVE_N, n_sim=n_sim, seed=seed)
    world_a_naive = NBA.sim_naive_iid(
        P_BAR_WORLD_A, Q_WT_WORLD_A, n_trades=NAIVE_N, n_sim=n_sim, seed=seed + 1
    )
    dec_naive = NBA.sim_naive_iid(P_BAR_DEC, Q_WT_DEC, n_trades=NAIVE_N, n_sim=n_sim, seed=seed + 2)
    jan_naive = NBA.sim_naive_iid(P_BAR_JAN, Q_WT_JAN, n_trades=NAIVE_N, n_sim=n_sim, seed=seed + 3)
    alphas = {
        "p_alpha": (BOOK_SURVIVE, BOOK_T40),
        "q_alpha": (BOOK_WTOUCH, BOOK_LOSE),
    }
    persist_real = NBA.sim_realistic(
        p_mean=None,
        q_mean=Q_WT_BOOK,
        unknown_p=True,
        unknown_q=True,
        weeks=weeks,
        n_sim=n_sim,
        seed=seed + 10,
        **alphas,
    )
    world_a_real = NBA.sim_realistic(
        p_mean=P_BAR_WORLD_A,
        q_mean=Q_WT_WORLD_A,
        unknown_p=False,
        unknown_q=False,
        weeks=weeks,
        n_sim=n_sim,
        seed=seed + 11,
    )
    dec_real = NBA.sim_realistic(
        p_mean=P_BAR_DEC,
        q_mean=Q_WT_DEC,
        unknown_p=False,
        unknown_q=False,
        weeks=weeks,
        n_sim=n_sim,
        seed=seed + 12,
    )
    jan_real = NBA.sim_realistic(
        p_mean=P_BAR_JAN,
        q_mean=Q_WT_JAN,
        unknown_p=False,
        unknown_q=False,
        weeks=weeks,
        n_sim=n_sim,
        seed=seed + 13,
    )
    clean_ev = (
        BOOK_SURVIVE * NBA.PNL_SURVIVE + BOOK_T40 * NBA.PNL_T40_CLEAN
    ) / BOOK_N
    slip_ev = (
        BOOK_SURVIVE * NBA.PNL_SURVIVE
        + BOOK_WTOUCH * NBA.PNL_T40_CLEAN
        + BOOK_LOSE * (-52)
    ) / BOOK_N
    return {
        "generated_at": utc_now(),
        "research_only": True,
        "live_first01_unchanged": True,
        "fee_cents": 0,
        "l2": "UNAVAILABLE",
        "sport": "NCAAB",
        "universe": "P5 vs P5 KXNCAAMBGAME 2025-26 FIRST80, H1_2 ∪ H2_1",
        "alignment_model": "HALF_BOUNDED_OBSERVED_WALLCLOCK",
        "n_sim": n_sim,
        "seed": seed,
        "identities": {
            "H1_2": {
                "n": H12_N,
                "w": H12_W,
                "survive": H12_SURVIVE,
                "wtouch": H12_WTOUCH,
                "lose": H12_LOSE,
            },
            "H2_1": {
                "n": H21_N,
                "w": H21_W,
                "survive": H21_SURVIVE,
                "wtouch": H21_WTOUCH,
                "lose": H21_LOSE,
            },
            "book": {
                "n": BOOK_N,
                "w": BOOK_W,
                "survive": BOOK_SURVIVE,
                "wtouch": BOOK_WTOUCH,
                "lose": BOOK_LOSE,
                "p_bar": P_BAR_BOOK,
                "p_term": BOOK_W / BOOK_N,
                "p_bar_given_w": BOOK_SURVIVE / BOOK_W,
                "q_wt": Q_WT_BOOK,
                "clean_ev_cents": clean_ev,
                "slip_ev_cents": slip_ev,
            },
            "december": {
                "n": DEC_N,
                "survive": DEC_SURVIVE,
                "wtouch": DEC_WTOUCH,
                "lose": DEC_LOSE,
                "p_bar": P_BAR_DEC,
            },
            "january": {
                "n": JAN_N,
                "survive": JAN_SURVIVE,
                "wtouch": JAN_WTOUCH,
                "lose": JAN_LOSE,
                "p_bar": P_BAR_JAN,
            },
            "world_a": {
                "p_term": 0.75,
                "p_bar": P_BAR_WORLD_A,
                "q_wt": Q_WT_WORLD_A,
                "path_conditionals": "P(¬T40|W)=250/281, P(T40|L)=1",
            },
            "calendar": {
                "date_min": DATE_MIN.isoformat(),
                "date_max": DATE_MAX.isoformat(),
                "weeks": WINDOW_WEEKS,
                "worst_week": f"{WORST_WEEK[0]}-W{WORST_WEEK[1]:02d}",
                "worst_week_p": weeks["worst_week_p"],
                "project_2026_27": "2026-11-01 to 2027-04-05",
                "project_note": (
                    "Official 2026-27 D1 men's season Nov 1–championship Apr 5. "
                    "76-team NCAA tournament is a structural change; this sim "
                    "does not invent extra FIRST80 prints from expansion."
                ),
            },
            "six_cap": caps,
        },
        "hurdles": {
            "clean_be_p_bar": NBA.CLEAN_BE,
            "slip_be_p_bar_book_q": NBA.slip_breakeven_p(Q_WT_BOOK),
            "slip_be_p_bar_world_a_q": NBA.slip_breakeven_p(Q_WT_WORLD_A),
            "slip_be_p_bar_dec_q": NBA.slip_breakeven_p(Q_WT_DEC),
            "slip_be_p_bar_jan_q": NBA.slip_breakeven_p(Q_WT_JAN),
        },
        "naive_iid": {
            "n": NAIVE_N,
            "persist": persist_naive,
            "world_a": world_a_naive,
            "december": dec_naive,
            "january": jan_naive,
        },
        "realistic": {
            "persist_unknown_p": persist_real,
            "world_a_known_mean": world_a_real,
            "december_known_mean": dec_real,
            "january_known_mean": jan_real,
        },
        "table": [
            _row(
                "75.30% last-year H1_2∪H2_1",
                P_BAR_BOOK,
                persist_naive,
                persist_real,
                "p* ~ Beta(250,82), q* ~ Beta(31,51), 21-week residual remix, random 50/30/20 fills",
            ),
            _row(
                "66.73% World A",
                P_BAR_WORLD_A,
                world_a_naive,
                world_a_real,
                "mean locked at World A; week residuals + random fills",
            ),
            _row(
                "77.42% December",
                P_BAR_DEC,
                dec_naive,
                dec_real,
                "mean locked at December 24/31; week residuals + random fills. Not a crash month.",
            ),
            _row(
                "71.29% January (weak month)",
                P_BAR_JAN,
                jan_naive,
                jan_real,
                "mean locked at January 72/101 — the actual NCAAB weak month, not December",
            ),
        ],
        "vs_nba_q23": {
            "nba_book_n": 604,
            "nba_p_bar": 450 / 604,
            "nba_naive_n": 499,
            "nba_weeks": 24,
            "nba_dec_p_bar": 56 / 85,
            "nba_realistic_p_slip": NBA_REALISTIC_SLIP,
            "nba_realistic_p_clean": NBA_REALISTIC_CLEAN,
            "difference": [
                "NCAAB book is 332 vs NBA 604; 6-cap drops 63 vs 9 (conference Saturdays).",
                "NCAAB December is 77.42% — above the season rate. NBA December was 65.88%.",
                "NCAAB weak month is January 71.29%, still above the ~70.4% slip hurdle.",
                "NCAAB worst week is 7/12=58.3%; NBA week 50 was 5/11=45.5%.",
                "World A is 66.69% here vs 66.83% NBA — both sit on the clean-40 breakeven.",
                "Persist posterior is Beta(250,82) vs Beta(450,154): more unknown-p mass.",
            ],
        },
        "do_not": [
            "Do not average the worlds into one P(profit).",
            "Do not treat NCAAB December as the NBA December crash.",
            "Do not invent 76-team-tournament extra FIRST80 prints.",
            "Do not treat these as after-fee probabilities.",
            "Do not change live FIRST01 from this table.",
        ],
    }


def write_summary(summary: dict) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "summary.json"
    path.write_text(json.dumps(summary, indent=2) + "\n")
    return path


def main() -> None:
    summary = analyze()
    path = write_summary(summary)
    print(json.dumps({"wrote": str(path), "table": summary["table"]}, indent=2))


if __name__ == "__main__":
    main()
