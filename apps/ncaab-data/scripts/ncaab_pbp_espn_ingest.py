#!/usr/bin/env python3
"""Download ESPN men's CBB play-by-play and join it to Kalshi KXNCAAMBGAME.

Research only. Does not change live FIRST01 / 80/81/83/89. Does not invent
L2 or tip-from-Kalshi-open. Observed ESPN wallclock is stored as-is.

Resumable: existing scoreboard/summary files and COMPLETE manifest rows
are skipped. FAILED rows are retried.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(
    "/Users/user/Desktop/Momento/Backtesting Suite/Data/NCAAB/2025-2026/warehouse"
)
NORM = ROOT / "normalized" / "ncaab"
RAW = ROOT / "raw" / "espn"
MANIFEST_PATH = ROOT / "manifests" / "ncaab" / "espn_pbp_ingest_manifest.json"
LOG_PATH = ROOT / "manifests" / "ncaab" / "espn_pbp_ingest.log"
CROSSWALK_PATH = NORM / "pbp" / "game_crosswalk.json"
PLAYS_DIR = NORM / "pbp" / "plays"
GAMES_PATH = NORM / "games" / "ncaab_games.parquet"

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
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

SLEEP_S = 0.45
TIMEOUT_S = 30
MAX_RETRIES = 4

# Kalshi P5 codes. Identity aliases plus ESPN abbreviations that differ.
P5_CODES = frozenset(
    {
        "ALA",
        "ARIZ",
        "ARK",
        "ASU",
        "AUB",
        "BAY",
        "BC",
        "BYU",
        "CAL",
        "CIN",
        "CLEM",
        "COLO",
        "DUKE",
        "FLA",
        "FSU",
        "GT",
        "HOU",
        "ILL",
        "IND",
        "IOWA",
        "ISU",
        "KSU",
        "KU",
        "LOU",
        "LSU",
        "MD",
        "MIA",
        "MICH",
        "MINN",
        "MISS",
        "MIZZ",
        "MSST",
        "MSU",
        "NCST",
        "ND",
        "NEB",
        "NW",
        "OKLA",
        "OKST",
        "ORE",
        "ORST",
        "OSU",
        "PITT",
        "PSU",
        "PUR",
        "RUTG",
        "SCAR",
        "SMU",
        "STAN",
        "SYR",
        "TCU",
        "TENN",
        "TEX",
        "TTU",
        "TXAM",
        "UCF",
        "UCLA",
        "UGA",
        "UK",
        "UNC",
        "USC",
        "UTAH",
        "UVA",
        "VAN",
        "VT",
        "WAKE",
        "WASH",
        "WIS",
        "WSU",
        "WVU",
    }
)

# ESPN abbreviation → Kalshi code. Identity first; overrides after.
ESPN_ABBR_TO_KALSHI: dict[str, str] = {c: c for c in P5_CODES}
ESPN_ABBR_TO_KALSHI.update(
    {
        "SC": "SCAR",
        "OU": "OKLA",
        "TA&M": "TXAM",
        "TAMU": "TXAM",
        "MIZ": "MIZZ",
        "MSU": "MSU",
        "MICHST": "MSU",
        "PITT": "PITT",
        "NCST": "NCST",
        "NCSU": "NCST",
    }
)

NAME_ALIASES = {
    "pitt": "pittsburgh",
    "nc st": "north carolina st",
    "n carolina": "north carolina",
    "va tech": "virginia tech",
    "georgia tech": "georgia tech",
    "boston coll": "boston college",
    "miami": "miami fl",
    "miami fl": "miami fl",
    "ole miss": "ole miss",
}


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    print(line, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a") as f:
        f.write(line + "\n")


def write_atomic(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str) + "\n")
    tmp.replace(path)


def write_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text())


def norm_name(s: str | None) -> str:
    if not s:
        return ""
    t = str(s).lower().replace("&", " and ")
    out = []
    for ch in t:
        out.append(ch if ch.isalnum() else " ")
    words = "".join(out).split()
    words = ["st" if w == "state" else w for w in words]
    if words[-2:] == ["miami", "fl"]:
        return "miami fl"
    if words[:2] == ["miami"] and "oh" not in words:
        return "miami fl"
    return " ".join(words)


def fetch(url: str) -> bytes:
    last = None
    for attempt in range(1, MAX_RETRIES + 1):
        req = urllib.request.Request(url, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return resp.read()
        except Exception as exc:  # noqa: BLE001
            last = exc
            wait = min(30, 2**attempt)
            log(f"RETRY attempt={attempt} wait={wait}s err={exc} url={url}")
            time.sleep(wait)
    raise RuntimeError(f"fetch failed {url}: {last}")


def load_p5_games() -> list[dict]:
    t = pq.read_table(
        GAMES_PATH,
        columns=[
            "event_id",
            "game_date",
            "home_team_code",
            "away_team_code",
            "home_team",
            "away_team",
        ],
    )
    rows = []
    for i in range(t.num_rows):
        home = t.column("home_team_code")[i].as_py()
        away = t.column("away_team_code")[i].as_py()
        if home not in P5_CODES or away not in P5_CODES:
            continue
        rows.append(
            {
                "event_id": t.column("event_id")[i].as_py(),
                "game_date": t.column("game_date")[i].as_py(),
                "home_team_code": home,
                "away_team_code": away,
                "home_team": t.column("home_team")[i].as_py(),
                "away_team": t.column("away_team")[i].as_py(),
            }
        )
    # Unique event_id
    by = {}
    for r in rows:
        by[r["event_id"]] = r
    return list(by.values())


def kalshi_name_index(games: list[dict]) -> dict[str, str]:
    idx = {}
    for g in games:
        for code, name in (
            (g["home_team_code"], g["home_team"]),
            (g["away_team_code"], g["away_team"]),
        ):
            n = norm_name(name)
            idx[n] = code
            idx[NAME_ALIASES.get(n, n)] = code
            if n.endswith(" st"):
                idx[n[:-3] + " state"] = code
    idx["miami fl"] = "MIA"
    idx["ole miss"] = "MISS"
    idx["pittsburgh"] = "PITT"
    idx["pitt"] = "PITT"
    idx["north carolina st"] = "NCST"
    idx["nc st"] = "NCST"
    return idx


def espn_team_to_kalshi(team: dict, name_idx: dict[str, str]) -> str | None:
    abbr = ((team or {}).get("abbreviation") or "").upper()
    if abbr in ESPN_ABBR_TO_KALSHI:
        return ESPN_ABBR_TO_KALSHI[abbr]
    for field in ("shortDisplayName", "displayName", "name", "nickname"):
        n = norm_name((team or {}).get(field))
        n = NAME_ALIASES.get(n, n)
        if n in name_idx:
            return name_idx[n]
    return None


def parse_espn_events(payload: dict, name_idx: dict[str, str]) -> list[dict]:
    out = []
    for ev in payload.get("events") or []:
        comps = ev.get("competitions") or []
        if not comps:
            continue
        c = comps[0]
        teams = {}
        raw_teams = []
        for t in c.get("competitors") or []:
            side = t.get("homeAway")
            team = t.get("team") or {}
            code = espn_team_to_kalshi(team, name_idx)
            rec = {
                "home_away": side,
                "espn_abbr": team.get("abbreviation"),
                "espn_name": team.get("displayName"),
                "espn_id": team.get("id"),
                "kalshi_code": code,
            }
            raw_teams.append(rec)
            if side in ("home", "away"):
                teams[side] = rec
        if "home" not in teams or "away" not in teams:
            continue
        out.append(
            {
                "espn_game_id": str(ev.get("id") or ""),
                "espn_date": (c.get("date") or ev.get("date") or "")[:10],
                "espn_datetime": c.get("date") or ev.get("date"),
                "home": teams["home"],
                "away": teams["away"],
                "name": ev.get("name"),
                "raw_teams": raw_teams,
            }
        )
    return out


def scoreboard_path(yyyymmdd: str) -> Path:
    return RAW / "scoreboard" / f"{yyyymmdd}.json"


def summary_path(espn_id: str) -> Path:
    return RAW / "summary" / f"{espn_id}.json"


def date_window(game_date: str) -> list[str]:
    """Kalshi calendar date vs ESPN UTC start can slip two days (late tips)."""
    d = datetime.strptime(game_date, "%Y-%m-%d")
    return [(d + timedelta(days=off)).strftime("%Y%m%d") for off in (-2, -1, 0, 1, 2)]


def ensure_scoreboard(yyyymmdd: str, refresh: bool = False) -> dict:
    path = scoreboard_path(yyyymmdd)
    if path.exists() and path.stat().st_size > 20 and not refresh:
        return json.loads(path.read_text())
    url = f"{SCOREBOARD_URL}?dates={yyyymmdd}&limit=300&groups=50"
    raw = fetch(url)
    write_bytes_atomic(path, raw)
    time.sleep(SLEEP_S)
    return json.loads(raw)


def compact_plays(summary: dict, espn_id: str) -> dict:
    header = summary.get("header") or {}
    comps = header.get("competitions") or [{}]
    comp = comps[0] if comps else {}
    home = away = None
    for t in comp.get("competitors") or []:
        team = t.get("team") or {}
        rec = {
            "abbr": team.get("abbreviation"),
            "name": team.get("displayName"),
            "id": team.get("id"),
            "home_away": t.get("homeAway"),
        }
        if t.get("homeAway") == "home":
            home = rec
        elif t.get("homeAway") == "away":
            away = rec
    plays = []
    for p in summary.get("plays") or []:
        period = p.get("period") or {}
        clock = p.get("clock") or {}
        typ = p.get("type") or {}
        plays.append(
            {
                "id": p.get("id"),
                "sequenceNumber": p.get("sequenceNumber"),
                "type_id": typ.get("id"),
                "type_text": typ.get("text"),
                "text": p.get("text"),
                "period": period.get("number"),
                "period_display": period.get("displayValue"),
                "clock": clock.get("displayValue"),
                "wallclock": p.get("wallclock"),
                "homeScore": p.get("homeScore"),
                "awayScore": p.get("awayScore"),
                "scoringPlay": p.get("scoringPlay"),
            }
        )
    return {
        "espn_game_id": espn_id,
        "wallclock_available": bool(summary.get("wallclockAvailable")),
        "competition_date": comp.get("date"),
        "home": home,
        "away": away,
        "n_plays": len(plays),
        "plays": plays,
    }


def ensure_summary(espn_id: str) -> dict:
    path = summary_path(espn_id)
    if path.exists() and path.stat().st_size > 20:
        summary = json.loads(path.read_text())
    else:
        url = f"{SUMMARY_URL}?event={espn_id}"
        raw = fetch(url)
        write_bytes_atomic(path, raw)
        time.sleep(SLEEP_S)
        summary = json.loads(raw)
    compact = compact_plays(summary, espn_id)
    write_atomic(PLAYS_DIR / f"{espn_id}.json", compact)
    return compact


def build_crosswalk(
    games: list[dict], name_idx: dict[str, str], refresh_scoreboards: bool = False
) -> list[dict]:
    dates = sorted({d for g in games for d in date_window(g["game_date"])})
    log(f"scoreboard dates {len(dates)} refresh={refresh_scoreboards}")
    espn_games = []
    for i, d in enumerate(dates, 1):
        if i == 1 or i == len(dates) or i % 20 == 0:
            log(f"  scoreboard {i}/{len(dates)} {d}")
        payload = ensure_scoreboard(d, refresh=refresh_scoreboards)
        espn_games.extend(parse_espn_events(payload, name_idx))

    by_key: dict[tuple, list[dict]] = {}
    for eg in espn_games:
        home_k = eg["home"]["kalshi_code"]
        away_k = eg["away"]["kalshi_code"]
        if not home_k or not away_k:
            continue
        if home_k not in P5_CODES or away_k not in P5_CODES:
            continue
        key = (eg["espn_date"], tuple(sorted((home_k, away_k))))
        by_key.setdefault(key, []).append(eg)

    rows = []
    for g in games:
        keys = []
        for d in date_window(g["game_date"]):
            iso = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
            keys.append((iso, tuple(sorted((g["home_team_code"], g["away_team_code"])))))
        hits = []
        seen = set()
        for key in keys:
            for eg in by_key.get(key, []):
                eid = eg["espn_game_id"]
                if eid in seen:
                    continue
                seen.add(eid)
                hits.append(eg)
        status = "UNMATCHED"
        method = None
        picked = None
        if len(hits) == 1:
            status = "MATCHED"
            method = "DATE_PM2_TEAM_PAIR"
            picked = hits[0]
        elif len(hits) > 1:
            same_day = [h for h in hits if h["espn_date"] == g["game_date"]]
            if len(same_day) == 1:
                status = "MATCHED"
                method = "DATE_EXACT_TEAM_PAIR"
                picked = same_day[0]
            else:
                kd = datetime.strptime(g["game_date"], "%Y-%m-%d")
                ranked = []
                for h in hits:
                    try:
                        ed = datetime.strptime(h["espn_date"], "%Y-%m-%d")
                    except ValueError:
                        continue
                    ranked.append((abs((ed - kd).days), h))
                ranked.sort(key=lambda x: x[0])
                if ranked and (
                    len(ranked) == 1 or ranked[0][0] < ranked[1][0]
                ):
                    status = "MATCHED"
                    method = "DATE_CLOSEST_TEAM_PAIR"
                    picked = ranked[0][1]
                else:
                    status = "AMBIGUOUS"
                    method = "MULTIPLE_ESPN_HITS"
        row = {
            "event_id": g["event_id"],
            "game_date": g["game_date"],
            "home_team_code": g["home_team_code"],
            "away_team_code": g["away_team_code"],
            "home_team": g["home_team"],
            "away_team": g["away_team"],
            "espn_game_id": None if picked is None else picked["espn_game_id"],
            "espn_date": None if picked is None else picked["espn_date"],
            "espn_datetime": None if picked is None else picked["espn_datetime"],
            "espn_home_abbr": None if picked is None else picked["home"]["espn_abbr"],
            "espn_away_abbr": None if picked is None else picked["away"]["espn_abbr"],
            "match_status": status,
            "match_method": method,
            "n_hits": len(hits),
        }
        rows.append(row)
    return rows


def main() -> int:
    RAW.joinpath("scoreboard").mkdir(parents=True, exist_ok=True)
    RAW.joinpath("summary").mkdir(parents=True, exist_ok=True)
    PLAYS_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    games = load_p5_games()
    log(f"p5 vs p5 kalshi games {len(games)}")
    name_idx = kalshi_name_index(games)
    refresh_sb = "--refresh-scoreboards" in sys.argv
    crosswalk = build_crosswalk(games, name_idx, refresh_scoreboards=refresh_sb)
    write_atomic(CROSSWALK_PATH, crosswalk)
    n_m = sum(1 for r in crosswalk if r["match_status"] == "MATCHED")
    n_u = sum(1 for r in crosswalk if r["match_status"] == "UNMATCHED")
    n_a = sum(1 for r in crosswalk if r["match_status"] == "AMBIGUOUS")
    log(f"crosswalk MATCHED={n_m} UNMATCHED={n_u} AMBIGUOUS={n_a}")
    for r in crosswalk:
        if r["match_status"] != "MATCHED":
            log(
                f"  {r['match_status']} {r['game_date']} {r['away_team_code']}@{r['home_team_code']} {r['event_id']}"
            )

    manifest = load_json(MANIFEST_PATH, {"games": {}})
    wanted = [r for r in crosswalk if r["match_status"] == "MATCHED" and r["espn_game_id"]]
    log(f"summaries wanted {len(wanted)}")
    ok = fail = skip = 0
    for i, r in enumerate(wanted, 1):
        eid = r["espn_game_id"]
        prev = (manifest.get("games") or {}).get(eid) or {}
        plays_path = PLAYS_DIR / f"{eid}.json"
        if prev.get("status") == "COMPLETE" and plays_path.exists():
            skip += 1
            continue
        if i == 1 or i == len(wanted) or i % 25 == 0:
            log(f"  summary {i}/{len(wanted)} {eid}")
        try:
            compact = ensure_summary(eid)
            manifest.setdefault("games", {})[eid] = {
                "status": "COMPLETE",
                "event_id": r["event_id"],
                "n_plays": compact.get("n_plays"),
                "wallclock_available": compact.get("wallclock_available"),
                "finished_utc": datetime.now(timezone.utc).isoformat(),
            }
            ok += 1
        except Exception as exc:  # noqa: BLE001
            manifest.setdefault("games", {})[eid] = {
                "status": "FAILED",
                "event_id": r["event_id"],
                "error": str(exc),
            }
            fail += 1
            log(f"FAIL summary {eid} {exc}")
        if i % 20 == 0:
            write_atomic(MANIFEST_PATH, manifest)
    write_atomic(MANIFEST_PATH, manifest)
    log(f"done summaries ok={ok} skip={skip} fail={fail}")
    return 0 if fail == 0 and n_u == 0 and n_a == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
