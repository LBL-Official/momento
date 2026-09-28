"""NCAAB half-clock alignment from ESPN play-by-play.

ESPN summaries expose an observed per-play `wallclock`. Snap uses the last
play whose wall ≤ the candle timestamp. Intra-half times are not invented
from Kalshi market open.

Regulation is 2 × 20:00 halves. Future OT is unknown and is not added to
remaining clock. Period ≥ 3 is OT (typically 5:00).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

ROOT = Path(
    "/Users/user/Desktop/Momento/Backtesting Suite/Data/NCAAB/2025-2026/warehouse"
)
PLAYS_DIR = ROOT / "normalized" / "ncaab" / "pbp" / "plays"
CROSSWALK_PATH = ROOT / "normalized" / "ncaab" / "pbp" / "game_crosswalk.json"

HALF_S = 1200
OT_S = 300
SPLIT_S = 600  # 10:00 remaining splits first/second 10 of a half
PRIMARY_ALIGN = frozenset({"HIGH", "MEDIUM"})
CLOCK_RE = re.compile(r"^(\d{1,2}):(\d{2}(?:\.\d+)?)$")

ALIGNMENT_MODEL = "HALF_BOUNDED_OBSERVED_WALLCLOCK"


def parse_clock_seconds(clock: str | None) -> float | None:
    if not clock:
        return None
    s = str(clock).strip()
    m = CLOCK_RE.match(s)
    if not m:
        return None
    return int(m.group(1)) * 60.0 + float(m.group(2))


def period_length_s(period: int | None) -> int:
    if period is None:
        return HALF_S
    return HALF_S if int(period) <= 2 else OT_S


def game_seconds_elapsed(period: int | None, remaining: float | None) -> float | None:
    if period is None or remaining is None:
        return None
    p = int(period)
    elapsed = 0.0
    for prior in range(1, p):
        elapsed += float(period_length_s(prior))
    elapsed += max(0.0, period_length_s(p) - float(remaining))
    return elapsed


def game_seconds_remaining(period: int | None, remaining: float | None) -> float | None:
    """Unused regulation remaining. Future OT is not invented."""
    if period is None or remaining is None:
        return None
    p = int(period)
    if p <= 0:
        return None
    if p == 1:
        return float(remaining) + HALF_S
    if p == 2:
        return float(remaining)
    return float(remaining)


def parse_iso_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    t = s.strip()
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(t)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def wall_ts(s: str | None) -> int | None:
    dt = parse_iso_dt(s)
    if dt is None:
        return None
    return int(dt.timestamp())


def load_json(path: Path):
    return json.loads(path.read_text())


@lru_cache(maxsize=2048)
def load_plays(espn_game_id: str) -> dict | None:
    path = PLAYS_DIR / f"{espn_game_id}.json"
    if not path.exists():
        return None
    return load_json(path)


def load_crosswalk() -> dict[str, dict]:
    rows = load_json(CROSSWALK_PATH) if CROSSWALK_PATH.exists() else []
    return {r["event_id"]: r for r in rows}


def _is_period_start(play: dict, period: int | None) -> bool:
    text = (play.get("text") or "").lower()
    typ = (play.get("type_text") or "").lower()
    if period == 1 and ("start game" in text or "start of 1st" in text):
        return True
    if "start of" in text and "half" in text:
        return True
    if typ == "end period" or typ == "end game":
        return False
    clock = play.get("clock")
    rem = parse_clock_seconds(clock)
    return rem is not None and abs(rem - period_length_s(period)) < 0.6 and text.startswith("start")


def _is_period_end(play: dict) -> bool:
    typ = (play.get("type_text") or "").lower()
    text = (play.get("text") or "").lower()
    if typ in {"end period", "end game"}:
        return True
    return text.startswith("end of") and ("half" in text or "ot" in text or "game" in text)


def enrich_actions(plays: list[dict]) -> list[dict]:
    out = []
    for i, p in enumerate(plays):
        try:
            period_i = int(p["period"]) if p.get("period") is not None else None
        except (TypeError, ValueError):
            period_i = None
        remaining = parse_clock_seconds(p.get("clock"))
        observed = wall_ts(p.get("wallclock"))
        rec = {
            "idx": i,
            "actionType": "period" if _is_period_start(p, period_i) or _is_period_end(p) else (p.get("type_text") or ""),
            "subType": "start" if _is_period_start(p, period_i) else ("end" if _is_period_end(p) else ""),
            "period": period_i,
            "clock": p.get("clock"),
            "remaining_s": remaining,
            "elapsed_s": game_seconds_elapsed(period_i, remaining),
            "score_home": p.get("homeScore"),
            "score_away": p.get("awayScore"),
            "description": p.get("text") or "",
            "knot_wall_ts": observed,
            "modeled_wall_ts": observed,
            "wall_source": "OBSERVED" if observed is not None else None,
        }
        out.append(rec)
    _fill_missing_walls(out)
    return out


def _fill_missing_walls(rows: list[dict]) -> None:
    """Linear interpolate only where ESPN omitted wallclock, within a half."""
    by_period: dict[int, list[dict]] = {}
    for r in rows:
        if r["period"] is None:
            continue
        by_period.setdefault(r["period"], []).append(r)
    for items in by_period.values():
        knots = []
        for r in items:
            if r["knot_wall_ts"] is None or r["remaining_s"] is None:
                continue
            knots.append((float(r["remaining_s"]), int(r["knot_wall_ts"])))
        knots.sort(key=lambda t: -t[0])
        uniq = []
        seen = set()
        for rem, ts in knots:
            key = round(rem, 2)
            if key in seen:
                continue
            seen.add(key)
            uniq.append((rem, ts))
        for r in items:
            if r["modeled_wall_ts"] is not None:
                continue
            r["modeled_wall_ts"] = _interp_wall(r["remaining_s"], uniq)
            if r["modeled_wall_ts"] is not None:
                r["wall_source"] = "LINEAR_HALF"


def _interp_wall(remaining: float | None, knots: list[tuple[float, int]]) -> int | None:
    if remaining is None or len(knots) < 1:
        return None
    if len(knots) == 1:
        return knots[0][1]
    rem = float(remaining)
    if rem >= knots[0][0]:
        return knots[0][1]
    if rem <= knots[-1][0]:
        return knots[-1][1]
    for i in range(len(knots) - 1):
        r0, t0 = knots[i]
        r1, t1 = knots[i + 1]
        if r0 >= rem >= r1:
            if r0 == r1:
                return t0
            frac = (r0 - rem) / (r0 - r1)
            return int(t0 + frac * (t1 - t0))
    return knots[-1][1]


def period_bounds(rows: list[dict]) -> dict[int, dict]:
    bounds: dict[int, dict] = {}
    for r in rows:
        p = r["period"]
        if p is None:
            continue
        b = bounds.setdefault(p, {"start": None, "end": None})
        if r["subType"] == "start" and r["knot_wall_ts"]:
            b["start"] = r["knot_wall_ts"]
        if r["subType"] == "end" and r["knot_wall_ts"]:
            b["end"] = r["knot_wall_ts"]
    for p, items in _by_period(rows).items():
        b = bounds.setdefault(p, {"start": None, "end": None})
        walls = [r["modeled_wall_ts"] for r in items if r["modeled_wall_ts"] is not None]
        if b["start"] is None and walls:
            b["start"] = walls[0]
        if b["end"] is None and walls:
            b["end"] = walls[-1]
    return bounds


def _by_period(rows: list[dict]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for r in rows:
        if r["period"] is None:
            continue
        out.setdefault(r["period"], []).append(r)
    return out


def snap_to_entry(rows: list[dict], entry_ts: int) -> dict:
    """Last action with wall ≤ entry. Halftime uses last completed half."""
    bounds = period_bounds(rows)
    first_start = None if 1 not in bounds else bounds[1].get("start")
    last_end = None
    for p in sorted(bounds):
        if bounds[p].get("end") is not None:
            last_end = bounds[p]["end"]
    candidates = [
        r for r in rows if r["modeled_wall_ts"] is not None and r["modeled_wall_ts"] <= entry_ts
    ]
    if not candidates:
        if first_start is not None and entry_ts < first_start:
            return {
                "snap_idx": None,
                "game_phase": "GAME_NOT_STARTED",
                "first_period_start_ts": first_start,
                "last_period_end_ts": last_end,
            }
        with_elapsed = [r for r in rows if r["elapsed_s"] is not None]
        if not with_elapsed:
            return {
                "snap_idx": None,
                "game_phase": "UNALIGNED",
                "first_period_start_ts": first_start,
                "last_period_end_ts": last_end,
            }
        return {
            "snap_idx": with_elapsed[-1]["idx"],
            "game_phase": "WALL_MISSING_FALLBACK",
            "first_period_start_ts": first_start,
            "last_period_end_ts": last_end,
        }
    snap = candidates[-1]
    phase = "IN_PERIOD"
    if last_end is not None and entry_ts > last_end + 30:
        phase = "GAME_ENDED"
    elif first_start is not None and entry_ts < first_start:
        phase = "GAME_NOT_STARTED"
    else:
        nxt = None
        if snap["period"] is not None:
            nxt_b = bounds.get(int(snap["period"]) + 1)
            if nxt_b:
                nxt = nxt_b.get("start")
        ended = None if snap["period"] is None else bounds.get(int(snap["period"]), {}).get("end")
        if ended is not None and nxt is not None and ended < entry_ts < nxt:
            phase = "INTERMISSION"
    return {
        "snap_idx": snap["idx"],
        "game_phase": phase,
        "first_period_start_ts": first_start,
        "last_period_end_ts": last_end,
        "snap_modeled_wall_ts": snap["modeled_wall_ts"],
        "snap_lag_s": entry_ts - snap["modeled_wall_ts"] if snap["modeled_wall_ts"] else None,
    }


def classify_confidence(rows: list[dict], snap: dict, entry_ts: int) -> tuple[str, str]:
    if not rows:
        return "UNUSABLE", "NO_PBP"
    phase = snap.get("game_phase")
    if phase == "UNALIGNED":
        return "UNUSABLE", "NO_MODELED_WALL"
    first_start = snap.get("first_period_start_ts")
    last_end = snap.get("last_period_end_ts")
    if first_start is None or last_end is None:
        return "LOW", "MISSING_PERIOD_STAMPS"
    if entry_ts < first_start - 30 * 60 or entry_ts > last_end + 30 * 60:
        if phase == "GAME_NOT_STARTED" and first_start - 30 * 60 <= entry_ts < first_start:
            return "MEDIUM", "PRE_TIP_WITHIN_30M"
        return "UNUSABLE", "ENTRY_OUTSIDE_GAME_WINDOW"
    if phase == "GAME_NOT_STARTED":
        return "MEDIUM", "GAME_NOT_STARTED"
    if phase in ("INTERMISSION", "GAME_ENDED"):
        return "MEDIUM", phase
    if phase == "WALL_MISSING_FALLBACK":
        return "LOW", "WALL_MISSING_FALLBACK"
    observed = sum(1 for r in rows if r.get("wall_source") == "OBSERVED")
    if observed >= max(20, int(0.5 * len(rows))) and phase == "IN_PERIOD":
        return "HIGH", "IN_PERIOD_OBSERVED_WALL"
    if phase == "IN_PERIOD":
        return "MEDIUM", "IN_PERIOD_PARTIAL_WALL"
    return "LOW", "INCOMPLETE_BOUNDS"


def entry_bucket(
    confidence: str | None,
    phase: str | None,
    period: int | None,
    period_remaining_s: float | None,
) -> str:
    """H1_1 / H1_2 / H2_1 / H2_2. OT and unusable stay out of the 10-min bins."""
    if confidence not in PRIMARY_ALIGN:
        return "UNALIGNED"
    if phase in (None, "GAME_NOT_STARTED", "UNALIGNED"):
        return "UNALIGNED"
    if period is None or period_remaining_s is None:
        return "UNALIGNED"
    p = int(period)
    rem = float(period_remaining_s)
    if p >= 3:
        return "OT"
    if p == 1:
        return "H1_1" if rem > SPLIT_S else "H1_2"
    if p == 2:
        return "H2_1" if rem > SPLIT_S else "H2_2"
    return "UNALIGNED"


def snap_clock(actions: list[dict], ts: int) -> dict:
    snap = snap_to_entry(actions, int(ts))
    idx = snap.get("snap_idx")
    row = actions[idx] if idx is not None and 0 <= idx < len(actions) else None
    period = None if row is None else row.get("period")
    period_remaining = None if row is None else row.get("remaining_s")
    return {
        "phase": snap.get("game_phase"),
        "snap_idx": idx,
        "period": period,
        "period_remaining_s": period_remaining,
        "elapsed_s": None if row is None else row.get("elapsed_s"),
        "game_seconds_remaining": game_seconds_remaining(period, period_remaining),
        "game_seconds_elapsed": game_seconds_elapsed(period, period_remaining),
        "snap_modeled_wall_ts": snap.get("snap_modeled_wall_ts"),
        "wall_source": None if row is None else row.get("wall_source"),
    }
