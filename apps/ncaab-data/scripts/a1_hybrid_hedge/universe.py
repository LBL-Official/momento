"""Frozen FIRST-80 loaders. NCAAB is P5 vs P5 only."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path("/Users/user/Desktop/Momento/Backtesting Suite/Data")
GAMES_NCAAB = (
    ROOT / "NCAAB/2025-2026/warehouse/normalized/ncaab/games/ncaab_games.parquet"
)

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

SPLIT_TRAIN_END = "2025-12-31"
SPLIT_VAL_END = "2026-03-15"

BASELINE = {
    "nba": {"n": 1230, "hold": 2.8455, "stop": 4.3902, "v1": 5.1707},
    "ncaab": {"n": 721, "hold": 3.3564, "stop": 4.3551, "v1": 4.3551},
}


def split_of(game_date: str | None) -> str:
    if not game_date:
        return "UNSPLIT"
    if game_date <= SPLIT_TRAIN_END:
        return "TRAIN"
    if game_date <= SPLIT_VAL_END:
        return "VALIDATION"
    return "OOS"


def _paths(sport: str) -> tuple[Path, Path]:
    d = ROOT / sport.upper() / f"2025-2026/warehouse/derived/{sport}"
    return (
        d / "first80_opponent_hedge_execution_model_v3/opportunity_dataset.parquet",
        d / "first80_opponent_hedge_optimal_v4/trade_ledger.parquet",
    )


def load_ledger(sport: str) -> pd.DataFrame:
    _, led_p = _paths(sport)
    led = pq.read_table(led_p).to_pandas()
    if sport == "ncaab":
        g = pq.read_table(
            GAMES_NCAAB, columns=["event_id", "home_team_code", "away_team_code"]
        ).to_pandas().drop_duplicates("event_id")
        led = led.merge(g, on="event_id", how="left")
        led = led[
            led.home_team_code.isin(P5_CODES) & led.away_team_code.isin(P5_CODES)
        ].copy()
    if "dataset_split" not in led.columns or led["dataset_split"].isna().any():
        led["dataset_split"] = led["game_date"].map(split_of)
    led["sport"] = sport
    return led.reset_index(drop=True)


def load_opportunity(sport: str) -> pd.DataFrame:
    opp_p, _ = _paths(sport)
    return pq.read_table(opp_p).to_pandas()


def config_hash(obj: dict) -> str:
    raw = json.dumps(obj, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def reproduce_baseline(led: pd.DataFrame, sport: str) -> dict:
    exp = BASELINE[sport]
    hold = float(led.pnl_hold.mean())
    stop = float(led.pnl_stop_80_40.mean())
    v1 = float(led.pnl_replace_h40.mean())
    n = int(len(led))
    ok = (
        n == exp["n"]
        and round(hold, 4) == exp["hold"]
        and round(stop, 4) == exp["stop"]
        and round(v1, 4) == exp["v1"]
    )
    return {
        "sport": sport,
        "ok": ok,
        "n": n,
        "hold": round(hold, 4),
        "stop": round(stop, 4),
        "v1": round(v1, 4),
        "expected": exp,
        "label": "REPRODUCED FROZEN FIRST80 / V4 LEDGER",
    }
