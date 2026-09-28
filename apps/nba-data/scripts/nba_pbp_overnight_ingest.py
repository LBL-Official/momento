#!/usr/bin/env python3
"""Overnight lossless NBA play-by-play ingest for Kalshi KXNBAGAME 2025-26.

Research only. Does not change live trading. Does not invent L2.

PlayByPlayV3 is the primary lossless action stream (period + game clock).
PlayByPlayV2 is empty for 2025-26. BoxScoreSummaryV3 stores observed
gameTimeUTC tip. Per-play wall clock (timeActual) is not on V3; it lives
on the live CDN feed and is downloaded separately by
nba_pbp_live_timeactual_ingest.py. Never reconstruct timeActual from
tip + game clock. This script does not overwrite pbp_live.

Resumable: existing pbp_v3 JSON or COMPLETE manifest entries are skipped.
FAILED games are retried on the next launch.
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

DATA_ROOT = Path("/Users/user/Desktop/Momento/Backtesting Suite/Data")
ROOT = DATA_ROOT / "NBA" / "2025-2026" / "warehouse"
NORM = ROOT / "normalized" / "nba"
RAW = ROOT / "raw" / "nba_stats"
MANIFEST_PATH = ROOT / "manifests" / "nba" / "pbp_ingest_manifest.json"
LOG_PATH = ROOT / "manifests" / "nba" / "pbp_ingest.log"
PID_PATH = ROOT / "manifests" / "nba" / "pbp_ingest.pid"
STATUS_PATH = ROOT / "manifests" / "nba" / "pbp_ingest_status.json"
STATS_SEASON = "2025-26"
WAREHOUSE_SEASON = "2025-2026"

SLEEP_S = 0.45
TIMEOUT_S = 20
MAX_RETRIES = 4
CONSEC_FAIL_COOLDOWN_S = 45
CONSEC_FAIL_TRIGGER = 3

SEASON_TYPES = ("Pre Season", "Regular Season", "PlayIn", "Playoffs")


def configure(warehouse_season: str, stats_season: str) -> None:
    global ROOT, NORM, RAW, MANIFEST_PATH, LOG_PATH, PID_PATH, STATUS_PATH
    global STATS_SEASON, WAREHOUSE_SEASON
    WAREHOUSE_SEASON = warehouse_season
    STATS_SEASON = stats_season
    ROOT = DATA_ROOT / "NBA" / warehouse_season / "warehouse"
    NORM = ROOT / "normalized" / "nba"
    RAW = ROOT / "raw" / "nba_stats"
    MANIFEST_PATH = ROOT / "manifests" / "nba" / "pbp_ingest_manifest.json"
    LOG_PATH = ROOT / "manifests" / "nba" / "pbp_ingest.log"
    PID_PATH = ROOT / "manifests" / "nba" / "pbp_ingest.pid"
    STATUS_PATH = ROOT / "manifests" / "nba" / "pbp_ingest_status.json"
    for p in (RAW / "pbp_v3", RAW / "boxscore_summary", RAW / "schedule", MANIFEST_PATH.parent):
        p.mkdir(parents=True, exist_ok=True)


def stats_season_from_label(label: str) -> str:
    t = label.strip()
    if len(t) == 9 and t[4] == "-":
        return f"{t[:4]}-{t[-2:]}"
    return t


def os_env_season() -> str:
    return __import__("os").environ.get("NBA_PBP_WAREHOUSE_SEASON", "2025-2026")


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    print(line, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a") as f:
        f.write(line + "\n")


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open() as f:
        return json.load(f)


def write_atomic(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str))
    tmp.replace(path)


def write_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def parse_nba_date(raw) -> str | None:
    if raw is None:
        return None
    s = str(raw)[:10]
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return s
    return None


def load_kalshi_games():
    path = NORM / "games" / "nba_games.parquet"
    if not path.exists():
        log(f"no Kalshi games parquet at {path}; targeting full NBA schedule")
        return []
    import pyarrow.parquet as pq

    t = pq.read_table(path)
    rows = []
    for i in range(t.num_rows):
        rows.append({n: t.column(n)[i].as_py() for n in t.column_names})
    return rows


def fetch_league_game_log(season_type: str) -> list[dict]:
    from nba_api.stats.endpoints import leaguegamelog

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = leaguegamelog.LeagueGameLog(
                season=STATS_SEASON,
                season_type_all_star=season_type,
                timeout=TIMEOUT_S,
            )
            df = resp.get_data_frames()[0]
            return df.to_dict(orient="records")
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            wait = min(30, 2**attempt)
            log(
                f"RETRY leaguegamelog {STATS_SEASON} {season_type} "
                f"attempt={attempt} wait={wait}s err={exc}"
            )
            time.sleep(wait)
    raise RuntimeError(f"leaguegamelog failed for {STATS_SEASON} {season_type}: {last_err}")


def unique_nba_games(rows: list[dict]) -> dict[str, dict]:
    out = {}
    for r in rows:
        gid = str(r.get("GAME_ID") or "").zfill(10)
        if not gid or gid == "0000000000":
            continue
        team = str(r.get("TEAM_ABBREVIATION") or "").upper()
        matchup = str(r.get("MATCHUP") or "")
        date = parse_nba_date(r.get("GAME_DATE"))
        rec = out.setdefault(
            gid,
            {
                "nba_game_id": gid,
                "game_date": date,
                "teams": set(),
                "matchup": matchup,
                "season_type": None,
            },
        )
        if team:
            rec["teams"].add(team)
        if date and not rec["game_date"]:
            rec["game_date"] = date
        if matchup:
            rec["matchup"] = matchup
    for rec in out.values():
        rec["teams"] = sorted(rec["teams"])
    return out


def build_crosswalk(kalshi_games, nba_by_id: dict[str, dict]) -> list[dict]:
    by_key = {}
    ambiguous = set()
    for rec in nba_by_id.values():
        teams = tuple(sorted(rec["teams"]))
        if len(teams) != 2 or not rec["game_date"]:
            continue
        key = (rec["game_date"], teams)
        if key in by_key:
            ambiguous.add(key)
        by_key[key] = rec

    rows = []
    used = set()
    for g in kalshi_games:
        home = (g.get("home_team_code") or "").upper()
        away = (g.get("away_team_code") or "").upper()
        date = g.get("game_date")
        key = (date, tuple(sorted([home, away])))
        nba = None if key in ambiguous else by_key.get(key)
        status = "MATCHED"
        if key in ambiguous:
            status = "AMBIGUOUS"
        elif nba is None:
            status = "UNMATCHED"
        if nba:
            used.add(nba["nba_game_id"])
        rows.append(
            {
                "event_id": g.get("event_id"),
                "event_ticker": g.get("event_ticker"),
                "game_date": date,
                "season_phase": g.get("season_phase"),
                "home_team_code": home,
                "away_team_code": away,
                "scheduled_start": g.get("scheduled_start"),
                "nba_game_id": None if nba is None else nba["nba_game_id"],
                "nba_matchup": None if nba is None else nba.get("matchup"),
                "match_status": status,
                "match_method": "game_date+team_pair" if status == "MATCHED" else status,
            }
        )
    unmatched_nba = [
        {
            "nba_game_id": gid,
            "game_date": rec.get("game_date"),
            "teams": rec.get("teams"),
            "matchup": rec.get("matchup"),
        }
        for gid, rec in nba_by_id.items()
        if gid not in used
    ]
    return rows, unmatched_nba


def fetch_json(endpoint_cls, game_id: str, label: str) -> dict:
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = endpoint_cls(game_id=game_id, timeout=TIMEOUT_S)
            data = resp.get_dict()
            if not isinstance(data, dict) or not data:
                raise RuntimeError("empty dict")
            return data
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            wait = min(25, 1.5**attempt)
            log(f"RETRY {label} {game_id} attempt={attempt} wait={wait:.1f}s err={exc}")
            time.sleep(wait)
    raise RuntimeError(f"{label} failed {game_id}: {last_err}")


def fetch_pbp_v3(game_id: str) -> dict:
    from nba_api.stats.endpoints import playbyplayv3

    return fetch_json(playbyplayv3.PlayByPlayV3, game_id, "pbp v3")


def fetch_boxscore_summary(game_id: str) -> dict | None:
    from nba_api.stats.endpoints import boxscoresummaryv3

    try:
        return fetch_json(boxscoresummaryv3.BoxScoreSummaryV3, game_id, "boxsum")
    except Exception as exc:  # noqa: BLE001
        log(f"WARN boxsum skipped {game_id}: {exc}")
        return None


def v3_action_count(payload: dict) -> int:
    game = payload.get("game") or {}
    actions = game.get("actions") or []
    if actions:
        return len(actions)
    pbp = game.get("playByPlay") or {}
    if isinstance(pbp, dict):
        return len(pbp.get("actions") or [])
    return 0


def pbp_ok(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 200:
        return False
    try:
        n = v3_action_count(load_json(path, {}))
    except Exception:  # noqa: BLE001
        return False
    return n > 0


def save_manifest(manifest: dict) -> None:
    games_state = manifest.get("games") or {}
    manifest["updated_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["complete"] = sum(
        1 for v in games_state.values() if v.get("status") == "COMPLETE"
    )
    manifest["failed"] = sum(
        1 for v in games_state.values() if v.get("status") == "FAILED"
    )
    write_atomic(MANIFEST_PATH, manifest)


def write_status(**kwargs) -> None:
    payload = {
        "warehouse_season": WAREHOUSE_SEASON,
        "stats_season": STATS_SEASON,
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        **kwargs,
    }
    write_atomic(STATUS_PATH, payload)


def schedule_targets(nba_by_id: dict[str, dict]) -> list[dict]:
    rows = []
    for gid, rec in sorted(nba_by_id.items()):
        rows.append(
            {
                "event_id": gid,
                "event_ticker": gid,
                "game_date": rec.get("game_date"),
                "nba_game_id": gid,
                "nba_matchup": rec.get("matchup"),
                "match_status": "NBA_SCHEDULE",
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="NBA play-by-play overnight ingest")
    p.add_argument(
        "--warehouse-season",
        default=os_env_season(),
        help="Warehouse folder label, e.g. 2025-2026",
    )
    p.add_argument(
        "--stats-season",
        default=None,
        help="NBA stats API season, e.g. 2025-26. Default derived from warehouse-season.",
    )
    args = p.parse_args(argv)
    stats = args.stats_season or stats_season_from_label(args.warehouse_season)
    configure(args.warehouse_season, stats)

    PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    PID_PATH.write_text(str(__import__("os").getpid()))
    t0 = time.time()
    log(f"PBP ingest start warehouse={WAREHOUSE_SEASON} stats={STATS_SEASON}")
    kalshi = load_kalshi_games()
    log(f"Kalshi games={len(kalshi)}")

    nba_by_id: dict[str, dict] = {}
    for st in SEASON_TYPES:
        cache = RAW / "schedule" / f"leaguegamelog_{st.replace(' ', '_').lower()}.json"
        if cache.exists():
            rows = load_json(cache, [])
            log(f"schedule cache hit {st} rows={len(rows)}")
        else:
            log(f"fetching leaguegamelog {STATS_SEASON} {st}")
            try:
                rows = fetch_league_game_log(st)
            except Exception as exc:  # noqa: BLE001
                log(f"WARN skip season_type={st}: {exc}")
                continue
            for r in rows:
                r["_season_type"] = st
            write_atomic(cache, rows)
            time.sleep(SLEEP_S)
            log(f"wrote {cache} rows={len(rows)}")
        games = unique_nba_games(rows)
        for gid, rec in games.items():
            rec["season_type"] = st
            nba_by_id[gid] = rec
    log(f"unique NBA GAME_IDs={len(nba_by_id)}")

    if kalshi:
        crosswalk, unmatched_nba = build_crosswalk(kalshi, nba_by_id)
        write_atomic(NORM / "pbp" / "game_crosswalk.json", crosswalk)
        write_atomic(RAW / "schedule" / "unmatched_nba_games.json", unmatched_nba)
        n_matched = sum(1 for r in crosswalk if r["match_status"] == "MATCHED")
        n_unmatched = sum(1 for r in crosswalk if r["match_status"] == "UNMATCHED")
        n_amb = sum(1 for r in crosswalk if r["match_status"] == "AMBIGUOUS")
        log(f"crosswalk matched={n_matched} unmatched={n_unmatched} ambiguous={n_amb}")
        targets = [r for r in crosswalk if r["match_status"] == "MATCHED" and r["nba_game_id"]]
    else:
        targets = schedule_targets(nba_by_id)
        n_unmatched = 0
        log(f"schedule-only targets={len(targets)}")
        write_atomic(RAW / "schedule" / "ingest_targets.json", targets)

    manifest = load_json(
        MANIFEST_PATH,
        {
            "job": "nba_pbp_overnight_ingest",
            "warehouse_season": WAREHOUSE_SEASON,
            "stats_season": STATS_SEASON,
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "games": {},
        },
    )
    games_state = manifest.setdefault("games", {})

    remaining = []
    already = 0
    for rec in targets:
        gid = rec["nba_game_id"]
        v3_path = RAW / "pbp_v3" / f"{gid}.json"
        if pbp_ok(v3_path):
            if games_state.get(gid, {}).get("status") != "COMPLETE":
                games_state[gid] = {
                    **games_state.get(gid, {}),
                    "status": "COMPLETE",
                    "event_ticker": rec["event_ticker"],
                    "event_id": rec["event_id"],
                    "n_actions": v3_action_count(load_json(v3_path, {})),
                    "pbp_source": "playbyplayv3",
                    "resumed_from_file": True,
                }
            already += 1
            continue
        remaining.append(rec)
    save_manifest(manifest)
    log(
        f"download targets={len(targets)} already_on_disk={already} remaining={len(remaining)}"
    )
    write_status(
        targets=len(targets),
        on_disk=already,
        remaining=len(remaining),
        done=len(remaining) == 0,
    )

    consec_fail = 0
    done_this_run = 0
    for i, rec in enumerate(remaining, 1):
        gid = rec["nba_game_id"]
        ticker = rec["event_ticker"]
        v3_path = RAW / "pbp_v3" / f"{gid}.json"
        box_path = RAW / "boxscore_summary" / f"{gid}.json"
        try:
            v3 = fetch_pbp_v3(gid)
            n_act = v3_action_count(v3)
            if n_act <= 0:
                raise RuntimeError("pbp v3 returned 0 actions")
            write_bytes_atomic(
                v3_path, json.dumps(v3, ensure_ascii=False).encode("utf-8")
            )
            time.sleep(SLEEP_S)

            game_time_utc = None
            if not box_path.exists():
                box = fetch_boxscore_summary(gid)
                if box is not None:
                    write_bytes_atomic(
                        box_path, json.dumps(box, ensure_ascii=False).encode("utf-8")
                    )
                    game_time_utc = (box.get("boxScoreSummary") or {}).get("gameTimeUTC")
                time.sleep(SLEEP_S)
            else:
                box = load_json(box_path, {})
                game_time_utc = (box.get("boxScoreSummary") or {}).get("gameTimeUTC")

            games_state[gid] = {
                "status": "COMPLETE",
                "event_ticker": ticker,
                "event_id": rec["event_id"],
                "n_actions": n_act,
                "game_time_utc": game_time_utc,
                "wall_clock_source": "UNAVAILABLE",
                "pbp_source": "playbyplayv3",
                "completed_utc": datetime.now(timezone.utc).isoformat(),
            }
            consec_fail = 0
            done_this_run += 1
            save_manifest(manifest)
            elapsed = max(1.0, time.time() - t0)
            rate = done_this_run / (elapsed / 60.0)
            eta_min = (len(remaining) - i) / rate if rate > 0 else None
            if i % 5 == 0 or i == len(remaining) or i == 1:
                log(
                    f"progress {i}/{len(remaining)} complete_disk={already + done_this_run}/{len(targets)} "
                    f"gid={gid} ticker={ticker} actions={n_act} "
                    f"rate={rate:.1f}/min eta_min={None if eta_min is None else round(eta_min, 1)}"
                )
        except Exception as exc:  # noqa: BLE001
            consec_fail += 1
            games_state[gid] = {
                "status": "FAILED",
                "event_ticker": ticker,
                "error": str(exc),
                "traceback": traceback.format_exc()[-1500:],
                "failed_utc": datetime.now(timezone.utc).isoformat(),
            }
            save_manifest(manifest)
            log(f"FAIL {gid} {ticker} consec={consec_fail}: {exc}")
            if consec_fail >= CONSEC_FAIL_TRIGGER:
                log(f"cooldown {CONSEC_FAIL_COOLDOWN_S}s after {consec_fail} consecutive failures")
                time.sleep(CONSEC_FAIL_COOLDOWN_S)
                consec_fail = 0
            else:
                time.sleep(SLEEP_S * 4)

    complete = sum(1 for v in games_state.values() if v.get("status") == "COMPLETE")
    failed = sum(1 for v in games_state.values() if v.get("status") == "FAILED")
    on_disk = sum(1 for rec in targets if pbp_ok(RAW / "pbp_v3" / f"{rec['nba_game_id']}.json"))
    write_status(
        targets=len(targets),
        on_disk=on_disk,
        remaining=max(0, len(targets) - on_disk),
        complete=complete,
        failed=failed,
        done=on_disk >= len(targets) and len(targets) > 0,
    )
    log(f"PBP ingest done complete={complete} failed={failed} unmatched={n_unmatched}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        try:
            PID_PATH.unlink(missing_ok=True)
        except Exception:
            pass
