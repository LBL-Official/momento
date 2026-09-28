"""Assemble O_t at query time. Not a stored everything-at-every-t table. No labels."""

from __future__ import annotations

from typing import Any

import pandas as pd

from roller.admin import load_dataset, load_identity
from roller.canonical.align import latest_pbp
from roller.canonical.events import events_visible, project_events
from roller.config import RollerConfig
from roller.point_in_time.filters import AsOfRequiredError, public_filter
from roller.state.capabilities import capability
from roller.state.game import game_state_section
from roller.state.information import information_state_section
from roller.state.lineup import lineup_state
from roller.state.market import market_state_section
from roller.state.missingness import section
from roller.state.observation_id import make_observation_id
from roller.state.player import player_state
from roller.state.possessions import reconstruct_possessions
from roller.state.team import team_state_section
from roller.state.trajectory import trajectory_features
from roller.measurement.backward import backward_measurements
from roller.timeutil import resolve_cutoff, to_iso


def _load_optional(cfg: RollerConfig, sport: str, season: str, name: str) -> pd.DataFrame:
    try:
        return load_dataset(cfg, sport, season, name)
    except (FileNotFoundError, KeyError):
        return pd.DataFrame()


def assemble_observation(
    cfg: RollerConfig,
    internal_game_id: str,
    *,
    as_of=None,
    end_of_day: bool = False,
    full_history: bool = False,
) -> dict[str, Any]:
    if as_of is None and not full_history:
        raise AsOfRequiredError("observation requires as_of or full_history=True")
    ident = load_identity(cfg)
    hit = ident[ident["internal_game_id"] == internal_game_id]
    if hit.empty:
        raise KeyError(internal_game_id)
    rec = hit.iloc[0].to_dict()
    sport, season = rec["sport"], rec["season"]
    cutoff = resolve_cutoff(as_of or "9999-12-31", end_of_day=end_of_day)
    oid = make_observation_id(internal_game_id, cutoff, cfg.state_schema_version)

    games = _load_optional(cfg, sport, season, "games")
    if not games.empty and not full_history:
        games = public_filter(games, as_of=as_of, end_of_day=end_of_day, mask_results=True)
    game_row = games[games["internal_game_id"] == internal_game_id] if not games.empty else games
    game = game_row.iloc[0].to_dict() if game_row is not None and not game_row.empty else None

    pbp = _load_optional(cfg, sport, season, "pbp")
    if not pbp.empty:
        pbp = pbp[pbp["internal_game_id"] == internal_game_id]
    candles = _load_optional(cfg, sport, season, "kalshi_candles")
    if not candles.empty:
        candles = candles[candles["internal_game_id"] == internal_game_id]
    feats = _load_optional(cfg, sport, season, "team_features")
    if not feats.empty:
        feats = feats[feats["internal_game_id"] == internal_game_id]

    as_of_arg = None if full_history else as_of
    latest = None
    if pbp is not None and not pbp.empty and as_of_arg is not None:
        latest = latest_pbp(pbp, as_of_arg, end_of_day=end_of_day)
    elif pbp is not None and not pbp.empty and full_history:
        latest = pbp.iloc[-1]

    vis_events = (
        pbp
        if full_history or pbp is None or pbp.empty
        else events_visible(project_events(pbp), as_of_arg, end_of_day=end_of_day)
    )
    poss_cap = capability(sport, "possessions")
    if poss_cap == "NOT_SUPPORTED":
        poss_section = section("NOT_SUPPORTED", None)
    else:
        built = reconstruct_possessions(vis_events, sport=sport)
        poss_section = section(built["status"], {"possessions": built["possessions"]})

    return {
        "observation_id": oid,
        "internal_game_id": internal_game_id,
        "sport": sport,
        "season": season,
        "observation_time": to_iso(cutoff),
        "state_schema_version": cfg.state_schema_version,
        "GAME_STATE": game_state_section(
            pbp, game, sport=sport, as_of=as_of_arg or cutoff, end_of_day=end_of_day
        ),
        "TEAM_STATE": team_state_section(
            feats,
            game,
            None if latest is None else latest.to_dict(),
            as_of=as_of_arg,
            end_of_day=end_of_day,
            full_history=full_history,
        ),
        "PLAYER_STATE": player_state(
            pbp, sport=sport, as_of=as_of_arg or cutoff, end_of_day=end_of_day
        ),
        "LINEUP_STATE": lineup_state(
            pbp, sport=sport, as_of=as_of_arg or cutoff, end_of_day=end_of_day
        ),
        "MARKET_STATE": market_state_section(candles, as_of=as_of_arg or cutoff, end_of_day=end_of_day),
        "INFORMATION_STATE": information_state_section(sport),
        "TRAJECTORY": trajectory_features(pbp, as_of=as_of_arg or cutoff, end_of_day=end_of_day),
        "POSSESSIONS": poss_section,
        "BACKWARD_MEASUREMENTS": backward_measurements(
            candles, as_of_arg or cutoff, end_of_day=end_of_day
        ),
    }
