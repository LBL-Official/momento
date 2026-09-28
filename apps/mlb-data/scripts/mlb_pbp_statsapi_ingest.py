#!/usr/bin/env python3
"""Download MLB StatsAPI live-feed PBP into the KXMLBGAME warehouse.

Research only. Does not submit orders. Does not invent gamePk.

Reuses Foundation/Ingest landing envelopes when present. Fetches only
missing Final games from https://statsapi.mlb.com. Historical L2 is
not available and is not fabricated.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path("/Users/user/Desktop/Momento/Backtesting Suite/Data/MLB/2025-2026/warehouse")
RAW = ROOT / "raw" / "mlb_statsapi"
PBP_DIR = RAW / "pbp"
SCHED_DIR = RAW / "schedule"
NORM = ROOT / "normalized" / "mlb" / "pbp"
MANIFEST = ROOT / "manifests" / "mlb" / "pbp_ingest_manifest.json"
FOUNDATION = Path(
    "/Users/user/Desktop/Momento/Backtesting Suite/Foundation/Ingest/landing/mlb_statsapi"
)
PAIRS = Path(
    "/Users/user/Desktop/Momento/Backtesting Suite/Foundation/Ingest/runs/"
    "rejoin-20260827T114739Z/game_market_pairs.json"
)

STATSAPI = "https://statsapi.mlb.com"
UA = "MomentoResearch-MLB-PBP/1.0 (historical; not live trading)"
WINDOW_START = "2025-04-16"
WINDOW_END = "2026-09-04"
SLEEP_S = 0.15
ALIASES = {"AZ": "ARI", "ARI": "AZ"}


def log(msg: str) -> None:
    print(f"{datetime.now(timezone.utc).isoformat()} {msg}", flush=True)


def http_get(url: str, attempts: int = 4) -> bytes:
    last: Exception | None = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            time.sleep(1.5 * (i + 1))
    raise last  # type: ignore[misc]


def daterange(start: str, end: str, step_days: int = 14):
    cur = datetime.strptime(start, "%Y-%m-%d")
    last = datetime.strptime(end, "%Y-%m-%d")
    while cur <= last:
        chunk_end = min(cur + timedelta(days=step_days - 1), last)
        yield cur.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")
        cur = chunk_end + timedelta(days=1)


def kalshi_event_team_suffix(event_ticker: str) -> str | None:
    rest = event_ticker.removeprefix("KXMLBGAME-")
    if len(rest) < 7:
        return None
    after = rest[7:]
    teams = after[4:] if len(after) >= 4 and after[:4].isdigit() else after
    return teams.upper() if teams else None


def kalshi_event_team_and_game(event_ticker: str) -> tuple[str, int] | None:
    suffix = kalshi_event_team_suffix(event_ticker)
    if not suffix:
        return None
    if len(suffix) >= 6 and suffix[-2] == "G" and suffix[-1].isdigit() and suffix[:-2].isalpha():
        return suffix[:-2], int(suffix[-1])
    if suffix[-1].isdigit() and suffix[:-1].isalpha() and len(suffix[:-1]) >= 4:
        return suffix[:-1], int(suffix[-1])
    if suffix.isalpha():
        return suffix, 1
    return None


def abbr_variants(abbr: str) -> list[str]:
    u = abbr.upper()
    out = [u]
    if u in ALIASES:
        out.append(ALIASES[u])
    return sorted(set(out))


def official_concats(away: str, home: str) -> set[str]:
    out = set()
    for a in abbr_variants(away):
        for h in abbr_variants(home):
            out.add(f"{a}{h}")
            out.add(f"{h}{a}")
    return out


def existing_foundation() -> dict[str, Path]:
    found = {}
    for path in FOUNDATION.glob("date=*/gamePk=*.envelope.json"):
        pk = path.name.removeprefix("gamePk=").removesuffix(".envelope.json")
        found[pk] = path
    return found


def warehouse_pbp_path(date: str, game_pk: str) -> Path:
    return PBP_DIR / f"date={date}" / f"gamePk={game_pk}.json"


def fetch_schedule(start: str, end: str) -> list[dict]:
    rows = []
    seen = set()
    for a, b in daterange(start, end, 14):
        url = (
            f"{STATSAPI}/api/v1/schedule?sportId=1&startDate={a}&endDate={b}&hydrate=team"
        )
        body = json.loads(http_get(url))
        for block in body.get("dates") or []:
            date = block.get("date")
            for g in block.get("games") or []:
                pk = g.get("gamePk")
                if pk is None:
                    continue
                key = str(pk)
                if key in seen:
                    continue
                seen.add(key)
                home = ((g.get("teams") or {}).get("home") or {}).get("team") or {}
                away = ((g.get("teams") or {}).get("away") or {}).get("team") or {}
                rows.append(
                    {
                        "game_pk": key,
                        "official_date": date,
                        "status": ((g.get("status") or {}).get("detailedState") or ""),
                        "home_abbreviation": home.get("abbreviation") or "",
                        "away_abbreviation": away.get("abbreviation") or "",
                        "game_number": int(g.get("gameNumber") or 1),
                        "game_type": g.get("gameType") or "",
                    }
                )
        time.sleep(SLEEP_S)
    return rows


def fetch_live(game_pk: str) -> dict:
    url = f"{STATSAPI}/api/v1.1/game/{game_pk}/feed/live"
    return json.loads(http_get(url))


def wrap_envelope(payload: dict, game_pk: str) -> dict:
    return {
        "envelope_version": "1.0.0",
        "fixture_kind": "statsapi_live_feed",
        "source": "mlb_statsapi",
        "source_game_id": str(game_pk),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }


def match_event(game: dict, event_tickers: list[str]) -> tuple[str, list[str]]:
    concats = official_concats(game["away_abbreviation"], game["home_abbreviation"])
    want = max(1, int(game.get("game_number") or 1))
    hits = []
    for et in event_tickers:
        parsed = kalshi_event_team_and_game(et)
        if not parsed:
            continue
        teams, n = parsed
        if n == want and teams in concats:
            hits.append(et)
    hits = sorted(set(hits))
    if len(hits) == 1:
        return "MAPPED", hits
    if len(hits) > 1:
        return "AMBIGUOUS", hits
    return "UNMATCHED", hits


def load_pairs() -> dict[str, str]:
    """event_ticker -> game_pk from the frozen Foundation rejoin. No invented pk."""
    if not PAIRS.exists():
        return {}
    out = {}
    for row in json.loads(PAIRS.read_text()):
        if row.get("mapping") != "MAPPED":
            continue
        et = row.get("event_ticker")
        pk = row.get("game_pk")
        if et and pk:
            out[et] = str(pk)
    return out


def main() -> int:
    for d in (PBP_DIR, SCHED_DIR, NORM, MANIFEST.parent):
        d.mkdir(parents=True, exist_ok=True)

    log(f"listing Foundation envelopes under {FOUNDATION}")
    landed = existing_foundation()
    log(f"foundation envelopes={len(landed)}")

    log(f"fetching StatsAPI schedule {WINDOW_START}..{WINDOW_END}")
    games = fetch_schedule(WINDOW_START, WINDOW_END)
    (SCHED_DIR / f"schedule_{WINDOW_START}_{WINDOW_END}.json").write_text(
        json.dumps(games, indent=2) + "\n"
    )
    log(f"schedule games={len(games)}")

    downloaded = 0
    reused = 0
    skipped_not_final = 0
    failed = []
    index = []
    for i, g in enumerate(games, 1):
        pk = g["game_pk"]
        date = g["official_date"]
        dest = warehouse_pbp_path(date, pk)
        src = None
        if dest.exists():
            src = dest
            reused += 1
        elif pk in landed:
            src = landed[pk]
            reused += 1
        elif (g.get("status") or "").lower() == "final":
            try:
                payload = fetch_live(pk)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(json.dumps(wrap_envelope(payload, pk)) + "\n")
                src = dest
                downloaded += 1
                time.sleep(SLEEP_S)
            except Exception as exc:  # noqa: BLE001 — record and continue
                failed.append({"game_pk": pk, "error": str(exc)})
                log(f"FAIL gamePk={pk} {exc}")
        else:
            skipped_not_final += 1
        if i == 1 or i % 200 == 0 or i == len(games):
            log(
                f"progress {i}/{len(games)} downloaded={downloaded} "
                f"reused={reused} not_final={skipped_not_final} failed={len(failed)}"
            )
        index.append({**g, "pbp_path": str(src) if src else None, "has_pbp": src is not None})

    (NORM / "pbp_index.json").write_text(json.dumps(index) + "\n")

    # Crosswalk: frozen Foundation pairs first; unique concat for leftover Final games.
    frozen = load_pairs()
    games_by_date: dict[str, list[dict]] = {}
    for g in index:
        games_by_date.setdefault(g["official_date"], []).append(g)

    # Kalshi event tickers from warehouse games parquet if present, else pairs.
    event_by_date: dict[str, list[str]] = {}
    games_pq = ROOT / "normalized" / "mlb" / "games" / "mlb_games.parquet"
    if games_pq.exists():
        import pyarrow.parquet as pq

        t = pq.read_table(games_pq, columns=["event_ticker", "game_date"])
        for i in range(t.num_rows):
            et = t.column("event_ticker")[i].as_py()
            gd = t.column("game_date")[i].as_py()
            if et and gd:
                event_by_date.setdefault(str(gd), []).append(et)

    if PAIRS.exists():
        for row in json.loads(PAIRS.read_text()):
            et = row.get("event_ticker")
            d = row.get("official_date")
            if et and d:
                event_by_date.setdefault(d, []).append(et)

    by_pk = {g["game_pk"]: g for g in index}
    crosswalk = []
    mapped_events = set(frozen)
    for et, pk in frozen.items():
        g = by_pk.get(pk)
        crosswalk.append(
            {
                "event_ticker": et,
                "game_pk": pk,
                "official_date": (g or {}).get("official_date"),
                "mapping": "MAPPED",
                "method": "foundation_rejoin",
                "has_pbp": bool(g and g.get("has_pbp")),
                "pbp_path": (g or {}).get("pbp_path"),
                "home_abbreviation": (g or {}).get("home_abbreviation"),
                "away_abbreviation": (g or {}).get("away_abbreviation"),
            }
        )

    new_mapped = 0
    ambiguous = 0
    for date, day_games in games_by_date.items():
        taken_pk = {r["game_pk"] for r in crosswalk}
        for g in day_games:
            if g["game_pk"] in taken_pk:
                continue
            pool = sorted(set(event_by_date.get(date, [])))
            status, hits = match_event(g, pool)
            if status == "MAPPED" and hits[0] not in mapped_events:
                mapped_events.add(hits[0])
                new_mapped += 1
                crosswalk.append(
                    {
                        "event_ticker": hits[0],
                        "game_pk": g["game_pk"],
                        "official_date": date,
                        "mapping": "MAPPED",
                        "method": "unique_abbr_concat",
                        "has_pbp": g.get("has_pbp"),
                        "pbp_path": g.get("pbp_path"),
                        "home_abbreviation": g.get("home_abbreviation"),
                        "away_abbreviation": g.get("away_abbreviation"),
                    }
                )
            elif status == "AMBIGUOUS":
                ambiguous += 1
                crosswalk.append(
                    {
                        "event_ticker": hits[0] if hits else None,
                        "game_pk": g["game_pk"],
                        "official_date": date,
                        "mapping": "AMBIGUOUS",
                        "method": "unique_abbr_concat",
                        "has_pbp": g.get("has_pbp"),
                        "pbp_path": g.get("pbp_path"),
                        "candidates": hits,
                    }
                )

    (NORM / "game_crosswalk.json").write_text(json.dumps(crosswalk) + "\n")
    summary = {
        "written_utc": datetime.now(timezone.utc).isoformat(),
        "window": [WINDOW_START, WINDOW_END],
        "schedule_games": len(games),
        "foundation_reused": len(landed),
        "downloaded": downloaded,
        "reused": reused,
        "skipped_not_final": skipped_not_final,
        "failed": failed,
        "crosswalk_rows": len(crosswalk),
        "frozen_mapped_events": len(frozen),
        "new_mapped_events": new_mapped,
        "ambiguous": ambiguous,
        "has_pbp": sum(1 for r in index if r.get("has_pbp")),
        "live_trading_changed": False,
    }
    MANIFEST.write_text(json.dumps(summary, indent=2) + "\n")
    log(json.dumps(summary, indent=2))
    return 0 if not failed else 1


def _self_test() -> None:
    assert kalshi_event_team_and_game("KXMLBGAME-25APR18ATHMIL2") == ("ATHMIL", 2)
    assert kalshi_event_team_and_game("KXMLBGAME-25AUG18MILCHCG2") == ("MILCHC", 2)
    assert kalshi_event_team_and_game("KXMLBGAME-26APR041310STLDET") == ("STLDET", 1)
    assert kalshi_event_team_and_game("KXMLBGAME-25SEP28HOULAA") == ("HOULAA", 1)
    st, hits = match_event(
        {
            "away_abbreviation": "AZ",
            "home_abbreviation": "SD",
            "game_number": 1,
        },
        ["KXMLBGAME-25SEP28AZSD", "KXMLBGAME-25SEP28HOULAA"],
    )
    assert st == "MAPPED" and hits == ["KXMLBGAME-25SEP28AZSD"]
    st, hits = match_event(
        {
            "away_abbreviation": "ATH",
            "home_abbreviation": "MIL",
            "game_number": 1,
        },
        ["KXMLBGAME-25APR18ATHMIL2"],
    )
    assert st == "UNMATCHED" and hits == []


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="StatsAPI PBP → KXMLBGAME warehouse + identity crosswalk.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--window-start", default=WINDOW_START, help="YYYY-MM-DD inclusive")
    parser.add_argument(
        "--window-end",
        default=None,
        help="YYYY-MM-DD inclusive. Default: UTC today. Does not invent gamePk.",
    )
    args = parser.parse_args()
    if args.self_test:
        _self_test()
        print("ok")
        raise SystemExit(0)
    globals()["WINDOW_START"] = args.window_start
    globals()["WINDOW_END"] = args.window_end or datetime.now(timezone.utc).date().isoformat()
    raise SystemExit(main())
