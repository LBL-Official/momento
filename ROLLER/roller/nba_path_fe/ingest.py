"""Dump warehouse TRADABLE_YES_BID paths into data/raw/.

Candle path ≠ fill. L2 is SOURCE_UNAVAILABLE. PBP score/clock is
sequence-joined, not candle-PIT. Does not edit first80.py.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from roller.config import RollerConfig
from roller.nba_path_fe.clockparse import clock_to_seconds, e4_to_cents
from roller.nba_path_fe.errors import PathFeError
from roller.nba_path_fe.paths import raw_data_dir
from roller.warehouse.layout import (
    games_path,
    markets_path,
    observations_dir,
    pbp_dir,
    settlements_path,
    warehouse_root,
)
from roller.warehouse.partitioning import list_month_parquets


WAREHOUSE_SOURCE = "WAREHOUSE_2025_2026"
REGULAR_MONTHS = (
    "2025-10",
    "2025-11",
    "2025-12",
    "2026-01",
    "2026-02",
    "2026-03",
    "2026-04",
)


def _utc(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def _canonical_games(cfg: RollerConfig) -> pd.DataFrame:
    path = cfg.root / "data" / "nba" / "2025_2026" / "canonical" / "games.csv"
    if not path.is_file():
        raise PathFeError("DATA_REQUIRED", f"missing {path}")
    g = pd.read_csv(path)
    keep = [
        "internal_game_id",
        "game_date",
        "actual_start",
        "home_team_id",
        "away_team_id",
        "home_win",
        "result_available_at",
        "game_window_start",
        "game_window_end",
    ]
    return g[keep].copy()


def _rest_days(games: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for team_col, rest_col in (("home_team_id", "rest_home"), ("away_team_id", "rest_away")):
        tmp = games[["internal_game_id", "game_date", team_col]].copy()
        tmp = tmp.sort_values(["game_date", "internal_game_id"])
        prev = tmp.groupby(team_col)["game_date"].shift(1)
        delta = (
            pd.to_datetime(tmp["game_date"]) - pd.to_datetime(prev)
        ).dt.days
        tmp[rest_col] = delta.fillna(3).astype(int).clip(lower=0, upper=14)
        rows.append(tmp[["internal_game_id", rest_col]])
    out = games[["internal_game_id"]].drop_duplicates()
    for part in rows:
        out = out.merge(part, on="internal_game_id", how="left")
    return out


def _winner_from_settlement(settle: pd.DataFrame, markets: pd.DataFrame) -> pd.DataFrame:
    yes = settle.loc[settle["settlement_status"].astype(str).str.upper() == "YES", ["internal_game_id", "market_id"]]
    linked = yes.merge(markets[["market_id", "team_side"]], on="market_id", how="left")
    linked["winner_side"] = linked["team_side"].astype(str)
    return linked.groupby("internal_game_id", as_index=False)["winner_side"].first()


def ingest_warehouse(
    *,
    months: tuple[str, ...] = REGULAR_MONTHS,
    dest: Path | None = None,
) -> dict[str, Any]:
    cfg = RollerConfig()
    obs_dir = observations_dir(cfg)
    files = [p for p in list_month_parquets(obs_dir) if any(m in p.name for m in months)]
    if not files:
        raise PathFeError("DATA_REQUIRED", f"no observation parquet in {obs_dir} for {months}")
    markets = pd.read_parquet(markets_path(cfg), columns=["market_id", "ticker", "internal_game_id", "team_side"])
    settle = pd.read_parquet(settlements_path(cfg), columns=["market_id", "internal_game_id", "settlement_status"])
    wh_games = pd.read_parquet(games_path(cfg), columns=["internal_game_id", "event_ticker"])
    canon = _canonical_games(cfg)
    games = wh_games.merge(
        canon[
            [
                "internal_game_id",
                "game_date",
                "actual_start",
                "result_available_at",
                "home_team_id",
                "away_team_id",
            ]
        ],
        on="internal_game_id",
        how="left",
    )
    games = games.merge(_rest_days(games), on="internal_game_id", how="left")
    games = games.merge(_winner_from_settlement(settle, markets), on="internal_game_id", how="left")
    opp = _opposite_map(markets)

    tick_parts: list[pd.DataFrame] = []
    for path in sorted(files):
        month = path.name.replace("month=", "").replace(".parquet", "")
        frame = pd.read_parquet(
            path,
            columns=[
                "ticker",
                "market_id",
                "internal_game_id",
                "available_at",
                "yes_bid_close",
                "yes_ask_close",
                "game_link_status",
            ],
        )
        frame = frame.loc[frame["game_link_status"].astype(str) == "LINKED"].copy()
        frame = frame.merge(
            games[
                [
                    "internal_game_id",
                    "actual_start",
                    "result_available_at",
                    "game_date",
                    "rest_home",
                    "rest_away",
                    "winner_side",
                    "home_team_id",
                    "away_team_id",
                ]
            ],
            on="internal_game_id",
            how="inner",
        )
        ts = frame["available_at"].map(_utc)
        start = frame["actual_start"].map(_utc)
        end = frame["result_available_at"].map(_utc)
        keep = ts.notna() & start.notna()
        # in-game window: tip through settlement; drop pregame overnight quotes
        keep = keep & (ts >= start) & (end.isna() | (ts <= end))
        frame = frame.loc[keep].copy()
        if frame.empty:
            continue
        frame["timestamp_utc"] = frame["available_at"].astype(str)
        frame["yes_bid"] = frame["yes_bid_close"].map(e4_to_cents)
        frame["yes_ask"] = frame["yes_ask_close"].map(e4_to_cents)
        frame = frame.loc[frame["yes_bid"].notna()].copy()
        frame["spread"] = frame["yes_ask"] - frame["yes_bid"]
        frame["size_bid"] = pd.NA
        frame["game_id"] = frame["internal_game_id"].astype(str)
        frame["era"] = month
        frame["season"] = int(month.replace("-", ""))
        frame["source"] = WAREHOUSE_SOURCE
        frame["book_source"] = "SOURCE_UNAVAILABLE"
        frame["impulse_style"] = 0
        frame["thin_style"] = 0
        frame["period"] = pd.NA
        frame["sec_left_period"] = pd.NA
        frame["sec_left_game"] = pd.NA
        frame["home_score"] = pd.NA
        frame["away_score"] = pd.NA
        frame["possession"] = pd.NA
        side_map = markets.set_index("market_id")["team_side"].to_dict()
        frame["side"] = frame["market_id"].map(side_map)
        frame["opposite_market_id"] = frame["market_id"].map(opp)
        frame = frame.loc[frame["side"].isin(["home", "away"])].copy()
        frame = frame.sort_values(["market_id", "timestamp_utc"])
        frame["t"] = frame.groupby("market_id").cumcount()
        tick_parts.append(
            frame[
                [
                    "game_id",
                    "era",
                    "season",
                    "market_id",
                    "opposite_market_id",
                    "side",
                    "t",
                    "timestamp_utc",
                    "period",
                    "sec_left_period",
                    "sec_left_game",
                    "yes_bid",
                    "yes_ask",
                    "spread",
                    "size_bid",
                    "home_score",
                    "away_score",
                    "possession",
                    "impulse_style",
                    "thin_style",
                    "source",
                    "book_source",
                    "rest_home",
                    "rest_away",
                    "winner_side",
                    "actual_start",
                ]
            ]
        )

    if not tick_parts:
        raise PathFeError("DATA_REQUIRED", "no in-game warehouse bars in selected months")
    ticks = pd.concat(tick_parts, ignore_index=True)
    game_rows = (
        ticks.groupby("game_id", as_index=False)
        .agg(
            era=("era", "first"),
            season=("season", "first"),
            tip_utc=("actual_start", "first"),
            winner_side=("winner_side", "first"),
            rest_home=("rest_home", "first"),
            rest_away=("rest_away", "first"),
        )
        .assign(source=WAREHOUSE_SOURCE, home_team="", away_team="")
    )
    game_rows["tip_utc"] = game_rows["tip_utc"].map(
        lambda v: v.isoformat() if hasattr(v, "isoformat") else (None if pd.isna(v) else str(v))
    )
    out = dest or raw_data_dir()
    out.mkdir(parents=True, exist_ok=True)
    ticks.drop(columns=["rest_home", "rest_away", "winner_side", "actual_start"], inplace=True)
    ticks.to_parquet(out / "ticks.parquet", index=False)
    game_rows.to_parquet(out / "games.parquet", index=False)
    markets.to_parquet(out / "markets.parquet", index=False)
    manifest = {
        "source": WAREHOUSE_SOURCE,
        "observation_basis": "TRADABLE_YES_BID",
        "observation_resolution": "1_MINUTE_CANDLE",
        "months": list(months),
        "n_ticks": int(len(ticks)),
        "n_games": int(game_rows["game_id"].nunique()),
        "n_markets": int(ticks["market_id"].nunique()),
        "warehouse_root": str(warehouse_root(cfg)),
        "orderbook": "SOURCE_UNAVAILABLE",
        "tick_data": False,
        "pbp_pit_aligned_to_candles": False,
        "candle_path_is_not_a_fill": True,
        "fee_model": "KALSHI_FEE_MODEL_UNRESOLVED",
        "note": (
            "Real Kalshi NBA 1m TRADABLE_YES_BID paths. "
            "L2 size not present. Score/clock attached later via PBP sequence, not candle PIT. "
            "Do not treat as live FIRST01 or a fill."
        ),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def attach_pbp_state(episodes: pd.DataFrame, cfg: RollerConfig | None = None) -> pd.DataFrame:
    """Last PBP event with event_timestamp <= t_s. NOT candle-PIT."""
    cfg = cfg or RollerConfig()
    files = list_month_parquets(pbp_dir(cfg))
    if not files:
        episodes["game_state_source"] = "PBP_ABSENT"
        return episodes
    parts = []
    cols = [
        "internal_game_id",
        "event_timestamp",
        "period",
        "clock",
        "home_score",
        "away_score",
        "possession",
        "home_away",
    ]
    for path in files:
        parts.append(pd.read_parquet(path, columns=cols))
    pbp = pd.concat(parts, ignore_index=True)
    pbp["pbp_ts"] = pbp["event_timestamp"].map(_utc)
    pbp = pbp.loc[pbp["pbp_ts"].notna()].sort_values(["internal_game_id", "pbp_ts"])
    ep = episodes.copy()
    drop = [c for c in ("period", "sec_left_period", "sec_left_game", "home_score", "away_score", "possession") if c in ep.columns]
    ep = ep.drop(columns=drop)
    ep["sig_ts"] = pd.to_datetime(ep["timestamp_utc"].map(_utc), utc=True)
    pbp = pbp.rename(columns={"internal_game_id": "game_id"})
    pbp["pbp_ts"] = pd.to_datetime(pbp["pbp_ts"], utc=True)
    pbp["game_id"] = pbp["game_id"].astype(str)
    ep["game_id"] = ep["game_id"].astype(str)
    ep = ep.dropna(subset=["sig_ts"])
    pbp = pbp.dropna(subset=["pbp_ts"])
    chunks: list[pd.DataFrame] = []
    pbp_g = {gid: g.sort_values("pbp_ts") for gid, g in pbp.groupby("game_id", sort=False)}
    for gid, e in ep.groupby("game_id", sort=False):
        right = pbp_g.get(gid)
        left = e.sort_values("sig_ts")
        if right is None or right.empty:
            chunks.append(left)
            continue
        chunks.append(
            pd.merge_asof(
                left,
                right.drop(columns=["game_id"]),
                left_on="sig_ts",
                right_on="pbp_ts",
                direction="backward",
            )
        )
    joined = pd.concat(chunks, ignore_index=True) if chunks else ep
    joined["period"] = pd.to_numeric(joined["period"], errors="coerce")
    joined["sec_left_period"] = joined["clock"].map(clock_to_seconds)
    joined["sec_left_game"] = joined.apply(_sec_left_game, axis=1)
    joined["home_score"] = pd.to_numeric(joined["home_score"], errors="coerce")
    joined["away_score"] = pd.to_numeric(joined["away_score"], errors="coerce")
    # possession: 1 if the priced side has the ball, else 0; unknown stays NA
    poss_side = joined["home_away"].astype(str)
    joined["possession"] = [
        (1 if ps == sd else 0) if ps in {"home", "away"} and sd in {"home", "away"} else None
        for ps, sd in zip(poss_side, joined["side"].astype(str))
    ]
    joined["game_state_source"] = "PBP_SEQUENCE_NOT_PIT"
    return joined.drop(columns=["sig_ts", "pbp_ts", "clock", "home_away"], errors="ignore")


def _sec_left_game(rec: pd.Series) -> float | None:
    period = rec.get("period")
    left = rec.get("sec_left_period")
    if pd.isna(period) or pd.isna(left):
        return None
    remain_after = max(0, 4 - int(period)) * 720
    return float(int(left) + remain_after)


def _opposite_map(markets: pd.DataFrame) -> dict[str, str]:
    out: dict[str, str] = {}
    for gid, g in markets.groupby("internal_game_id"):
        sides = {str(r.team_side): str(r.market_id) for r in g.itertuples(index=False)}
        if "home" in sides and "away" in sides:
            out[sides["home"]] = sides["away"]
            out[sides["away"]] = sides["home"]
    _ = gid
    return out


def load_raw(raw: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    root = raw or raw_data_dir()
    ticks_p = root / "ticks.parquet"
    games_p = root / "games.parquet"
    if not ticks_p.is_file() or not games_p.is_file():
        raise PathFeError("DATA_REQUIRED", f"raw ticks/games missing under {root}")
    return pd.read_parquet(ticks_p), pd.read_parquet(games_p)
