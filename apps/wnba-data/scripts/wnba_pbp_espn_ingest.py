#!/usr/bin/env python3
"""Download ESPN WNBA play-by-play and join it to Kalshi KXWNBAGAME.

Research only. Does not change live FIRST01 / 80/81/83/89. Does not invent
L2 or tip-from-Kalshi-open. Observed ESPN wallclock is stored as-is.

Resumable: existing scoreboard/summary files and COMPLETE manifest rows
are skipped. FAILED rows are retried.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

import pyarrow.parquet as pq

ROOT = Path(
    "/Users/user/Desktop/Momento/Backtesting Suite/Data/WNBA/2025-2026/warehouse"
)
NORM = ROOT / "normalized" / "wnba"
RAW = ROOT / "raw" / "espn"
MANIFEST_PATH = ROOT / "manifests" / "wnba" / "espn_pbp_ingest_manifest.json"
LOG_PATH = ROOT / "manifests" / "wnba" / "espn_pbp_ingest.log"
CROSSWALK_PATH = NORM / "pbp" / "game_crosswalk.json"
PLAYS_DIR = NORM / "pbp" / "plays"
GAMES_PATH = NORM / "games" / "wnba_games.parquet"

SCOREBOARD_URL = "https://site.web.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard"
SUMMARY_URL = "https://site.web.api.espn.com/apis/site/v2/sports/basketball/wnba/summary"
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

# Warehouse codes are mixed (LA vs Los Angeles, LV vs LVA). Canonicalize.
CANON = {
    "ATL": "ATL",
    "CHI": "CHI",
    "CON": "CONN",
    "CONN": "CONN",
    "DAL": "DAL",
    "GS": "GS",
    "GSV": "GS",
    "IND": "IND",
    "LA": "LA",
    "LAS": "LA",
    "LV": "LV",
    "LVA": "LV",
    "MIN": "MIN",
    "NY": "NY",
    "NYL": "NY",
    "PDX": "PDX",
    "PHX": "PHX",
    "POR": "PDX",
    "SEA": "SEA",
    "TOR": "TOR",
    "WAS": "WSH",
    "WSH": "WSH",
    "CLA": "CLA",
    "COL": "COL",
}

NAME_TO_CODE = {
    "atlanta": "ATL",
    "atlanta dream": "ATL",
    "chicago": "CHI",
    "chicago sky": "CHI",
    "connecticut": "CONN",
    "connecticut sun": "CONN",
    "dallas": "DAL",
    "dallas wings": "DAL",
    "golden state": "GS",
    "golden state valkyries": "GS",
    "valkyries": "GS",
    "indiana": "IND",
    "indiana fever": "IND",
    "los angeles": "LA",
    "los angeles sparks": "LA",
    "sparks": "LA",
    "las vegas": "LV",
    "las vegas aces": "LV",
    "aces": "LV",
    "minnesota": "MIN",
    "minnesota lynx": "MIN",
    "lynx": "MIN",
    "new york": "NY",
    "new york liberty": "NY",
    "liberty": "NY",
    "phoenix": "PHX",
    "phoenix mercury": "PHX",
    "mercury": "PHX",
    "portland": "PDX",
    "portland fire": "PDX",
    "fire": "PDX",
    "seattle": "SEA",
    "seattle storm": "SEA",
    "storm": "SEA",
    "toronto": "TOR",
    "toronto tempo": "TOR",
    "tempo": "TOR",
    "washington": "WSH",
    "washington mystics": "WSH",
    "mystics": "WSH",
    "team clark": "CLA",
    "team collier": "COL",
    "team coop": "COO",
    "team spoon": "SPN",
}

TOKEN_CODES = sorted(
    {
        "CONN",
        "PHX",
        "MIN",
        "ATL",
        "IND",
        "SEA",
        "WSH",
        "CHI",
        "DAL",
        "PDX",
        "POR",
        "TOR",
        "CLA",
        "COL",
        "NYL",
        "LVA",
        "GSV",
        "NY",
        "LA",
        "LV",
        "GS",
        "CON",
        "COO",
        "SPN",
    },
    key=len,
    reverse=True,
)


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
    t = str(s).lower()
    out = []
    for ch in t:
        out.append(ch if ch.isalnum() else " ")
    return " ".join("".join(out).split())


def canon_code(raw: str | None) -> str | None:
    if not raw:
        return None
    t = str(raw).strip()
    up = t.upper()
    if up in CANON:
        return CANON[up]
    n = norm_name(t)
    return NAME_TO_CODE.get(n)


def parse_event_codes(event_id: str | None) -> tuple[str | None, str | None]:
    if not event_id or not event_id.startswith("KXWNBAGAME-"):
        return None, None
    body = event_id.removeprefix("KXWNBAGAME-")
    if len(body) < 8:
        return None, None
    pair = body[7:]
    for a in TOKEN_CODES:
        if pair.startswith(a):
            rest = pair[len(a) :]
            for b in TOKEN_CODES:
                if rest == b:
                    return canon_code(a), canon_code(b)
    return None, None


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


def load_games() -> list[dict]:
    t = pq.read_table(GAMES_PATH)
    rows = []
    for i in range(t.num_rows):
        eid = t.column("event_id")[i].as_py()
        home_raw = t.column("home_team_code")[i].as_py()
        away_raw = t.column("away_team_code")[i].as_py()
        home_name = t.column("home_team")[i].as_py()
        away_name = t.column("away_team")[i].as_py()
        away_e, home_e = parse_event_codes(eid)
        home = canon_code(home_raw) or canon_code(home_name) or home_e
        away = canon_code(away_raw) or canon_code(away_name) or away_e
        rows.append(
            {
                "event_id": eid,
                "game_date": t.column("game_date")[i].as_py(),
                "home_team_code": home,
                "away_team_code": away,
                "home_team": home_name or home_raw,
                "away_team": away_name or away_raw,
            }
        )
    by = {r["event_id"]: r for r in rows}
    return list(by.values())


def espn_team_to_kalshi(team: dict) -> str | None:
    abbr = ((team or {}).get("abbreviation") or "").upper()
    if abbr in CANON:
        return CANON[abbr]
    for field in ("shortDisplayName", "displayName", "name", "nickname", "location"):
        code = canon_code((team or {}).get(field))
        if code:
            return code
    return None


def parse_espn_events(payload: dict) -> list[dict]:
    out = []
    for ev in payload.get("events") or []:
        comps = ev.get("competitions") or []
        if not comps:
            continue
        c = comps[0]
        teams = {}
        for t in c.get("competitors") or []:
            side = t.get("homeAway")
            team = t.get("team") or {}
            rec = {
                "home_away": side,
                "espn_abbr": team.get("abbreviation"),
                "espn_name": team.get("displayName"),
                "espn_id": team.get("id"),
                "kalshi_code": espn_team_to_kalshi(team),
            }
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
            }
        )
    return out


def scoreboard_path(yyyymmdd: str) -> Path:
    return RAW / "scoreboard" / f"{yyyymmdd}.json"


def summary_path(espn_id: str) -> Path:
    return RAW / "summary" / f"{espn_id}.json"


def date_window(game_date: str) -> list[str]:
    d = datetime.strptime(game_date, "%Y-%m-%d")
    return [(d + timedelta(days=off)).strftime("%Y%m%d") for off in (-2, -1, 0, 1, 2)]


def espn_et_date(iso: str | None) -> str | None:
    if not iso:
        return None
    t = iso.strip()
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(t)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ET).date().isoformat()


def ensure_scoreboard(yyyymmdd: str, refresh: bool = False) -> dict:
    path = scoreboard_path(yyyymmdd)
    if path.exists() and path.stat().st_size > 20 and not refresh:
        return json.loads(path.read_text())
    url = f"{SCOREBOARD_URL}?dates={yyyymmdd}&limit=100"
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
        raw = fetch(f"{SUMMARY_URL}?event={espn_id}")
        write_bytes_atomic(path, raw)
        time.sleep(SLEEP_S)
        summary = json.loads(raw)
    compact = compact_plays(summary, espn_id)
    write_atomic(PLAYS_DIR / f"{espn_id}.json", compact)
    return compact


def build_crosswalk(games: list[dict], refresh_scoreboards: bool = False) -> list[dict]:
    dates = sorted({d for g in games if g.get("game_date") for d in date_window(g["game_date"])})
    log(f"scoreboard dates {len(dates)} refresh={refresh_scoreboards}")
    espn_games = []
    for i, d in enumerate(dates, 1):
        if i == 1 or i == len(dates) or i % 25 == 0:
            log(f"  scoreboard {i}/{len(dates)} {d}")
        espn_games.extend(parse_espn_events(ensure_scoreboard(d, refresh=refresh_scoreboards)))

    by_key: dict[tuple, list[dict]] = {}
    for eg in espn_games:
        home_k = eg["home"]["kalshi_code"]
        away_k = eg["away"]["kalshi_code"]
        if not home_k or not away_k:
            continue
        key = (eg["espn_date"], home_k, away_k)
        by_key.setdefault(key, []).append(eg)

    rows = []
    for g in games:
        if not g.get("home_team_code") or not g.get("away_team_code") or not g.get("game_date"):
            rows.append(
                {
                    **g,
                    "espn_game_id": None,
                    "match_status": "UNMATCHED",
                    "match_method": "NO_TEAM_CODES",
                    "n_hits": 0,
                }
            )
            continue
        hits = []
        seen = set()
        for d in date_window(g["game_date"]):
            iso = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
            key = (iso, g["home_team_code"], g["away_team_code"])
            for eg in by_key.get(key, []):
                if eg["espn_game_id"] in seen:
                    continue
                seen.add(eg["espn_game_id"])
                hits.append(eg)
        status = "UNMATCHED"
        method = None
        picked = None
        if len(hits) == 1:
            status = "MATCHED"
            method = "DATE_PM2_HOME_AWAY"
            picked = hits[0]
        elif len(hits) > 1:
            et_day = [h for h in hits if espn_et_date(h.get("espn_datetime")) == g["game_date"]]
            if len(et_day) == 1:
                status = "MATCHED"
                method = "ESPN_ET_DATE_HOME_AWAY"
                picked = et_day[0]
            else:
                same_day = [h for h in hits if h["espn_date"] == g["game_date"]]
                if len(same_day) == 1:
                    status = "MATCHED"
                    method = "DATE_EXACT_HOME_AWAY"
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
                    if ranked and (len(ranked) == 1 or ranked[0][0] < ranked[1][0]):
                        status = "MATCHED"
                        method = "DATE_CLOSEST_HOME_AWAY"
                        picked = ranked[0][1]
                    else:
                        status = "AMBIGUOUS"
                        method = "MULTIPLE_ESPN_HITS"
        rows.append(
            {
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
        )
    return rows


def main() -> int:
    RAW.joinpath("scoreboard").mkdir(parents=True, exist_ok=True)
    RAW.joinpath("summary").mkdir(parents=True, exist_ok=True)
    PLAYS_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    games = load_games()
    log(f"kalshi wnba games {len(games)}")
    crosswalk = build_crosswalk(games, refresh_scoreboards="--refresh-scoreboards" in sys.argv)
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
        if prev.get("status") == "COMPLETE" and (PLAYS_DIR / f"{eid}.json").exists():
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
