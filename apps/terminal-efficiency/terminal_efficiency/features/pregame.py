"""Point-in-time pregame team features. Priors require result_available_at < target start."""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from terminal_efficiency.clocks import parse_utc


def _mean(xs: list[float | None]) -> float | None:
    vals = [x for x in xs if x is not None]
    if not vals:
        return None
    return float(sum(vals) / len(vals))


def _appearances(games: pd.DataFrame) -> dict[str, list[dict]]:
    by_team: dict[str, list[dict]] = defaultdict(list)
    for g in games.to_dict("records"):
        if g.get("final_home_win") is None:
            continue
        end = parse_utc(g.get("result_available_at"))
        if end is None:
            continue
        common = {
            "game_id": g["game_id"],
            "game_date": g.get("game_date"),
            "result_available_at": end,
            "scheduled_start": parse_utc(g.get("scheduled_start")),
            "ortg": None,
            "drtg": None,
            "pace": None,
            "efg": None,
            "tov": None,
            "orb": None,
            "ftr": None,
            "won": False,
            "opponent": "",
        }
        home = dict(common)
        home.update(
            {
                "ortg": g.get("home_ortg"),
                "drtg": g.get("home_drtg"),
                "pace": g.get("home_pace"),
                "efg": g.get("home_efg"),
                "tov": g.get("home_tov_rate"),
                "orb": g.get("home_orb_rate"),
                "ftr": g.get("home_ft_rate"),
                "won": bool(g.get("final_home_win")),
                "opponent": g.get("away_team_id"),
            }
        )
        away = dict(common)
        away.update(
            {
                "ortg": g.get("away_ortg"),
                "drtg": g.get("away_drtg"),
                "pace": g.get("away_pace"),
                "efg": g.get("away_efg"),
                "tov": g.get("away_tov_rate"),
                "orb": g.get("away_orb_rate"),
                "ftr": g.get("away_ft_rate"),
                "won": not bool(g.get("final_home_win")),
                "opponent": g.get("home_team_id"),
            }
        )
        by_team[str(g["home_team_id"])].append(home)
        by_team[str(g["away_team_id"])].append(away)
    for team, apps in by_team.items():
        by_team[team] = sorted(apps, key=lambda a: a["result_available_at"])
    return by_team


def priors_before(apps: list[dict], cutoff) -> list[dict]:
    if cutoff is None:
        return []
    return [a for a in apps if a["result_available_at"] < cutoff and a["game_id"]]


def _team_stats(priors: list[dict]) -> dict:
    n = len(priors)
    wins = sum(1 for p in priors if p["won"])
    last5 = priors[-5:]
    last10 = priors[-10:]
    ortg = _mean([p["ortg"] for p in priors])
    drtg = _mean([p["drtg"] for p in priors])
    return {
        "games_played_pre": n,
        "win_pct_pre": (wins / n) if n else None,
        "wins_last5_pre": sum(1 for p in last5 if p["won"]),
        "wins_last10_pre": sum(1 for p in last10 if p["won"]),
        "ortg_pre": ortg,
        "drtg_pre": drtg,
        "net_rating_pre": (ortg - drtg) if ortg is not None and drtg is not None else None,
        "pace_pre": _mean([p["pace"] for p in priors]),
        "efg_pre": _mean([p["efg"] for p in priors]),
        "tov_rate_pre": _mean([p["tov"] for p in priors]),
        "orb_rate_pre": _mean([p["orb"] for p in priors]),
        "ft_rate_pre": _mean([p["ftr"] for p in priors]),
        "as_of": priors[-1]["result_available_at"] if priors else None,
        "opp_win_pcts": [],
    }


def build_pregame_features(games: pd.DataFrame) -> pd.DataFrame:
    by_team = _appearances(games)
    # opponent win% for SOS uses each opponent's priors before this game
    rows = []
    for g in games.to_dict("records"):
        start = parse_utc(g.get("scheduled_start"))
        hid, aid = str(g.get("home_team_id")), str(g.get("away_team_id"))
        hp = priors_before(by_team.get(hid, []), start)
        ap = priors_before(by_team.get(aid, []), start)
        hs, aws = _team_stats(hp), _team_stats(ap)

        def sos(priors: list[dict]) -> float | None:
            rates = []
            for p in priors:
                opp_apps = priors_before(by_team.get(str(p["opponent"]), []), p["result_available_at"])
                if opp_apps:
                    rates.append(sum(1 for x in opp_apps if x["won"]) / len(opp_apps))
            return _mean(rates)

        rest_h = None
        rest_a = None
        if hp and hp[-1].get("game_date") and g.get("game_date"):
            rest_h = (pd.Timestamp(g["game_date"]) - pd.Timestamp(hp[-1]["game_date"])).days
        if ap and ap[-1].get("game_date") and g.get("game_date"):
            rest_a = (pd.Timestamp(g["game_date"]) - pd.Timestamp(ap[-1]["game_date"])).days
        as_of = None
        cands = [hs["as_of"], aws["as_of"]]
        cands = [c for c in cands if c is not None]
        if cands:
            as_of = max(cands)
        # No priors: there is no later-than-tip information. Leave as_of at
        # scheduled_start so clocks are defined, not a future leak.
        rows.append(
            {
                "game_id": g["game_id"],
                "league": g.get("league"),
                "season": g.get("season"),
                "game_date": g.get("game_date"),
                "scheduled_start": g.get("scheduled_start"),
                "result_available_at": g.get("result_available_at"),
                "home_team_id": hid,
                "away_team_id": aid,
                "final_home_win": g.get("final_home_win"),
                "final_home_score": g.get("final_home_score"),
                "final_away_score": g.get("final_away_score"),
                "home_games_played_pre": hs["games_played_pre"],
                "away_games_played_pre": aws["games_played_pre"],
                "home_win_pct_pre": hs["win_pct_pre"],
                "away_win_pct_pre": aws["win_pct_pre"],
                "home_wins_last5_pre": hs["wins_last5_pre"],
                "away_wins_last5_pre": aws["wins_last5_pre"],
                "home_wins_last10_pre": hs["wins_last10_pre"],
                "away_wins_last10_pre": aws["wins_last10_pre"],
                "home_ortg_pre": hs["ortg_pre"],
                "away_ortg_pre": aws["ortg_pre"],
                "home_drtg_pre": hs["drtg_pre"],
                "away_drtg_pre": aws["drtg_pre"],
                "home_net_rating_pre": hs["net_rating_pre"],
                "away_net_rating_pre": aws["net_rating_pre"],
                "home_pace_pre": hs["pace_pre"],
                "away_pace_pre": aws["pace_pre"],
                "home_efg_pre": hs["efg_pre"],
                "away_efg_pre": aws["efg_pre"],
                "home_tov_rate_pre": hs["tov_rate_pre"],
                "away_tov_rate_pre": aws["tov_rate_pre"],
                "home_orb_rate_pre": hs["orb_rate_pre"],
                "away_orb_rate_pre": aws["orb_rate_pre"],
                "home_ft_rate_pre": hs["ft_rate_pre"],
                "away_ft_rate_pre": aws["ft_rate_pre"],
                "home_sos_pre": sos(hp),
                "away_sos_pre": sos(ap),
                "home_rest_days": rest_h,
                "away_rest_days": rest_a,
                "feature_as_of_timestamp": as_of.isoformat().replace("+00:00", "Z") if as_of else g.get("scheduled_start"),
                "prediction_timestamp": g.get("scheduled_start"),
                "p5_vs_p5": g.get("p5_vs_p5"),
                "season_type": g.get("season_type"),
            }
        )
    return pd.DataFrame(rows)
