"""Build NBA game catalog + box aggregates from LeagueGameLog and boxscore summaries."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from terminal_efficiency.clocks import add_duration, parse_utc, to_iso
from terminal_efficiency.paths import derived_root, warehouse
from terminal_efficiency.provenance import write_json


def _load_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _season_type_from_game_id(game_id: str) -> str:
    prefix = str(game_id)[:3]
    return {
        "001": "PRESEASON",
        "002": "REGULAR_SEASON",
        "003": "ALL_STAR",
        "004": "PLAYOFFS",
        "005": "PLAY_IN",
    }.get(prefix, "OTHER")


def _pair_leaguegamelog(rows: list[dict]) -> list[dict]:
    by_id: dict[str, list[dict]] = {}
    for r in rows:
        gid = str(r.get("GAME_ID") or "")
        if gid:
            by_id.setdefault(gid, []).append(r)
    games = []
    for gid, pair in by_id.items():
        home = away = None
        for r in pair:
            matchup = str(r.get("MATCHUP") or "")
            if " @ " in matchup:
                away = r
            else:
                home = r
        if home is None or away is None:
            if len(pair) == 2:
                # fallback: second listed vs first is unreliable — skip rather than guess sides
                continue
            continue
        hs = int(home.get("PTS") or 0)
        aws = int(away.get("PTS") or 0)
        games.append(
            {
                "game_id": gid,
                "league": "NBA",
                "season": None,
                "season_type": _season_type_from_game_id(gid),
                "game_date": home.get("GAME_DATE") or away.get("GAME_DATE"),
                "home_team_id": str(home.get("TEAM_ABBREVIATION") or ""),
                "away_team_id": str(away.get("TEAM_ABBREVIATION") or ""),
                "home_team_nba_id": home.get("TEAM_ID"),
                "away_team_nba_id": away.get("TEAM_ID"),
                "final_home_score": hs,
                "final_away_score": aws,
                "final_home_win": bool(hs > aws),
                "home_box": home,
                "away_box": away,
            }
        )
    return games


def _possessions_from_box(box: dict) -> float:
    fga = float(box.get("FGA") or 0)
    oreb = float(box.get("OREB") or 0)
    tov = float(box.get("TOV") or 0)
    fta = float(box.get("FTA") or 0)
    return fga - oreb + tov + 0.44 * fta


def enrich_boxscore(game: dict, box_path: Path) -> dict:
    raw = _load_json(box_path)
    if not raw:
        game["scheduled_start"] = f"{game['game_date']}T00:00:00Z"
        game["result_available_at"] = f"{game['game_date']}T23:59:59Z"
        game["start_quality"] = "UNAVAILABLE"
        return game
    bss = raw.get("boxScoreSummary") or raw
    start = parse_utc(bss.get("gameTimeUTC"))
    end = add_duration(start, bss.get("duration"))
    game["scheduled_start"] = to_iso(start) or f"{game['game_date']}T00:00:00Z"
    game["result_available_at"] = to_iso(end) or f"{game['game_date']}T23:59:59Z"
    game["start_quality"] = "OBSERVED" if start else "UNAVAILABLE"
    game["duration"] = bss.get("duration")
    ht = (bss.get("homeTeam") or {}).get("teamTricode")
    at = (bss.get("awayTeam") or {}).get("teamTricode")
    if ht:
        game["home_team_id"] = str(ht)
    if at:
        game["away_team_id"] = str(at)
    if bss.get("homeTeam") and "score" in bss["homeTeam"]:
        game["final_home_score"] = int(bss["homeTeam"]["score"])
    if bss.get("awayTeam") and "score" in bss["awayTeam"]:
        game["final_away_score"] = int(bss["awayTeam"]["score"])
    game["final_home_win"] = game["final_home_score"] > game["final_away_score"]
    return game


def build_nba_games(season: str) -> pd.DataFrame:
    sched = warehouse("NBA", season) / "raw" / "nba_stats" / "schedule"
    rows = []
    for name in (
        "leaguegamelog_pre_season.json",
        "leaguegamelog_regular_season.json",
        "leaguegamelog_playin.json",
        "leaguegamelog_playoffs.json",
    ):
        payload = _load_json(sched / name)
        if isinstance(payload, list):
            rows.extend(payload)
    games = _pair_leaguegamelog(rows)
    box_dir = warehouse("NBA", season) / "raw" / "nba_stats" / "boxscore_summary"
    out = []
    for g in games:
        g["season"] = season
        g = enrich_boxscore(g, box_dir / f"{g['game_id']}.json")
        hb, ab = g["home_box"], g["away_box"]
        hp = _possessions_from_box(hb)
        ap = _possessions_from_box(ab)
        g["home_pts"] = int(hb.get("PTS") or g["final_home_score"])
        g["away_pts"] = int(ab.get("PTS") or g["final_away_score"])
        g["home_possessions_est"] = hp
        g["away_possessions_est"] = ap
        g["home_ortg"] = (100.0 * g["home_pts"] / hp) if hp > 0 else None
        g["away_ortg"] = (100.0 * g["away_pts"] / ap) if ap > 0 else None
        g["home_drtg"] = (100.0 * g["away_pts"] / ap) if ap > 0 else None
        g["away_drtg"] = (100.0 * g["home_pts"] / hp) if hp > 0 else None
        g["home_pace"] = (48.0 * hp / (float(hb.get("MIN") or 240) / 5.0)) if hb.get("MIN") else None
        g["away_pace"] = (48.0 * ap / (float(ab.get("MIN") or 240) / 5.0)) if ab.get("MIN") else None
        fga = float(hb.get("FGA") or 0)
        g["home_efg"] = ((float(hb.get("FGM") or 0) + 0.5 * float(hb.get("FG3M") or 0)) / fga) if fga else None
        fga_a = float(ab.get("FGA") or 0)
        g["away_efg"] = ((float(ab.get("FGM") or 0) + 0.5 * float(ab.get("FG3M") or 0)) / fga_a) if fga_a else None
        g["home_tov_rate"] = (float(hb.get("TOV") or 0) / hp) if hp else None
        g["away_tov_rate"] = (float(ab.get("TOV") or 0) / ap) if ap else None
        den_h = float(hb.get("OREB") or 0) + float(ab.get("DREB") or 0)
        den_a = float(ab.get("OREB") or 0) + float(hb.get("DREB") or 0)
        g["home_orb_rate"] = (float(hb.get("OREB") or 0) / den_h) if den_h else None
        g["away_orb_rate"] = (float(ab.get("OREB") or 0) / den_a) if den_a else None
        g["home_ft_rate"] = (float(hb.get("FTA") or 0) / fga) if fga else None
        g["away_ft_rate"] = (float(ab.get("FTA") or 0) / fga_a) if fga_a else None
        g["minutes"] = float(hb.get("MIN") or 240)
        del g["home_box"]
        del g["away_box"]
        out.append(g)
    df = pd.DataFrame(out)
    dest = derived_root("NBA", season) / "games.parquet"
    if not df.empty:
        df.to_parquet(dest, index=False)
    write_json(derived_root("NBA", season) / "games_manifest.json", {"n": int(len(df)), "path": str(dest)})
    return df
