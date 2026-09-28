"""April 2025 NBA clock. Identity join only: date plus team pair. Scores are not read."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from first78.clocks import nba_bucket, nba_mod

REPO = Path(__file__).resolve().parents[4]
RAW = REPO / "Backtesting Suite/Data/NBA/2024-2025/warehouse/raw/nba_stats"
SCHEDULES = [
    RAW / "schedule/leaguegamelog_pre_season.json",
    RAW / "schedule/leaguegamelog_regular_season.json",
    RAW / "schedule/leaguegamelog_playin.json",
    RAW / "schedule/leaguegamelog_playoffs.json",
]
MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}
EVENT_RX = re.compile(r"KXNBAGAME-(\d{2})([A-Z]{3})(\d{2})([A-Z]{3})([A-Z]{3})$")


def parse_event_ticker(event_ticker: str) -> tuple[str, frozenset[str]] | None:
    match = EVENT_RX.fullmatch(str(event_ticker))
    if not match:
        return None
    year = 2000 + int(match.group(1))
    month = MONTHS.get(match.group(2))
    if month is None:
        return None
    day = int(match.group(3))
    teams = frozenset({match.group(4), match.group(5)})
    return (f"{year:04d}-{month:02d}-{day:02d}", teams)


def _teams(matchup: str) -> frozenset[str] | None:
    if " vs. " in matchup:
        left, right = matchup.split(" vs. ", 1)
    elif " @ " in matchup:
        left, right = matchup.split(" @ ", 1)
    else:
        return None
    return frozenset({left.strip(), right.strip()})


@lru_cache(maxsize=1)
def schedule_index() -> dict[tuple[str, frozenset[str]], list[dict]]:
    index: dict[tuple[str, frozenset[str]], list[dict]] = {}
    for path in SCHEDULES:
        if not path.exists():
            continue
        rows = json.loads(path.read_text())
        for row in rows:
            teams = _teams(str(row.get("MATCHUP") or ""))
            if teams is None or len(teams) != 2:
                continue
            key = (str(row.get("GAME_DATE")), teams)
            game_id = str(row.get("GAME_ID"))
            stage = str(row.get("_season_type") or path.stem)
            bucket = index.setdefault(key, [])
            if not any(item["nba_game_id"] == game_id for item in bucket):
                bucket.append({"nba_game_id": game_id, "stage": stage})
    return index


def align_april(event_ticker: str, ts: int) -> dict:
    out = {
        "bucket": "UNALIGNED",
        "clock_quality": "UNALIGNED",
        "period": None,
        "period_remaining_s": None,
        "phase": None,
        "stage": "STAGE_UNLABELED",
        "reason": None,
        "seconds_are_modeled": True,
    }
    parsed = parse_event_ticker(event_ticker)
    if parsed is None:
        out["reason"] = "TICKER_UNPARSED"
        return out
    matches = schedule_index().get(parsed) or []
    if len(matches) != 1:
        out["reason"] = "CLOCK_JOIN_AMBIGUOUS" if len(matches) > 1 else "CLOCK_JOIN_MISS"
        return out
    game_id = matches[0]["nba_game_id"]
    out["stage"] = matches[0]["stage"]
    pbp_path = RAW / "pbp_v3" / f"{game_id}.json"
    box_path = RAW / "boxscore_summary" / f"{game_id}.json"
    if not pbp_path.exists():
        out["reason"] = "NO_PBP"
        return out
    mod = nba_mod()
    pbp = json.loads(pbp_path.read_text())
    box = json.loads(box_path.read_text()) if box_path.exists() else None
    header = mod.box_header(box)
    actions = mod.enrich_actions(pbp.get("game", {}).get("actions") or [], header)
    if not actions:
        out["reason"] = "NO_PBP"
        return out
    snap = mod.snap_to_entry(actions, int(ts))
    residuals = mod.replay_residuals(actions)
    conf, reason = mod.classify_confidence(actions, snap, int(ts), header, residuals)
    idx = snap.get("snap_idx")
    row = actions[idx] if idx is not None and 0 <= idx < len(actions) else None
    period = None if row is None else row.get("period")
    out.update(
        {
            "bucket": nba_bucket(conf, snap.get("game_phase"), period),
            "clock_quality": conf,
            "period": period,
            "period_remaining_s": None if row is None else row.get("remaining_s"),
            "phase": snap.get("game_phase"),
            "reason": reason,
        }
    )
    return out
