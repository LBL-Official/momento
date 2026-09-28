"""ESPN men's CBB ingest for 2024–25: D1 scoreboards + P5-vs-P5 PBP only.

Does not fabricate possessions. Does not require Kalshi games parquet.
"""

from __future__ import annotations

import json
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from terminal_efficiency.constants import ESPN_ABBR_TO_P5, P5_CODES
from terminal_efficiency.paths import warehouse
from terminal_efficiency.provenance import data_gap, record_provenance, write_json

SCOREBOARD_URL = (
    "https://site.web.api.espn.com/apis/site/v2/sports/basketball/"
    "mens-college-basketball/scoreboard"
)
SUMMARY_URL = (
    "https://site.web.api.espn.com/apis/site/v2/sports/basketball/"
    "mens-college-basketball/summary"
)
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
SLEEP_S = 0.45
TIMEOUT_S = 30


def _season_dates(season: str) -> tuple[date, date]:
    start_year = int(season.split("-")[0])
    return date(start_year, 11, 4), date(start_year + 1, 4, 8)


def _paths(season: str) -> dict[str, Path]:
    root = warehouse("NCAAB", season)
    raw = root / "raw" / "espn"
    return {
        "root": root,
        "scoreboard": raw / "scoreboard",
        "summary": raw / "summary",
        "games": root / "normalized" / "ncaab" / "games" / "ncaab_games.json",
        "plays": root / "normalized" / "ncaab" / "pbp" / "plays",
        "manifest": root / "manifests" / "ncaab" / "terminal_efficiency_espn_ingest.json",
    }


def _fetch(url: str) -> bytes:
    last = None
    for attempt in range(1, 4):
        req = urllib.request.Request(url, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return resp.read()
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(min(20, 2**attempt))
    raise RuntimeError(f"fetch failed {url}: {last}")


def _p5_code(team: dict) -> str | None:
    abbr = str((team or {}).get("abbreviation") or "").upper()
    return ESPN_ABBR_TO_P5.get(abbr)


def parse_scoreboard(payload: dict) -> list[dict]:
    out = []
    for ev in payload.get("events") or []:
        comps = ev.get("competitions") or []
        if not comps:
            continue
        c = comps[0]
        sides = {}
        for t in c.get("competitors") or []:
            side = t.get("homeAway")
            team = t.get("team") or {}
            sides[side] = {
                "espn_id": team.get("id"),
                "abbr": team.get("abbreviation"),
                "name": team.get("displayName"),
                "p5_code": _p5_code(team),
                "score": t.get("score"),
                "winner": t.get("winner"),
            }
        if "home" not in sides or "away" not in sides:
            continue
        home, away = sides["home"], sides["away"]
        p5_vs_p5 = home["p5_code"] in P5_CODES and away["p5_code"] in P5_CODES
        out.append(
            {
                "espn_game_id": str(ev.get("id") or ""),
                "game_date": (c.get("date") or ev.get("date") or "")[:10],
                "scheduled_start": c.get("date") or ev.get("date") or "",
                "home_team": home["name"],
                "away_team": away["name"],
                "home_team_id": home["p5_code"] or home["abbr"] or home["espn_id"],
                "away_team_id": away["p5_code"] or away["abbr"] or away["espn_id"],
                "home_espn_id": home["espn_id"],
                "away_espn_id": away["espn_id"],
                "final_home_score": _int_or_none(home["score"]),
                "final_away_score": _int_or_none(away["score"]),
                "home_win": _win_flag(home, away),
                "p5_vs_p5": p5_vs_p5,
                "status": (c.get("status") or {}).get("type", {}).get("name"),
            }
        )
    return out


def _int_or_none(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _win_flag(home: dict, away: dict) -> bool | None:
    hs, aws = _int_or_none(home.get("score")), _int_or_none(away.get("score"))
    if hs is None or aws is None:
        return None
    if hs == aws:
        return None
    return hs > aws


def ingest_ncaab_espn(
    season: str,
    *,
    max_days: int | None = None,
    fetch_pbp: bool = True,
    sleep_s: float = SLEEP_S,
) -> dict:
    paths = _paths(season)
    for key in ("scoreboard", "summary", "plays"):
        paths[key].mkdir(parents=True, exist_ok=True)

    start, end = _season_dates(season)
    days = []
    d = start
    while d <= end:
        days.append(d)
        d += timedelta(days=1)
    if max_days is not None:
        days = days[: max(0, max_days)]

    games: dict[str, dict] = {}
    errors = []
    pbp_ok = 0
    pbp_skip = 0

    for day in days:
        ds = day.strftime("%Y%m%d")
        dest = paths["scoreboard"] / f"{ds}.json"
        try:
            if dest.exists():
                payload = json.loads(dest.read_text())
            else:
                url = f"{SCOREBOARD_URL}?dates={ds}&groups=50&limit=300"
                raw = _fetch(url)
                dest.write_bytes(raw)
                payload = json.loads(raw.decode())
                time.sleep(sleep_s)
            for g in parse_scoreboard(payload):
                if g["espn_game_id"]:
                    games[g["espn_game_id"]] = g
        except Exception as exc:  # noqa: BLE001
            errors.append({"date": ds, "error": str(exc)})

    if fetch_pbp:
        for gid, g in games.items():
            if not g.get("p5_vs_p5"):
                pbp_skip += 1
                continue
            play_path = paths["plays"] / f"{gid}.json"
            if play_path.exists():
                pbp_ok += 1
                continue
            summary_path = paths["summary"] / f"{gid}.json"
            try:
                if not summary_path.exists():
                    raw = _fetch(f"{SUMMARY_URL}?event={gid}")
                    summary_path.write_bytes(raw)
                    time.sleep(sleep_s)
                payload = json.loads(summary_path.read_text())
                plays = payload.get("plays")
                if isinstance(plays, dict):
                    plays = plays.get("items") or []
                elif not isinstance(plays, list):
                    plays = []
                if not plays:
                    # some summaries nest under articles; leave empty rather than invent
                    write_json(play_path, {"espn_game_id": gid, "plays": [], "status": "EMPTY"})
                    continue
                write_json(play_path, {"espn_game_id": gid, "plays": plays, "status": "OBSERVED"})
                pbp_ok += 1
            except Exception as exc:  # noqa: BLE001
                errors.append({"espn_game_id": gid, "error": str(exc)})

    game_list = list(games.values())
    write_json(paths["games"], game_list)
    p5 = sum(1 for g in game_list if g.get("p5_vs_p5"))
    extra = {
        "n_scoreboard_days": len(days),
        "n_games": len(game_list),
        "n_p5_vs_p5": p5,
        "n_pbp_written": pbp_ok,
        "n_non_p5_no_pbp": pbp_skip,
        "n_errors": len(errors),
        "errors_head": errors[:20],
        "status": "AVAILABLE" if game_list else "MISSING",
    }
    if not game_list:
        extra["data_gap"] = data_gap(
            source="ESPN scoreboard",
            required_field="D1 schedule/finals",
            why="zero games parsed" + (f"; first error {errors[0]}" if errors else ""),
            future_source="retry ingest_ncaab_espn",
            impact="NCAAB Dataset A/B cannot be built",
        )
    record_provenance(
        paths["manifest"],
        source="espn_mens_cbb",
        action="scoreboard+p5_pbp",
        season=season,
        league="NCAAB",
        extra=extra,
    )
    return extra
