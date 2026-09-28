"""Optional derived response corpus. Not a public PIT dataset."""

from __future__ import annotations

from typing import Any

import pandas as pd

from roller.admin import load_dataset, load_identity
from roller.config import RollerConfig
from roller.io_csv import read_csv_optional, write_csv
from roller.measurement.conditioning import condition_observation
from roller.measurement.response import build_response
from roller.paths import derived_dir
from roller.state.observation import assemble_observation
from roller.state.observation_id import make_observation_id
from roller.timeutil import parse_utc, series_to_utc

CORPUS_COLUMNS = [
    "observation_id",
    "internal_game_id",
    "sport",
    "season",
    "observation_time",
    "measurement_name",
    "horizon",
    "value",
    "status",
    "response_available_at",
    "condition_id",
    "contains_future_information",
]


def corpus_path(cfg: RollerConfig, sport: str, season: str):
    path_key = cfg.season_meta(sport, season)["path_key"]
    return derived_dir(cfg.root, sport, path_key) / "v3_response_corpus.csv"


def load_response_corpus(cfg: RollerConfig, sport: str, season: str) -> list[dict[str, Any]]:
    path = corpus_path(cfg, sport, season)
    df = read_csv_optional(path, columns=CORPUS_COLUMNS)
    if df.empty:
        return []
    return df.to_dict("records")


def _sample_times(candles: pd.DataFrame) -> list[str]:
    if candles is None or candles.empty:
        return []
    ts = series_to_utc(candles["available_at"]).dropna().sort_values()
    if ts.empty:
        return []
    vals = [t.strftime("%Y-%m-%dT%H:%M:%S") + "Z" for t in ts.tolist()]
    if len(vals) == 1:
        return vals
    mid = vals[len(vals) // 2]
    return list(dict.fromkeys([vals[0], mid, vals[-1]]))


def write_response_corpus(cfg: RollerConfig, sport: str, season: str) -> pd.DataFrame:
    """First/mid/last candle-close observation per game. Documented sample, not a full grid."""
    try:
        candles_all = load_dataset(cfg, sport, season, "kalshi_candles")
    except FileNotFoundError:
        candles_all = pd.DataFrame()
    ident = load_identity(cfg)
    games = ident[(ident["sport"] == sport) & (ident["season"] == season)]
    rows: list[dict[str, Any]] = []
    for rec in games.to_dict("records") if not games.empty else []:
        gid = rec["internal_game_id"]
        g_candles = (
            candles_all[candles_all["internal_game_id"] == gid] if not candles_all.empty else pd.DataFrame()
        )
        try:
            pbp = load_dataset(cfg, sport, season, "pbp")
            pbp = pbp[pbp["internal_game_id"] == gid] if not pbp.empty else pbp
        except FileNotFoundError:
            pbp = pd.DataFrame()
        for t in _sample_times(g_candles):
            oid = make_observation_id(gid, t, cfg.state_schema_version)
            try:
                obs = assemble_observation(cfg, gid, as_of=t)
            except (KeyError, FileNotFoundError):
                continue
            cond = condition_observation(cfg, obs)["condition_id"]
            for horizon in ("1m", "5m", "10m"):
                y = build_response(
                    cfg,
                    observation_id=oid,
                    measurement=f"market_response_{horizon}",
                    horizon=horizon,
                    candles=g_candles,
                    pbp=pbp,
                )
                rows.append(
                    {
                        "observation_id": oid,
                        "internal_game_id": gid,
                        "sport": sport,
                        "season": season,
                        "observation_time": y.get("observation_time"),
                        "measurement_name": y.get("measurement_name"),
                        "horizon": horizon,
                        "value": y.get("value") if y.get("value") is not None else "",
                        "status": y.get("status"),
                        "response_available_at": y.get("response_available_at"),
                        "condition_id": cond,
                        "contains_future_information": True,
                    }
                )
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=CORPUS_COLUMNS)
    else:
        df = df[CORPUS_COLUMNS]
    write_csv(corpus_path(cfg, sport, season), df, CORPUS_COLUMNS)
    return df
