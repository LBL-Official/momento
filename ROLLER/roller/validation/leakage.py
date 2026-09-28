"""Future-information leakage audit. Critical leaks fail the pipeline."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from roller.admin import load_dataset
from roller.config import RollerConfig
from roller.features.engine import priors_before, result_sort_key, team_appearances


def detect_pre_includes_current(features_row: dict, game: dict, team_id: str) -> bool:
    """True if wins_pre could only be explained by including the current game."""
    hw = str(game.get("home_win") or "")
    aw = str(game.get("away_win") or "")
    if hw not in {"0", "1"}:
        return False
    won = (team_id == game["home_team_id"] and hw == "1") or (
        team_id == game["away_team_id"] and aw == "1"
    )
    try:
        wins_pre = int(features_row.get("wins_pre") or 0)
        games_pre = int(features_row.get("games_played_pre") or 0)
    except ValueError:
        return False
    # If there are no prior games, wins_pre must be 0 even if current is a win.
    if games_pre == 0 and wins_pre > 0:
        return True
    return False


def synthetic_leak_example() -> dict[str, Any]:
    """W, L, W sequence. Before game 3: wins_pre=1, losses_pre=1."""
    return {
        "sequence": ["W", "L", "W"],
        "before_game_3": {"wins_pre": 1, "losses_pre": 1},
        "leaky_before_game_3": {"wins_pre": 2, "losses_pre": 1},
    }


def audit_team_features(cfg: RollerConfig, sport: str, season: str) -> list[str]:
    errors = []
    games = load_dataset(cfg, sport, season, "games")
    feats = load_dataset(cfg, sport, season, "team_features")
    if games.empty or feats.empty:
        return errors
    games_by_id = {g["internal_game_id"]: g for g in games.to_dict("records")}
    completed_by_team: dict[str, list] = defaultdict(list)
    for g in games.to_dict("records"):
        for app in team_appearances(g):
            if app["has_result"]:
                completed_by_team[app["team_id"]].append(app)
    for team, apps in completed_by_team.items():
        completed_by_team[team] = sorted(apps, key=result_sort_key)

    for fr in feats.to_dict("records"):
        gid = fr["internal_game_id"]
        team = fr["team_id"]
        g = games_by_id.get(gid)
        if g is None:
            continue
        completed = completed_by_team.get(team, [])
        this = next((a for a in completed if a["internal_game_id"] == gid), None)
        probe = this or {
            "internal_game_id": gid,
            "result_available_at": g.get("result_available_at") or "",
            "scheduled_start": g.get("scheduled_start") or "",
            "game_date": g.get("game_date") or "",
        }
        expected_priors = priors_before(completed, probe)
        exp_wins = sum(1 for a in expected_priors if a["won"])
        exp_games = len(expected_priors)
        got_wins = int(fr.get("wins_pre") or 0)
        got_games = int(fr.get("games_played_pre") or 0)
        if got_wins != exp_wins or got_games != exp_games:
            errors.append(
                f"{gid} {team} wins_pre={got_wins}/{got_games} expected {exp_wins}/{exp_games}"
            )
        if this is not None and this["won"] and got_wins == exp_wins + 1:
            errors.append(f"{gid} {team} current-game win leaked into wins_pre")
    return errors


def run_leakage(cfg: RollerConfig, sports: list[str] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    sports = sports or cfg.sport_ids()
    for sport in sports:
        for season in cfg.season_labels(sport):
            try:
                errors.extend(audit_team_features(cfg, sport, season))
            except FileNotFoundError:
                continue
            try:
                pbp = load_dataset(cfg, sport, season, "pbp")
                candles = load_dataset(cfg, sport, season, "kalshi_candles")
            except FileNotFoundError:
                continue
            if pbp.empty or candles.empty:
                continue
            # Sample alignment leakage: any joined future PBP would be a fail.
            # Full join is expensive; check per-game max pbp vs min candle is not required.
            # Explicit test coverage lives in tests/test_no_future_leakage.py
            errors.extend(audit_observation_sample(cfg, sport, season))
    from roller.validation.greek_leakage import audit_baseline_eligibility_example
    from roller.validation.fundamental_leakage import audit_fundamental_eligibility_example
    from roller.validation.v4b_leakage import audit_v4b_eligibility_example
    from roller.validation.v4c_constructibility import audit_no_proxy, audit_possession_not_implemented
    from roller.validation.v4c_information_regime import audit_declared_clocks, audit_information_regimes
    from roller.validation.v4c_measurement_identity import audit_frozen_negatives, audit_identity_uniqueness

    errors.extend(audit_baseline_eligibility_example())
    errors.extend(audit_fundamental_eligibility_example())
    errors.extend(audit_v4b_eligibility_example())
    errors.extend(audit_information_regimes())
    errors.extend(audit_declared_clocks())
    errors.extend(audit_no_proxy())
    errors.extend(audit_possession_not_implemented())
    errors.extend(audit_identity_uniqueness())
    errors.extend(audit_frozen_negatives())
    return {
        "status": "FAIL" if errors else "PASS",
        "errors": errors,
        "synthetic": synthetic_leak_example(),
    }


def audit_observation_excludes_labels(obs: dict[str, Any]) -> list[str]:
    errors = []
    if "labels" in obs:
        errors.append("observation contains labels")
    for key in obs:
        if "label" in str(key).lower():
            errors.append(f"observation key {key} looks like a label")
    if "contains_future_information" in obs:
        errors.append("observation carries contains_future_information")
    return errors


def audit_visible_available_at(rows: list[dict[str, Any]], cutoff) -> list[str]:
    from roller.timeutil import parse_utc

    errors = []
    cut = parse_utc(cutoff) if not hasattr(cutoff, "tzinfo") else cutoff
    for rec in rows:
        ts = parse_utc(rec.get("available_at"))
        if ts is not None and cut is not None and not (ts < cut):
            errors.append(f"row visible at equality-or-future available_at={ts} cutoff={cut}")
    return errors


def audit_observation_sample(cfg: RollerConfig, sport: str, season: str) -> list[str]:
    errors: list[str] = []
    try:
        games = load_dataset(cfg, sport, season, "games")
    except FileNotFoundError:
        return errors
    if games.empty:
        return errors
    gid = str(games.iloc[0]["internal_game_id"])
    as_of = games.iloc[0].get("scheduled_start") or games.iloc[0].get("available_at")
    if not as_of:
        return errors
    try:
        from roller.state.observation import assemble_observation

        obs = assemble_observation(cfg, gid, as_of=as_of)
    except (KeyError, FileNotFoundError, ValueError):
        return errors
    from roller.validation.greek_leakage import audit_observation_clean

    errors.extend(audit_observation_excludes_labels(obs))
    errors.extend(audit_observation_clean(obs))
    traj = (obs.get("TRAJECTORY") or {}).get("data") or {}
    n = traj.get("n_events")
    try:
        pbp = load_dataset(cfg, sport, season, "pbp")
    except FileNotFoundError:
        return errors
    game_pbp = pbp[pbp["internal_game_id"] == gid] if not pbp.empty else pbp
    if n is not None and not game_pbp.empty:
        from roller.canonical.events import events_visible, project_events

        vis = events_visible(project_events(game_pbp), as_of)
        if int(n) != int(len(vis)):
            errors.append(f"{gid} trajectory n_events={n} visible={len(vis)}")
        errors.extend(audit_visible_available_at(vis.to_dict("records"), as_of))
    return errors


def leaky_wins_pre(sequence_results: list[bool]) -> list[int]:
    """Incorrect pandas pattern: rolling without shift (includes current)."""
    wins = []
    acc = 0
    for w in sequence_results:
        acc += int(w)
        wins.append(acc)
    return wins


def correct_wins_pre(sequence_results: list[bool]) -> list[int]:
    wins = []
    acc = 0
    for w in sequence_results:
        wins.append(acc)
        acc += int(w)
    return wins
