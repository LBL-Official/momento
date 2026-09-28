"""PBP clock parsing and PERIOD_BOUNDED_LINEAR_GAME_CLOCK alignment.

Per-play structured wall clock is UNAVAILABLE. Period start/end (and some
replay) descriptions carry local times. Those are observed knots. Intra-period
times are modeled. Never infer tip from Kalshi market open.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from common import BOX_DIR, PBP_DIR

CLOCK_RE = re.compile(
    r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?$",
    re.I,
)
TIME_IN_DESC = re.compile(
    r"\((\d{1,2}):(\d{2})\s*(AM|PM)\s*([A-Z]{2,4})\)",
    re.I,
)


def parse_clock_seconds(clock: str | None) -> float | None:
    if not clock:
        return None
    m = CLOCK_RE.match(str(clock).strip())
    if not m:
        return None
    h = int(m.group(1) or 0)
    mi = int(m.group(2) or 0)
    s = float(m.group(3) or 0.0)
    return h * 3600.0 + mi * 60.0 + s


def period_length_s(period: int | None) -> int:
    if period is None:
        return 720
    return 720 if int(period) <= 4 else 300


def game_seconds_elapsed(period: int | None, remaining: float | None) -> float | None:
    if period is None or remaining is None:
        return None
    p = int(period)
    elapsed = 0.0
    for prior in range(1, p):
        elapsed += 720.0 if prior <= 4 else 300.0
    plen = period_length_s(p)
    elapsed += max(0.0, plen - float(remaining))
    return elapsed


def game_seconds_remaining(period: int | None, remaining: float | None) -> float | None:
    """Unused regulation remaining. Future OT is unknown and not invented."""
    if period is None or remaining is None:
        return None
    p = int(period)
    if p <= 4:
        return float(remaining) + (4 - p) * 720.0
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


def naive_from_zulu_tagged(s: str | None) -> datetime | None:
    """gameEt is local clock incorrectly tagged Z. Treat as naive wall."""
    if not s:
        return None
    t = s.strip()
    if t.endswith("Z"):
        t = t[:-1]
    try:
        return datetime.fromisoformat(t)
    except ValueError:
        return None


def parse_duration_seconds(dur: str | None) -> int | None:
    if not dur:
        return None
    parts = str(dur).strip().split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 3600 + int(parts[1]) * 60
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except ValueError:
        return None
    return None


def load_json(path: Path):
    return json.loads(path.read_text())


@lru_cache(maxsize=2048)
def load_pbp(nba_game_id: str) -> dict | None:
    path = PBP_DIR / f"{nba_game_id}.json"
    if not path.exists():
        return None
    return load_json(path)


@lru_cache(maxsize=2048)
def load_box(nba_game_id: str) -> dict | None:
    path = BOX_DIR / f"{nba_game_id}.json"
    if not path.exists():
        return None
    return load_json(path)


def box_header(box: dict | None) -> dict:
    if not box:
        return {}
    return box.get("boxScoreSummary") or {}


def utc_offset_from_box(header: dict) -> int | None:
    """Seconds to add to naive local (gameEt) to obtain UTC."""
    utc = parse_iso_dt(header.get("gameTimeUTC"))
    local = naive_from_zulu_tagged(header.get("gameEt"))
    if utc is None or local is None:
        return None
    local_as_utc = local.replace(tzinfo=timezone.utc)
    return int((utc - local_as_utc).total_seconds())


def local_clock_to_utc(header: dict, hour: int, minute: int, ampm: str) -> int | None:
    local = naive_from_zulu_tagged(header.get("gameEt"))
    offset = utc_offset_from_box(header)
    utc_tip = parse_iso_dt(header.get("gameTimeUTC"))
    if local is None or offset is None or utc_tip is None:
        return None
    h = int(hour) % 12
    if ampm.upper() == "PM":
        h += 12
    naive = datetime(local.year, local.month, local.day, h, int(minute), 0)
    utc = naive.replace(tzinfo=timezone.utc) + timedelta(seconds=offset)
    # OT / late games past midnight: if more than 8h before tip, roll forward a day.
    if (utc_tip - utc).total_seconds() > 8 * 3600:
        utc = utc + timedelta(days=1)
    if (utc - utc_tip).total_seconds() > 12 * 3600:
        utc = utc - timedelta(days=1)
    return int(utc.timestamp())


def extract_desc_time(header: dict, description: str | None) -> int | None:
    if not description:
        return None
    m = TIME_IN_DESC.search(description)
    if not m:
        return None
    return local_clock_to_utc(header, int(m.group(1)), int(m.group(2)), m.group(3))


def actions_of(pbp: dict | None) -> list[dict]:
    if not pbp:
        return []
    game = pbp.get("game") or {}
    return list(game.get("actions") or [])


def enrich_actions(actions: list[dict], header: dict) -> list[dict]:
    out = []
    for i, a in enumerate(actions):
        period = a.get("period")
        try:
            period_i = int(period) if period is not None else None
        except (TypeError, ValueError):
            period_i = None
        remaining = parse_clock_seconds(a.get("clock"))
        desc = a.get("description") or ""
        knot = extract_desc_time(header, desc)
        try:
            sh = int(a.get("scoreHome") or 0)
        except (TypeError, ValueError):
            sh = 0
        try:
            sa = int(a.get("scoreAway") or 0)
        except (TypeError, ValueError):
            sa = 0
        elapsed = game_seconds_elapsed(period_i, remaining)
        rec = {
            "idx": i,
            "actionNumber": a.get("actionNumber"),
            "actionType": a.get("actionType"),
            "subType": a.get("subType"),
            "period": period_i,
            "clock": a.get("clock"),
            "remaining_s": remaining,
            "elapsed_s": elapsed,
            "score_home": sh,
            "score_away": sa,
            "team_tricode": (a.get("teamTricode") or "") or None,
            "description": desc,
            "knot_wall_ts": knot,
            "modeled_wall_ts": None,
        }
        out.append(rec)
    _assign_modeled_walls(out)
    return out


def _assign_modeled_walls(rows: list[dict]) -> None:
    by_period: dict[int, list[dict]] = {}
    for r in rows:
        p = r["period"]
        if p is None:
            continue
        by_period.setdefault(p, []).append(r)
    for _p, items in by_period.items():
        knots = []
        for r in items:
            if r["knot_wall_ts"] is None or r["remaining_s"] is None:
                continue
            knots.append((float(r["remaining_s"]), int(r["knot_wall_ts"])))
        knots.sort(key=lambda t: -t[0])
        # Dedup remaining
        uniq = []
        seen = set()
        for rem, ts in knots:
            key = round(rem, 2)
            if key in seen:
                continue
            seen.add(key)
            uniq.append((rem, ts))
        for r in items:
            r["modeled_wall_ts"] = _interp_wall(r["remaining_s"], uniq)


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
    bounds = {}
    for r in rows:
        p = r["period"]
        if p is None:
            continue
        b = bounds.setdefault(p, {"start": None, "end": None, "replays": []})
        typ = (r.get("actionType") or "").lower()
        sub = (r.get("subType") or "").lower()
        if typ == "period" and sub == "start" and r["knot_wall_ts"]:
            b["start"] = r["knot_wall_ts"]
        if typ == "period" and sub == "end" and r["knot_wall_ts"]:
            b["end"] = r["knot_wall_ts"]
        if typ == "instant replay" and r["knot_wall_ts"] is not None:
            b["replays"].append(r)
    return bounds


def replay_residuals(rows: list[dict]) -> list[float]:
    """Leave-one-out: interpolate replay using only period start/end knots."""
    bounds = period_bounds(rows)
    out = []
    for p, b in bounds.items():
        if b["start"] is None or b["end"] is None:
            continue
        plen = period_length_s(p)
        knots = [(float(plen), int(b["start"])), (0.0, int(b["end"]))]
        for r in b["replays"]:
            if r["remaining_s"] is None:
                continue
            pred = _interp_wall(r["remaining_s"], knots)
            if pred is None:
                continue
            out.append(abs(pred - int(r["knot_wall_ts"])))
    return out


def snap_to_entry(rows: list[dict], entry_ts: int) -> dict:
    """Last action with modeled wall ≤ entry. Intermission uses last completed."""
    first_start = None
    last_end = None
    for r in rows:
        typ = (r.get("actionType") or "").lower()
        sub = (r.get("subType") or "").lower()
        if typ == "period" and sub == "start" and r["period"] == 1 and r["knot_wall_ts"]:
            first_start = r["knot_wall_ts"]
        if typ == "period" and sub == "end" and r["knot_wall_ts"]:
            last_end = r["knot_wall_ts"]
    candidates = [r for r in rows if r["modeled_wall_ts"] is not None and r["modeled_wall_ts"] <= entry_ts]
    if not candidates:
        if first_start is not None and entry_ts < first_start:
            return {
                "snap_idx": None,
                "game_phase": "GAME_NOT_STARTED",
                "first_period_start_ts": first_start,
                "last_period_end_ts": last_end,
            }
        # Fall back: last action with elapsed defined if walls missing entirely.
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
        # Intermission: snap period has ended and next period start is after entry.
        nxt = None
        for r in rows:
            if r["period"] is not None and snap["period"] is not None:
                if r["period"] == snap["period"] + 1:
                    typ = (r.get("actionType") or "").lower()
                    sub = (r.get("subType") or "").lower()
                    if typ == "period" and sub == "start" and r["knot_wall_ts"]:
                        nxt = r["knot_wall_ts"]
                        break
        ended = None
        for r in rows:
            typ = (r.get("actionType") or "").lower()
            sub = (r.get("subType") or "").lower()
            if typ == "period" and sub == "end" and r["period"] == snap["period"] and r["knot_wall_ts"]:
                ended = r["knot_wall_ts"]
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


def classify_confidence(
    rows: list[dict],
    snap: dict,
    entry_ts: int,
    header: dict,
    residuals: list[float],
) -> tuple[str, str]:
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
    idx = snap.get("snap_idx")
    snap_row = rows[idx] if idx is not None else None
    bounds = period_bounds(rows)
    p = snap_row["period"] if snap_row else None
    b = bounds.get(p) if p is not None else None
    duration_ok = True
    if b and b.get("start") and b.get("end"):
        dur = b["end"] - b["start"]
        if p is not None and p <= 4:
            duration_ok = 6 * 60 <= dur <= 50 * 60
        else:
            duration_ok = 3 * 60 <= dur <= 25 * 60
    med_res = float(sorted(residuals)[len(residuals) // 2]) if residuals else None
    replay_ok = med_res is None or med_res <= 180
    if phase == "GAME_NOT_STARTED":
        return "MEDIUM", "GAME_NOT_STARTED"
    if phase in ("INTERMISSION", "GAME_ENDED"):
        return "MEDIUM", phase
    if phase == "WALL_MISSING_FALLBACK":
        return "LOW", "WALL_MISSING_FALLBACK"
    if b and b.get("start") and b.get("end") and duration_ok and phase == "IN_PERIOD":
        if residuals and len(residuals) >= 2 and replay_ok:
            return "HIGH", "IN_PERIOD_REPLAY_VALIDATED"
        if residuals and len(residuals) >= 2 and not replay_ok:
            return "MEDIUM", "IN_PERIOD_REPLAY_RESIDUAL"
        return "HIGH" if duration_ok else "MEDIUM", "IN_PERIOD_BOUNDS"
    return "LOW", "INCOMPLETE_BOUNDS"


def team_scores(snap_row: dict | None, team_is_home: bool) -> tuple[int | None, int | None]:
    if snap_row is None:
        return None, None
    h, a = snap_row["score_home"], snap_row["score_away"]
    if team_is_home:
        return h, a
    return a, h
