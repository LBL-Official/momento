"""As-of clocks. NBA intra-quarter seconds are modeled. NCAAB uses observed walls."""

from __future__ import annotations

import importlib.util
import json
import sys
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
NBA_PBP = REPO / "apps/nba-data/scripts/game_path_engine_v2"
NCAAB_ALIGN = REPO / "apps/ncaab-data/scripts/ncaab_pbp_align.py"
NBA_XWALK = (
    REPO
    / "Backtesting Suite/Data/NBA/2025-2026/warehouse/normalized/nba/pbp/game_crosswalk.json"
)
NCAAB_XWALK = (
    REPO
    / "Backtesting Suite/Data/NCAAB/2025-2026/warehouse/normalized/ncaab/pbp/game_crosswalk.json"
)

NBA_WINDOWS = frozenset({"Q2", "Q3"})
NCAAB_WINDOWS = frozenset({"H1_2", "H2_1"})
PRIMARY = frozenset({"HIGH", "MEDIUM"})


def _load(name: str, path: Path, extra: Path | None = None):
    if extra is not None and str(extra) not in sys.path:
        sys.path.insert(0, str(extra))
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@lru_cache(maxsize=1)
def nba_mod():
    return _load("first78_nba_pbp", NBA_PBP / "pbp.py", NBA_PBP)


@lru_cache(maxsize=1)
def ncaab_mod():
    return _load("first78_ncaab_pbp", NCAAB_ALIGN)


@lru_cache(maxsize=1)
def nba_crosswalk() -> dict[str, dict]:
    rows = json.loads(NBA_XWALK.read_text())
    return {r["event_id"]: r for r in rows}


@lru_cache(maxsize=1)
def ncaab_crosswalk() -> dict[str, dict]:
    rows = json.loads(NCAAB_XWALK.read_text())
    return {r["event_id"]: r for r in rows}


def nba_bucket(confidence: str | None, phase: str | None, period: int | None) -> str:
    """Same rule as first80_quarter_barrier_survival.entry_bucket."""
    if confidence not in PRIMARY:
        return "UNALIGNED"
    if phase in (None, "GAME_NOT_STARTED", "UNALIGNED"):
        return "UNALIGNED"
    if period is None:
        return "UNALIGNED"
    period_i = int(period)
    if period_i >= 5:
        return "OT"
    if 1 <= period_i <= 4:
        return f"Q{period_i}"
    return "UNALIGNED"


def align(sport: str, event_id: str, ts: int) -> dict:
    if sport == "NBA":
        return _align_nba(event_id, int(ts))
    if sport == "NCAAB":
        return _align_ncaab(event_id, int(ts))
    return {"bucket": "UNALIGNED", "clock_quality": "UNKNOWN_SPORT", "period": None, "period_remaining_s": None, "phase": None}


def _align_nba(event_id: str, ts: int) -> dict:
    cw = nba_crosswalk().get(event_id) or {}
    nba_id = cw.get("nba_game_id")
    mod = nba_mod()
    out = {
        "bucket": "UNALIGNED",
        "clock_quality": "UNALIGNED",
        "period": None,
        "period_remaining_s": None,
        "phase": None,
        "clock_source": "NBA_PBP_PERIOD_BOUNDED_LINEAR",
        "seconds_are_modeled": True,
        "reason": None,
    }
    if cw.get("match_status") != "MATCHED" or not nba_id:
        out["reason"] = "UNMATCHED_CROSSWALK"
        return out
    pbp = mod.load_pbp(str(nba_id))
    box = mod.load_box(str(nba_id))
    if not pbp:
        out["reason"] = "NO_PBP"
        return out
    header = mod.box_header(box)
    actions = mod.enrich_actions(pbp.get("game", {}).get("actions") or [], header)
    snap = mod.snap_to_entry(actions, ts)
    residuals = mod.replay_residuals(actions)
    conf, reason = mod.classify_confidence(actions, snap, ts, header, residuals)
    idx = snap.get("snap_idx")
    row = actions[idx] if idx is not None and 0 <= idx < len(actions) else None
    period = None if row is None else row.get("period")
    remaining = None if row is None else row.get("remaining_s")
    phase = snap.get("game_phase")
    out.update(
        {
            "bucket": nba_bucket(conf, phase, period),
            "clock_quality": conf,
            "period": period,
            "period_remaining_s": remaining,
            "phase": phase,
            "reason": reason,
        }
    )
    return out


def _align_ncaab(event_id: str, ts: int) -> dict:
    cw = ncaab_crosswalk().get(event_id) or {}
    espn_id = cw.get("espn_game_id")
    mod = ncaab_mod()
    out = {
        "bucket": "UNALIGNED",
        "clock_quality": "UNALIGNED",
        "period": None,
        "period_remaining_s": None,
        "phase": None,
        "clock_source": "NCAAB_ESPN_OBSERVED_WALL",
        "seconds_are_modeled": False,
        "reason": None,
    }
    if cw.get("match_status") != "MATCHED" or not espn_id:
        out["reason"] = "UNMATCHED_CROSSWALK"
        return out
    packed = mod.load_plays(str(espn_id))
    if not packed:
        out["reason"] = "NO_PBP"
        return out
    plays = packed.get("plays") or packed.get("items") or []
    if isinstance(packed, dict) and not plays:
        # ESPN summary shape used by the aligner: plays list under a known key.
        plays = packed.get("plays") or []
    actions = mod.enrich_actions(plays)
    snap = mod.snap_to_entry(actions, ts)
    conf, reason = mod.classify_confidence(actions, snap, ts)
    clock = mod.snap_clock(actions, ts)
    out.update(
        {
            "bucket": mod.entry_bucket(conf, clock.get("phase"), clock.get("period"), clock.get("period_remaining_s")),
            "clock_quality": conf,
            "period": clock.get("period"),
            "period_remaining_s": clock.get("period_remaining_s"),
            "phase": clock.get("phase"),
            "reason": reason,
        }
    )
    return out


def window_ok(sport: str, bucket: str) -> bool:
    if sport == "NBA":
        return bucket in NBA_WINDOWS
    if sport == "NCAAB":
        return bucket in NCAAB_WINDOWS
    return False
