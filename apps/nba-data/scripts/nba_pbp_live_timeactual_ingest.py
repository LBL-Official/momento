#!/usr/bin/env python3
"""Download NBA live CDN play-by-play so each action has observed timeActual.

Research only. Does not change live trading. Does not overwrite pbp_v3.
Does not invent wall clocks from tip + game clock.

The Stats PlayByPlayV3 payload we already warehouse has period + game clock
only. timeActual lives on the live CDN feed:

    https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{gameId}.json

On 2026-08-31 the overnight V3 ingest hit Access Denied on this URL because
the request lacked browser client-hint headers. As of 2026-09-03 the same
URL returns JSON (including opening-night 0022500001 and Finals 0042500405)
when the headers below are sent. Referer/Origin alone is still 403.

Accept a file only when actions exist and timeActual coverage is high.
Never reconstruct missing timeActual.
"""

from __future__ import annotations

import json
import time
import traceback
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATA_ROOT = Path("/Users/user/Desktop/Momento/Backtesting Suite/Data")
ROOT = DATA_ROOT / "NBA" / "2025-2026" / "warehouse"
RAW = ROOT / "raw" / "nba_stats"
NORM = ROOT / "normalized" / "nba"
LIVE_DIR = RAW / "pbp_live"
MANIFEST_PATH = ROOT / "manifests" / "nba" / "pbp_live_ingest_manifest.json"
LOG_PATH = ROOT / "manifests" / "nba" / "pbp_live_ingest.log"
PID_PATH = ROOT / "manifests" / "nba" / "pbp_live_ingest.pid"
STATUS_PATH = ROOT / "manifests" / "nba" / "pbp_live_ingest_status.json"
FIRST80_INDEX = (
    ROOT
    / "derived"
    / "nba"
    / "first80_multidimensional_exit_hedge_fee_v2"
    / "pbp"
    / "first80_pbp_index.json"
)
V2_PBP_DIR = (
    ROOT / "derived" / "nba" / "first80_multidimensional_exit_hedge_fee_v2" / "pbp"
)

CDN_URL = (
    "https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{game_id}.json"
)
# WAF as of 2026-09-03: Referer+Origin alone → 403. Client hints required.
CDN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.nba.com",
    "Referer": "https://www.nba.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
    "Sec-CH-UA": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"macOS"',
}

SLEEP_S = 0.45
TIMEOUT_S = 25
MAX_RETRIES = 4
CONSEC_FAIL_COOLDOWN_S = 45
CONSEC_FAIL_TRIGGER = 3
MIN_TIMEACTUAL_RATE = 0.95


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


def live_actions(payload: dict) -> list:
    game = payload.get("game") or {}
    actions = game.get("actions") or []
    return actions if isinstance(actions, list) else []


def timeactual_stats(payload: dict) -> tuple[int, int]:
    actions = live_actions(payload)
    n = len(actions)
    n_ta = sum(1 for a in actions if isinstance(a, dict) and a.get("timeActual"))
    return n, n_ta


def live_ok(path: Path) -> dict | None:
    if not path.exists() or path.stat().st_size < 200:
        return None
    try:
        payload = load_json(path, {})
    except Exception:  # noqa: BLE001
        return None
    n, n_ta = timeactual_stats(payload)
    if n <= 0:
        return None
    rate = n_ta / n
    if rate < MIN_TIMEACTUAL_RATE:
        return None
    return {"n_actions": n, "n_timeActual": n_ta, "timeActual_rate": rate}


