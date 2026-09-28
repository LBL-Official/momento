"""Build possession-level Dataset B: PIT game state + pregame priors + terminal label."""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from terminal_efficiency.clocks import parse_utc, to_iso
from terminal_efficiency.config import LeagueConfig
from terminal_efficiency.features.pregame import build_pregame_features
from terminal_efficiency.state.possession_builder import reconstruct_possessions
from terminal_efficiency.validation.temporal_split import add_split


def _recent_run(events: list[dict], i: int, n: int = 8) -> int:
    window = events[max(0, i - n) : i + 1]
    if not window:
        return 0
    return int(window[-1]["score_difference"] - window[0]["score_difference"])


def build_possession_observations(
    games: pd.DataFrame,
    events: list[dict],
    cfg: LeagueConfig,
) -> pd.DataFrame:
    pregame = build_pregame_features(games)
    pre_by_id = {r["game_id"]: r for r in pregame.to_dict("records")}
    games_by_id = {r["game_id"]: r for r in games.to_dict("records")}
    events_by_game: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        events_by_game[str(e["game_id"])].append(e)

    rows = []
    for gid, evs in events_by_game.items():
        evs = sorted(evs, key=lambda e: int(e.get("event_number") or 0))
        poss = reconstruct_possessions(evs, sport=cfg.league)
        g = games_by_id.get(gid, {})
        pre = pre_by_id.get(gid, {})
        if cfg.league == "NCAAB" and cfg.p5_only_in_game and not g.get("p5_vs_p5"):
            continue
        if str(g.get("game_id") or gid)[:3] in cfg.exclude_game_id_prefixes:
            continue
        hid, aid = str(g.get("home_team_id") or ""), str(g.get("away_team_id") or "")
        ev_ix = {int(e.get("event_number") or -1): i for i, e in enumerate(evs)}
        for p in poss:
            if p.get("end_status") in {"UNRESOLVED"}:
                continue
            end_n = int(p.get("end_event_number") or 0)
            i = ev_ix.get(end_n, len(evs) - 1)
            e = evs[i]
            pred = parse_utc(e.get("available_at") or e.get("event_timestamp"))
            start = parse_utc(g.get("scheduled_start"))
            feat_as_of = parse_utc(pre.get("feature_as_of_timestamp")) or start
            # in-game state as-of is the event time; pregame as-of is last prior result
            # observation feature_as_of is the max of allowed clocks that is still <= pred
            if pred and feat_as_of and feat_as_of > pred:
                feat_as_of = pred
            pace = pre.get("home_pace_pre")
            srg = float(e.get("seconds_remaining_game") or 0)
            est_rem = None
            if pace and pace > 0:
                est_rem = srg / 60.0 * (pace / cfg.pace_minutes)
            off = str(p.get("offensive_team_id") or "")
            rows.append(
                {
                    "observation_id": f"TE_{gid}_{p.get('possession_uid')}",
                    "league": cfg.league,
                    "season": g.get("season"),
                    "game_id": gid,
                    "market_id": None,
                    "prediction_timestamp": to_iso(pred) if pred else e.get("event_timestamp"),
                    "feature_as_of_timestamp": to_iso(feat_as_of) if feat_as_of else pre.get("feature_as_of_timestamp"),
                    "game_event_timestamp": e.get("event_timestamp"),
                    "market_timestamp": None,
                    "period": e.get("period"),
                    "seconds_remaining_period": e.get("seconds_remaining_period"),
                    "seconds_remaining_game": e.get("seconds_remaining_game"),
                    "home_team_id": hid,
                    "away_team_id": aid,
                    "home_score": e.get("home_score"),
                    "away_score": e.get("away_score"),
                    "score_difference": e.get("score_difference"),
                    "possession_team": off,
                    "possession_home": 1 if off and off == hid else (0 if off else None),
                    "current_run_home": _recent_run(evs, i),
                    "est_possessions_remaining": est_rem,
                    "end_status": p.get("end_status"),
                    "end_reason": p.get("end_reason"),
                    "timestamp_quality": e.get("timestamp_quality"),
                    "data_quality_flags": e.get("timestamp_quality") or "",
                    "final_home_win": bool(g.get("final_home_win")) if g.get("final_home_win") is not None else None,
                    "game_date": g.get("game_date"),
                    "scheduled_start": g.get("scheduled_start"),
                    "home_games_played_pre": pre.get("home_games_played_pre"),
                    "away_games_played_pre": pre.get("away_games_played_pre"),
                    "home_win_pct_pre": pre.get("home_win_pct_pre"),
                    "away_win_pct_pre": pre.get("away_win_pct_pre"),
                    "home_wins_last5_pre": pre.get("home_wins_last5_pre"),
                    "away_wins_last5_pre": pre.get("away_wins_last5_pre"),
                    "home_wins_last10_pre": pre.get("home_wins_last10_pre"),
                    "away_wins_last10_pre": pre.get("away_wins_last10_pre"),
                    "home_ortg_pre": pre.get("home_ortg_pre"),
                    "away_ortg_pre": pre.get("away_ortg_pre"),
                    "home_drtg_pre": pre.get("home_drtg_pre"),
                    "away_drtg_pre": pre.get("away_drtg_pre"),
                    "home_net_rating_pre": pre.get("home_net_rating_pre"),
                    "away_net_rating_pre": pre.get("away_net_rating_pre"),
                    "home_pace_pre": pre.get("home_pace_pre"),
                    "away_pace_pre": pre.get("away_pace_pre"),
                    "home_efg_pre": pre.get("home_efg_pre"),
                    "away_efg_pre": pre.get("away_efg_pre"),
                    "home_tov_rate_pre": pre.get("home_tov_rate_pre"),
                    "away_tov_rate_pre": pre.get("away_tov_rate_pre"),
                    "home_orb_rate_pre": pre.get("home_orb_rate_pre"),
                    "away_orb_rate_pre": pre.get("away_orb_rate_pre"),
                    "home_ft_rate_pre": pre.get("home_ft_rate_pre"),
                    "away_ft_rate_pre": pre.get("away_ft_rate_pre"),
                    "home_sos_pre": pre.get("home_sos_pre"),
                    "away_sos_pre": pre.get("away_sos_pre"),
                    "home_rest_days": pre.get("home_rest_days"),
                    "away_rest_days": pre.get("away_rest_days"),
                    "xib_home_win_probability": None,
                    "mcd_home_win_probability": None,
                }
            )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return add_split(df, cfg.train_end)
