"""Score the derived-four 936 at entries 78, 79, and 81. Does not write the ex-ante artifact."""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roller.choosin_texas.first78.artifact import repo_root, strategy_sha256
from roller.choosin_texas.first78.eligibility import find_entry, stop_after
from roller.choosin_texas.first78.membership import MEMBERSHIP_N, load_membership
from roller.choosin_texas.first78.outcomes import cell_name, gross_threshold_cents

PATH_STOPS = (52, 57, 62, 67, 72, 75, 77)
MID_STOPS = (60, 64, 70, 74)
COMPARE_STOPS = (65,)
OFFICIAL_STOP = 67
ALL_STOPS = tuple(sorted(set(PATH_STOPS + MID_STOPS + COMPARE_STOPS + (OFFICIAL_STOP,))))
ENTRIES = (
    {"entry_cents": 78, "gain_cents": 22, "cap_cents": 84, "rule": "FIRST78"},
    {"entry_cents": 79, "gain_cents": 21, "cap_cents": 85, "rule": "FIRST79"},
    {"entry_cents": 81, "gain_cents": 19, "cap_cents": 87, "rule": "FIRST81"},
)
LATEST_RELATIVE = "research/first78_derived_four_v1/LATEST.json"


def _bought(home: int, away: int, side: str) -> int | None:
    if side == "home":
        return home - away
    if side == "away":
        return away - home
    return None


def _nba_cache(event_id: str, cache: dict[str, list]) -> list | None:
    if event_id in cache:
        return cache[event_id]
    from first78.clocks import nba_crosswalk, nba_mod

    cw = nba_crosswalk().get(event_id) or {}
    nba_id = cw.get("nba_game_id")
    actions: list | None = None
    if cw.get("match_status") == "MATCHED" and nba_id:
        mod = nba_mod()
        pbp = mod.load_pbp(str(nba_id))
        box = mod.load_box(str(nba_id))
        if pbp:
            header = mod.box_header(box)
            actions = mod.enrich_actions(pbp.get("game", {}).get("actions") or [], header)
    cache[event_id] = actions or []
    return cache[event_id]


def _snap(actions: list, ts: int) -> dict[str, Any]:
    from first78.clocks import nba_mod

    snap = nba_mod().snap_to_entry(actions, int(ts))
    idx = snap.get("snap_idx")
    row = actions[idx] if isinstance(idx, int) and 0 <= idx < len(actions) else None
    if row is None:
        return {"period": None, "remaining_s": None, "home": None, "away": None}
    home = row.get("score_home")
    away = row.get("score_away")
    if home == 0 and away == 0:
        home, away = None, None
    return {
        "period": row.get("period"),
        "remaining_s": row.get("remaining_s"),
        "home": home,
        "away": away,
    }


def _empty_stop() -> dict[str, Any]:
    return {"n": 0, "gross_sum_cents": 0, "resolved": 0, "cells": Counter(), "excluded_cap": 0}


def _add(bucket: dict[str, Any], *, cell: str, gross: int | None) -> None:
    bucket["n"] += 1
    bucket["cells"][cell] += 1
    if gross is not None:
        bucket["resolved"] += 1
        bucket["gross_sum_cents"] += int(gross)


def _public_stop(bucket: dict[str, Any]) -> dict[str, Any]:
    cells = {key: int(bucket["cells"].get(key, 0)) for key in ("YES_NO_STOP", "YES_STOP", "NO_NO_STOP", "NO_STOP", "UNRESOLVED")}
    resolved = int(bucket["resolved"])
    gross = int(bucket["gross_sum_cents"])
    return {
        "n": int(bucket["n"]),
        "resolved": resolved,
        "gross_sum_cents": gross,
        "gross_ev_per_contract": _fraction(gross, resolved),
        "cells": cells,
        "excluded_cap": int(bucket["excluded_cap"]),
    }


def _fraction(numer: int, denom: int) -> str | None:
    from fractions import Fraction

    if denom <= 0:
        return None
    return format(Fraction(int(numer), int(denom)), "f")


