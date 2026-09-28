"""Schema, identity, time-order, and registry integrity checks."""

from __future__ import annotations

from typing import Any

import pandas as pd

from roller.admin import load_dataset, load_identity
from roller.config import RollerConfig
from roller.identity import MAPPING_MAPPED
from roller.registry import missing_required_paths
from roller.timeutil import series_to_utc


def run_integrity(cfg: RollerConfig, sports: list[str] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    sports = sports or cfg.sport_ids()

    for p in missing_required_paths(cfg):
        errors.append(f"required registry path missing: {p}")

    ident = load_identity(cfg)
    if ident.empty:
        errors.append("game_identity.csv is empty or missing")
    else:
        if ident["internal_game_id"].duplicated().any():
            errors.append("duplicate internal_game_id")
        if (ident["home_team_id"] == ident["away_team_id"]).any():
            errors.append("home_team_id == away_team_id")
        if (~ident["sport"].isin(cfg.sport_ids())).any():
            errors.append("identity row with unknown sport")

    for sport in sports:
        for season in cfg.season_labels(sport):
            try:
                games = load_dataset(cfg, sport, season, "games")
            except FileNotFoundError:
                # Pending seasons are not a failure; required paths are checked above.
                continue
            if games.empty:
                continue
            if games["internal_game_id"].duplicated().any():
                errors.append(f"{sport} {season} duplicate game pk")
            if (games["home_team_id"] == games["away_team_id"]).any():
                errors.append(f"{sport} {season} home == away")
            for col in ("event_timestamp", "available_at", "ingested_at"):
                if col not in games.columns:
                    errors.append(f"{sport} {season} games missing {col}")

            try:
                pbp = load_dataset(cfg, sport, season, "pbp")
            except FileNotFoundError:
                pbp = pd.DataFrame()
            if not pbp.empty:
                if pbp.duplicated(["internal_game_id", "event_number"]).any():
                    errors.append(f"{sport} {season} duplicate pbp pk")
                ts = series_to_utc(pbp["available_at"])
                ordered = pbp.assign(_t=ts).dropna(subset=["_t"])
                for gid, grp in ordered.groupby("internal_game_id", sort=False):
                    times = grp["_t"].tolist()
                    if times != sorted(times):
                        errors.append(f"{sport} {season} pbp not time-ordered {gid}")
                        break

            try:
                candles = load_dataset(cfg, sport, season, "kalshi_candles")
            except FileNotFoundError:
                candles = pd.DataFrame()
            if not candles.empty and not ident.empty:
                mapped = set(ident.loc[ident["mapping_status"] == MAPPING_MAPPED, "internal_game_id"])
                extra = set(candles["internal_game_id"].astype(str)) - mapped
                if extra:
                    errors.append(
                        f"{sport} {season} unmapped games in kalshi_candles: {sorted(extra)[:5]}"
                    )
            try:
                pm = load_dataset(cfg, sport, season, "polymarket_candles")
            except (FileNotFoundError, KeyError):
                pm = pd.DataFrame()
            if not pm.empty:
                if "yes_bid_close" in pm.columns and pm["yes_bid_close"].astype(str).str.strip().ne("").any():
                    errors.append(
                        f"{sport} {season} polymarket_candles invented yes_bid_close from last price"
                    )
                known = set(ident["internal_game_id"].astype(str)) if not ident.empty else set()
                extra_pm = set(pm["internal_game_id"].astype(str)) - known
                extra_pm.discard("")
                if extra_pm:
                    errors.append(
                        f"{sport} {season} unknown internal_game_id in polymarket_candles: {sorted(extra_pm)[:5]}"
                    )

    return {"status": "FAIL" if errors else "PASS", "errors": errors, "warnings": warnings}
