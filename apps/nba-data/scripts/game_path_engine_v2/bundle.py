"""Compute the full game-feature bundle for one aligned observation."""

from __future__ import annotations

from functools import lru_cache

from gamepath import features_at_snap
from pbp import box_header, enrich_actions, load_box, load_pbp


@lru_cache(maxsize=2048)
def enriched_for_game(nba_game_id: str) -> list:
    pbp = load_pbp(nba_game_id)
    box = load_box(nba_game_id)
    header = box_header(box)
    return enrich_actions((pbp or {}).get("game", {}).get("actions") or [], header)


def team_is_home(obs: dict) -> bool | None:
    code = (obs.get("team_code") or "").upper()
    home = (obs.get("home_team_code") or "").upper()
    away = (obs.get("away_team_code") or "").upper()
    if code and home and code == home:
        return True
    if code and away and code == away:
        return False
    return None


def compute_game_features(obs: dict) -> dict:
    nba_id = obs.get("nba_game_id")
    snap_idx = obs.get("snap_idx")
    phase = obs.get("game_phase") or "UNALIGNED"
    home = team_is_home(obs)
    if nba_id is None or home is None:
        return features_at_snap([], None, True, phase)
    actions = enriched_for_game(nba_id)
    idx = snap_idx if isinstance(snap_idx, int) else None
    return features_at_snap(actions, idx, home, phase)