def run_derived(progress=print) -> Path:
    src = repo_root() / "research/first78_67_portfolio_v1/src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from first78.extract import _index_candles, _read_bars

    root = repo_root()
    membership = load_membership()
    candles = {
        "NBA": _index_candles(root / "Backtesting Suite/Data/NBA/2025-2026/warehouse/normalized/nba"),
        "NCAAB": _index_candles(root / "Backtesting Suite/Data/NCAAB/2025-2026/warehouse/normalized/ncaab"),
    }
    exclusions: Counter[str] = Counter()
    books = {
        spec["entry_cents"]: {
            "rule": spec["rule"],
            "entry_cents": spec["entry_cents"],
            "gain_cents": spec["gain_cents"],
            "cap_cents": spec["cap_cents"],
            "qualified": 0,
            "stops": {stop: {"pool": _empty_stop(), "slices": {name: _empty_stop() for name in ("Q2", "Q3", "H1_2", "H2_1")}} for stop in ALL_STOPS},
        }
        for spec in ENTRIES
    }
    clock_samples: list[dict] = []
    scatter: list[dict] = []
    nba_actions: dict[str, list] = {}
    for index, member in enumerate(membership, start=1):
        if progress and index % 100 == 0:
            progress(f"members {index}")
        path = candles[member["sport"]].get(member["ticker"])
        if path is None:
            exclusions["NO_CANDLES"] += 1
            continue
        bars = _read_bars(path)
        for spec in ENTRIES:
            entry = find_entry(bars, hit_cents=spec["entry_cents"])
            if not entry.get("cross_found"):
                if spec["entry_cents"] == 78:
                    exclusions[str(entry.get("reason") or "NO_CROSS")] += 1
                continue
            book = books[spec["entry_cents"]]
            book["qualified"] += 1
            terminal = member["terminal"]
            stop67 = None
            for stop in ALL_STOPS:
                slot = book["stops"][stop]
                found = stop_after(entry, stop)
                stopped = found.get("stop_ts") is not None
                cell = cell_name(terminal=terminal, stopped=stopped)
                gross = gross_threshold_cents(terminal=terminal, stopped=stopped, stop_cents=stop, entry_cents=spec["entry_cents"])
                _add(slot["pool"], cell=cell, gross=gross)
                _add(slot["slices"][member["slice"]], cell=cell, gross=gross)
                if spec["entry_cents"] == 78 and stop == OFFICIAL_STOP:
                    stop67 = found
            if spec["entry_cents"] != 78 or member["sport"] != "NBA":
                continue
            actions = _nba_snap_actions(member["event_id"], nba_actions)
            entry_snap = _snap(actions, int(entry["signal_ts"])) if actions else {}
            stop_snap = {}
            if stop67 and stop67.get("stop_ts") is not None and actions:
                stop_snap = _snap(actions, int(stop67["stop_ts"]))
            if member["slice"] in {"Q2", "Q3"} and stop67 and stop67.get("stop_ts") is not None:
                clock_samples.append(
                    {
                        "slice": member["slice"],
                        "stopped": True,
                        "stop_period": stop_snap.get("period"),
                        "stop_remaining_s": stop_snap.get("remaining_s"),
                    }
                )
            final = _bought(member["final_home"], member["final_away"], member["side"]) if member["final_home"] is not None and member["final_away"] is not None else None
            entry_margin = None
            if entry_snap.get("home") is not None and entry_snap.get("away") is not None:
                entry_margin = _bought(int(entry_snap["home"]), int(entry_snap["away"]), member["side"])
            stop_margin = None
            if stop_snap.get("home") is not None and stop_snap.get("away") is not None:
                stop_margin = _bought(int(stop_snap["home"]), int(stop_snap["away"]), member["side"])
            scatter.append(
                {
                    "ticker": member["ticker"],
                    "slice": member["slice"],
                    "stopped": bool(stop67 and stop67.get("stop_ts") is not None),
                    "entry_margin": entry_margin,
                    "final_margin": final,
                    "stop_margin": stop_margin,
                }
            )
    payload = {
        "schema_version": "first78_derived_four_v1",
        "status": "OBSERVED",
        "population_id": "DERIVED_FOUR_FIRST78",
        "official_strategy_id": "FIRST78_67",
        "strategy_sha256": strategy_sha256(),
        "membership_n": MEMBERSHIP_N,
        "live_execution": False,
        "submits": False,
        "candle_path_is_not_a_fill": True,
        "fee_applicability": "FEE_APPLICABILITY_UNVERIFIED",
        "exclusions": dict(exclusions),
        "path_stops": list(PATH_STOPS),
        "mid_stops": list(MID_STOPS),
        "compare_stops": list(COMPARE_STOPS),
        "official_stop_cents": OFFICIAL_STOP,
        "books": {str(cents): _publish_book(book) for cents, book in books.items()},
        "clock_samples": clock_samples,
        "scatter_rows": scatter,
    }
    run_id = "first78_derived_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload["run_id"] = run_id
    out_dir = root / "research/first78_derived_four_v1/runs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = out_dir / "summary.json"
    summary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    latest = root / LATEST_RELATIVE
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "summary": f"research/first78_derived_four_v1/runs/{run_id}/summary.json",
                "strategy_sha256": payload["strategy_sha256"],
                "population_id": "DERIVED_FOUR_FIRST78",
            },
            indent=2,
        )
        + "\n"
    )
    if progress:
        progress(f"wrote {summary} qualified78={books[78]['qualified']}")
    return summary


def _nba_snap_actions(event_id: str, cache: dict[str, list]) -> list:
    loaded = _nba_cache(event_id, cache)
    return loaded or []


def _publish_book(book: dict) -> dict[str, Any]:
    stops = {}
    for stop, slot in book["stops"].items():
        stops[str(stop)] = {
            "pool": _public_stop(slot["pool"]),
            "slices": {name: _public_stop(bucket) for name, bucket in slot["slices"].items()},
        }
    return {
        "rule": book["rule"],
        "entry_cents": book["entry_cents"],
        "gain_cents": book["gain_cents"],
        "cap_cents": book["cap_cents"],
        "qualified": book["qualified"],
        "stops": stops,
    }


def main() -> None:
    run_derived()


if __name__ == "__main__":
    main()
