#!/usr/bin/env python3
"""FIRST80_HYBRID_MODFILL_H37_42

Hybrid candle book around H=40:

  if V3 class at H is A_STRONG or B_MODERATE (moderate-confidence persist,
  not jump / weak / wick):
      lock 20 − H
  else:
      80→40 Model A

NCAAB working universe is Power 5 vs Power 5 only (both
Kalshi team codes in the 2025–26 P5 set). Mid-majors and P5–mid
are excluded. Full-warehouse NCAAB (4,099) is not used.

Does not modify V1–V5, FIRST01, Risk, or live execution.
LIVE EXECUTION CHANGED: FALSE.
CANDLE TAXONOMY ≠ ACTUAL MAKER FILL.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path("/Users/user/Desktop/Momento/Backtesting Suite/Data")
GAMES = (
    ROOT
    / "NCAAB/2025-2026/warehouse/normalized/ncaab/games/ncaab_games.parquet"
)
# 2025–26: ACC + B1G + Big 12 + SEC + Pac-12 (ORST, WSU). Both teams required.
P5_CODES = frozenset(
    {
        "ALA",
        "ARIZ",
        "ARK",
        "ASU",
        "AUB",
        "BAY",
        "BC",
        "BYU",
        "CAL",
        "CIN",
        "CLEM",
        "COLO",
        "DUKE",
        "FLA",
        "FSU",
        "GT",
        "HOU",
        "ILL",
        "IND",
        "IOWA",
        "ISU",
        "KSU",
        "KU",
        "LOU",
        "LSU",
        "MD",
        "MIA",
        "MICH",
        "MINN",
        "MISS",
        "MIZZ",
        "MSST",
        "MSU",
        "NCST",
        "ND",
        "NEB",
        "NW",
        "OKLA",
        "OKST",
        "ORE",
        "ORST",
        "OSU",
        "PITT",
        "PSU",
        "PUR",
        "RUTG",
        "SCAR",
        "SMU",
        "STAN",
        "SYR",
        "TCU",
        "TENN",
        "TEX",
        "TTU",
        "TXAM",
        "UCF",
        "UCLA",
        "UGA",
        "UK",
        "UNC",
        "USC",
        "UTAH",
        "UVA",
        "VAN",
        "VT",
        "WAKE",
        "WASH",
        "WIS",
        "WSU",
        "WVU",
    }
)
HS = (37, 38, 39, 40, 41, 42)
MOD = frozenset({"A_STRONG", "B_MODERATE"})
HIGH = frozenset({"A_STRONG"})
NO_E = frozenset({"A_STRONG", "B_MODERATE", "C_WEAK"})


def opp_path(sport: str) -> Path:
    return (
        ROOT
        / sport.upper()
        / "2025-2026/warehouse/derived"
        / sport
        / "first80_opponent_hedge_execution_model_v3/opportunity_dataset.parquet"
    )


def led_path(sport: str) -> Path:
    return (
        ROOT
        / sport.upper()
        / "2025-2026/warehouse/derived"
        / sport
        / "first80_opponent_hedge_optimal_v4/trade_ledger.parquet"
    )


def load_led(sport: str, p5: bool) -> pd.DataFrame:
    led = pq.read_table(led_path(sport)).to_pandas()
    if sport != "ncaab" and not p5:
        return led
    g = pq.read_table(
        GAMES, columns=["event_id", "home_team_code", "away_team_code"]
    ).to_pandas().drop_duplicates("event_id")
    led = led.merge(g, on="event_id", how="left")
    return led[
        led.home_team_code.isin(P5_CODES) & led.away_team_code.isin(P5_CODES)
    ].copy()


def hybrid_at_h(led: pd.DataFrame, opp: pd.DataFrame, h: int, fill_classes: frozenset[str]) -> dict:
    sub = opp[opp.H == h][
        [
            "game_id",
            "opportunity_close",
            "opportunity_quality_class",
            "touch_candle_close_cents",
            "jump_10c",
        ]
    ].copy()
    df = led.merge(sub, left_on="event_id", right_on="game_id", how="left")
    cls = df.opportunity_quality_class.fillna("NONE")
    fill = df.opportunity_close.fillna(False).astype(bool) & cls.isin(fill_classes)
    stop = df.pnl_stop_80_40.to_numpy(dtype=float)
    lock = 20.0 - h
    pnl = np.where(fill.to_numpy(), lock, stop)
    won = df.won.to_numpy()
    n = len(df)
    n_fill = int(fill.sum())
    n_fb = n - n_fill
    fb = df.loc[~fill]
    n_fb_stop = int(fb.pnl_stop_80_40.eq(-40).sum()) if n_fb else 0
    n_fb_win = int(fb.pnl_stop_80_40.eq(20).sum()) if n_fb else 0
    n_fb_leak = n_fb - n_fb_stop - n_fb_win
    worse = int((pnl < stop).sum())
    better = int((pnl > stop).sum())
    fill_won = int((fill & df.won).sum())
    fill_lost = n_fill - fill_won
    return {
        "h": h,
        "lock": int(lock),
        "n": n,
        "n_hedge": n_fill,
        "n_fallback": n_fb,
        "pct_hedge": round(100.0 * n_fill / n, 2) if n else None,
        "hedge_wins": fill_won,
        "hedge_losses": fill_lost,
        "fallback_stop": n_fb_stop,
        "fallback_hold_win": n_fb_win,
        "fallback_leak": n_fb_leak,
        "ev": round(float(np.mean(pnl)), 4),
        "ev_stop": round(float(np.mean(stop)), 4),
        "ev_v1": round(float(df.pnl_replace_h40.mean()), 4),
        "ev_hold": round(float(df.pnl_hold.mean()), 4),
        "vs_stop": round(float(np.mean(pnl) - np.mean(stop)), 4),
        "n_better_than_8040": better,
        "n_worse_than_8040": worse,
        "n_equal": n - better - worse,
        "total_cents": int(np.round(np.sum(pnl))),
    }


def run_universe(sport: str, p5: bool, label: str) -> dict:
    led = load_led(sport, p5)
    opp = pq.read_table(opp_path(sport)).to_pandas()
    books = {
        "MOD_A_PLUS_B": MOD,
        "HIGH_A_ONLY": HIGH,
        "NO_JUMP_ABC": NO_E,
    }
    out: dict = {"label": label, "n": int(len(led)), "books": {}}
    for bname, classes in books.items():
        rows = [hybrid_at_h(led, opp, h, classes) for h in HS]
        out["books"][bname] = rows
    return out


def main() -> None:
    payload = {
        "program": "FIRST80_HYBRID_MODFILL_H37_42",
        "live_execution_changed": False,
        "fill_rule": (
            "MOD = V3 A_STRONG|B_MODERATE at H → lock 20-H; else 80→40 Model A. "
            "HIGH = A_STRONG only. NO_JUMP = A|B|C (exclude E_JUMP)."
        ),
        "label": "CANDLE TAXONOMY — NOT ACTUAL MAKER FILL",
        "ncaab_universe": "P5_VS_P5_ONLY",
        "universes": {
            "nba": run_universe("nba", False, "NBA"),
            "ncaab": run_universe("ncaab", True, "NCAAB P5 vs P5"),
        },
    }
    dest = Path("/tmp/first80_hybrid_modfill_h37_42.json")
    dest.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