def fetch_live(game_id: str) -> tuple[bytes, dict]:
    url = CDN_URL.format(game_id=game_id)
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        req = urllib.request.Request(url, headers=CDN_HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                raw = resp.read()
                status = getattr(resp, "status", 200)
            if status != 200:
                raise RuntimeError(f"HTTP {status}")
            if raw[:1] != b"{":
                head = raw[:180].decode("utf-8", errors="replace")
                raise RuntimeError(f"non-json body: {head}")
            payload = json.loads(raw)
            n, n_ta = timeactual_stats(payload)
            if n <= 0:
                raise RuntimeError("live pbp returned 0 actions")
            rate = n_ta / n
            if rate < MIN_TIMEACTUAL_RATE:
                raise RuntimeError(
                    f"timeActual coverage {n_ta}/{n}={rate:.4f} < {MIN_TIMEACTUAL_RATE}"
                )
            return raw, payload
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            code = getattr(exc, "code", None)
            wait = min(25, 1.5**attempt)
            log(
                f"RETRY live pbp {game_id} attempt={attempt} wait={wait:.1f}s "
                f"http={code} err={exc}"
            )
            time.sleep(wait)
    raise RuntimeError(f"live pbp failed {game_id}: {last_err}")


def target_ids() -> list[dict]:
    """Unique nba_game_id list: FIRST-80 first, then remaining V3 / crosswalk."""
    seen: dict[str, dict] = {}

    crosswalk = load_json(NORM / "pbp" / "game_crosswalk.json", [])
    if isinstance(crosswalk, list):
        for row in crosswalk:
            gid = str(row.get("nba_game_id") or "").zfill(10)
            if not gid or gid == "0000000000":
                continue
            if row.get("match_status") not in (None, "MATCHED", "NBA_SCHEDULE"):
                if not row.get("nba_game_id"):
                    continue
            seen[gid] = {
                "nba_game_id": gid,
                "event_ticker": row.get("event_ticker"),
                "event_id": row.get("event_id"),
                "game_date": row.get("game_date"),
                "priority": 1,
                "source": "crosswalk",
            }

    v3_dir = RAW / "pbp_v3"
    if v3_dir.exists():
        for path in v3_dir.glob("*.json"):
            gid = path.stem.zfill(10)
            seen.setdefault(
                gid,
                {
                    "nba_game_id": gid,
                    "event_ticker": gid,
                    "event_id": gid,
                    "game_date": None,
                    "priority": 1,
                    "source": "pbp_v3",
                },
            )

    first80 = load_json(FIRST80_INDEX, [])
    first80_ids = set()
    if isinstance(first80, list):
        for row in first80:
            gid = str(row.get("nba_game_id") or "").zfill(10)
            if not gid or gid == "0000000000":
                continue
            first80_ids.add(gid)
            rec = seen.setdefault(
                gid,
                {
                    "nba_game_id": gid,
                    "event_ticker": row.get("event_id") or row.get("ticker"),
                    "event_id": row.get("event_id"),
                    "game_date": row.get("game_date"),
                    "priority": 0,
                    "source": "first80",
                },
            )
            rec["priority"] = 0
            rec["event_ticker"] = rec.get("event_ticker") or row.get("event_id")
            rec["event_id"] = rec.get("event_id") or row.get("event_id")

    rows = list(seen.values())
    rows.sort(key=lambda r: (r["priority"], r.get("game_date") or "", r["nba_game_id"]))
    return rows, first80_ids


def write_status(**kwargs) -> None:
    payload = {
        "job": "nba_pbp_live_timeactual_ingest",
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "live_execution_changed": False,
        **kwargs,
    }
    write_atomic(STATUS_PATH, payload)


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


def refresh_v2_pointer(complete: int, failed: int, first80_ids: set[str]) -> None:
    """Symlink live dir into V2 pbp pointer. Do not join into V2 EV."""
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    pointer = V2_PBP_DIR / "raw_pbp_live"
    if pointer.exists() or pointer.is_symlink():
        if pointer.is_symlink() or pointer.is_file():
            pointer.unlink()
        else:
            # leave a real directory alone
            pass
    if not pointer.exists():
        pointer.symlink_to(LIVE_DIR.resolve())

    first80 = load_json(FIRST80_INDEX, [])
    n_first80 = len(first80) if isinstance(first80, list) else 0
    with_live = 0
    missing = []
    if isinstance(first80, list):
        for row in first80:
            gid = str(row.get("nba_game_id") or "").zfill(10)
            if gid and gid != "0000000000" and live_ok(LIVE_DIR / f"{gid}.json"):
                with_live += 1
            elif row.get("match_status") == "MATCHED" and gid and gid != "0000000000":
                missing.append(row.get("event_id") or gid)
            elif not row.get("nba_game_id"):
                missing.append(row.get("event_id"))

    inventory = {
        "program": "FIRST80_MULTIDIMENSIONAL_EXIT_HEDGE_FEE_ENGINE_V2",
        "live_execution_changed": False,
        "note": (
            "Live CDN PBP added for observed timeActual. "
            "Does not join PBP into V2 EV. Does not invent wall-clock fills. "
            "Does not overwrite pbp_v3."
        ),
        "source": {
            "provider": "cdn.nba.com liveData playbyplay",
            "endpoint": CDN_URL,
            "canonical_raw_live": str(LIVE_DIR),
            "canonical_raw_v3": str(RAW / "pbp_v3"),
            "canonical_crosswalk": str(NORM / "pbp" / "game_crosswalk.json"),
            "copy_policy": "SYMLINK_NO_DUPLICATE",
        },
        "warehouse": {
            "pbp_live_complete": complete,
            "pbp_live_failed": failed,
            "pbp_v3_files": len(list((RAW / "pbp_v3").glob("*.json")))
            if (RAW / "pbp_v3").exists()
            else 0,
        },
        "first80": {
            "n": n_first80,
            "with_live_timeActual": with_live,
            "missing_or_unmatched": len(missing),
        },
        "clock": {
            "per_play_wall_clock_timeActual": "PRESENT on live CDN actions",
            "period_and_game_clock": "PRESENT on V3 and live",
            "label": (
                "timeActual is observed wall clock from the live feed. "
                "GAME CLOCK ≠ WALL CLOCK. Do not treat V3 clock as timeActual."
            ),
        },
        "join_status": (
            "LIVE_PBP_DOWNLOADED — not yet validated as a V2 EV input."
        ),
        "updated_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_atomic(V2_PBP_DIR / "live_inventory.json", inventory)


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="NBA live PBP timeActual ingest")
    p.add_argument("--limit", type=int, default=0, help="Max new downloads this run")
    args = p.parse_args(argv)

    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PID_PATH.write_text(str(__import__("os").getpid()))
    t0 = time.time()

    targets, first80_ids = target_ids()
    log(
        f"live timeActual ingest start targets={len(targets)} "
        f"first80_ids={len(first80_ids)}"
    )

    manifest = load_json(
        MANIFEST_PATH,
        {
            "job": "nba_pbp_live_timeactual_ingest",
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "endpoint": CDN_URL,
            "min_timeActual_rate": MIN_TIMEACTUAL_RATE,
            "does_not_overwrite_pbp_v3": True,
            "live_execution_changed": False,
            "games": {},
        },
    )
    games_state = manifest.setdefault("games", {})

    remaining = []
    already = 0
    for rec in targets:
        gid = rec["nba_game_id"]
        stats = live_ok(LIVE_DIR / f"{gid}.json")
        if stats:
            games_state[gid] = {
                **games_state.get(gid, {}),
                "status": "COMPLETE",
                "event_ticker": rec.get("event_ticker"),
                "event_id": rec.get("event_id"),
                "priority": rec.get("priority"),
                **stats,
                "pbp_source": "cdn_live_playbyplay",
                "wall_clock_source": "timeActual",
                "resumed_from_file": True,
            }
            already += 1
            continue
        remaining.append(rec)
    save_manifest(manifest)
    if args.limit and args.limit > 0:
        remaining = remaining[: args.limit]
    log(
        f"download targets={len(targets)} already_on_disk={already} "
        f"remaining={len(remaining)}"
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
        ticker = rec.get("event_ticker") or gid
        dest = LIVE_DIR / f"{gid}.json"
        try:
            raw, payload = fetch_live(gid)
            n, n_ta = timeactual_stats(payload)
            write_bytes_atomic(dest, raw)
            games_state[gid] = {
                "status": "COMPLETE",
                "event_ticker": ticker,
                "event_id": rec.get("event_id"),
                "priority": rec.get("priority"),
                "n_actions": n,
                "n_timeActual": n_ta,
                "timeActual_rate": n_ta / n,
                "bytes": len(raw),
                "pbp_source": "cdn_live_playbyplay",
                "wall_clock_source": "timeActual",
                "completed_utc": datetime.now(timezone.utc).isoformat(),
            }
            consec_fail = 0
            done_this_run += 1
            save_manifest(manifest)
            elapsed = max(1.0, time.time() - t0)
            rate = done_this_run / (elapsed / 60.0)
            eta_min = (len(remaining) - i) / rate if rate > 0 else None
            if i % 10 == 0 or i == len(remaining) or i == 1:
                log(
                    f"progress {i}/{len(remaining)} "
                    f"complete_disk={already + done_this_run}/{len(targets)} "
                    f"gid={gid} ticker={ticker} actions={n} timeActual={n_ta} "
                    f"rate={rate:.1f}/min eta_min={None if eta_min is None else round(eta_min, 1)}"
                )
            time.sleep(SLEEP_S)
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
                log(
                    f"cooldown {CONSEC_FAIL_COOLDOWN_S}s after "
                    f"{consec_fail} consecutive failures"
                )
                time.sleep(CONSEC_FAIL_COOLDOWN_S)
                consec_fail = 0
            else:
                time.sleep(SLEEP_S * 4)

    complete = sum(1 for v in games_state.values() if v.get("status") == "COMPLETE")
    failed = sum(1 for v in games_state.values() if v.get("status") == "FAILED")
    on_disk = sum(1 for rec in targets if live_ok(LIVE_DIR / f"{rec['nba_game_id']}.json"))
    write_status(
        targets=len(targets),
        on_disk=on_disk,
        remaining=max(0, len(targets) - on_disk),
        complete=complete,
        failed=failed,
        done=on_disk >= len(targets) and len(targets) > 0,
    )
    refresh_v2_pointer(complete, failed, first80_ids)
    log(f"live timeActual ingest done complete={complete} failed={failed} on_disk={on_disk}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        try:
            PID_PATH.unlink(missing_ok=True)
        except Exception:
            pass
